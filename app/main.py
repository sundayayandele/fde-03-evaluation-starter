"""Evaluation service: golden sets, runs, red-team results, a judge endpoint, Prometheus gauges
for Grafana, and a small UI.

Runs are files (runs/<id>/ and the published evals/results/<id>/), so the service is
stateless apart from runs it starts itself, which execute in a background thread.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from prometheus_client import REGISTRY, Counter, Histogram, make_asgi_app
from prometheus_client.core import GaugeMetricFamily
from pydantic import BaseModel, Field

from rag_eval import __version__, golden
from rag_eval.config import get_settings

settings = get_settings()
app = FastAPI(title="RAG evaluation service", version=__version__,
              description="Golden sets, evaluation runs, red-team results and a release gate "
                          "for retrieval-augmented systems.")
app.mount("/metrics", make_asgi_app())
UI = Path(__file__).parent / "static" / "index.html"

REQUESTS = Counter("http_requests_total", "HTTP requests handled", ["method", "route", "status"])
LATENCY = Histogram("http_request_duration_seconds", "HTTP request duration", ["method", "route"])
RUNS_STARTED = Counter("eval_runs_started_total", "Evaluation runs started by the service")
_jobs: dict[str, dict] = {}
_lock = threading.Lock()


def run_roots() -> list[Path]:
    return [Path(p) for p in (settings.runs_dir, settings.results_dir) if p]


def find_runs() -> dict[str, Path]:
    """run_id → directory, for every directory holding a summary.json or redteam.json."""
    found: dict[str, Path] = {}
    for root in run_roots():
        if not root.exists():
            continue
        for d in sorted(root.iterdir()):
            if d.is_dir() and ((d / "summary.json").exists() or (d / "redteam.json").exists()):
                found.setdefault(d.name, d)
    return found


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class RunCollector:
    """Gauges read from the run files at scrape time, so Grafana always shows what is on disk."""

    def collect(self):
        acc = GaugeMetricFamily("eval_accuracy", "Share of cases judged correct",
                                labels=["run", "golden", "split"])
        hit = GaugeMetricFamily("eval_retrieval_hit_at_5", "Share of cases with evidence in "
                                "the top 5 retrieved passages", labels=["run", "golden", "split"])
        fr = GaugeMetricFamily("eval_false_refusal_rate", "Share of answerable cases refused",
                               labels=["run", "golden", "split"])
        p95 = GaugeMetricFamily("eval_latency_p95_ms", "95th percentile answer latency",
                                labels=["run", "golden", "split"])
        rt = GaugeMetricFamily("eval_redteam_pass_rate", "Red-team pass rate by category",
                               labels=["run", "category"])
        for run_id, d in find_runs().items():
            if (d / "summary.json").exists():
                s, g = _read(d / "summary.json"), _read(d / "config.json")["golden"]
                labels = [run_id, g["name"], g["split"]]
                for family, value in ((acc, s["accuracy"]["rate"]),
                                      (hit, (s.get("retrieval_hit_at_5") or {}).get("rate")),
                                      (fr, (s.get("false_refusal") or {}).get("rate")),
                                      (p95, s["latency_ms"]["p95"])):
                    if value is not None:
                        family.add_metric(labels, value)
            if (d / "redteam.json").exists():
                r = _read(d / "redteam.json")
                rt.add_metric([run_id, "overall"], r["pass_rate"])
                for cat, res in r["categories"].items():
                    rt.add_metric([run_id, cat], res["pass_rate"])
        yield from (acc, hit, fr, p95, rt)


if not getattr(REGISTRY, "_rag_eval_collector", False):
    REGISTRY.register(RunCollector())
    REGISTRY._rag_eval_collector = True


@app.middleware("http")
async def observe(request: Request, call_next):
    started = time.perf_counter()
    response = await call_next(request)
    path = getattr(request.scope.get("route"), "path", "unmatched")
    REQUESTS.labels(request.method, path, str(response.status_code)).inc()
    LATENCY.labels(request.method, path).observe(time.perf_counter() - started)
    return response


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def ui() -> str:
    return UI.read_text(encoding="utf-8")


@app.get("/health/live")
def live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready")
def ready() -> dict:
    return {"status": "ready", "version": __version__, "environment": settings.environment,
            "goldens": len(list_goldens()), "runs": len(find_runs()),
            "target_url": settings.target_url}


@app.get("/api/v1/goldens")
def list_goldens() -> list[dict]:
    root = Path(settings.goldens_dir)
    out = []
    for manifest in sorted(root.glob("*/*/manifest.json")):
        m = _read(manifest)
        m["items_present"] = (manifest.parent / "items.jsonl").exists()
        out.append(m)
    return out


@app.get("/api/v1/goldens/{name}/{version}/items")
def golden_items(name: str, version: str, split: str = "all",
                 limit: int = Query(50, ge=1, le=500)) -> list[dict]:
    try:
        items = golden.load(Path(settings.goldens_dir), name, version, split)
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(404, f"golden set {name}/{version} not available: build it with "
                                 f"`rag-eval golden build {name}`") from e
    return [i.to_dict() for i in items[:limit]]


@app.get("/api/v1/runs")
def list_runs() -> list[dict]:
    out = []
    for run_id, d in find_runs().items():
        row: dict = {"run_id": run_id, "location": d.parent.name}
        if (d / "summary.json").exists():
            c, s = _read(d / "config.json"), _read(d / "summary.json")
            row |= {"kind": "golden", "label": c.get("label"), "golden": c["golden"],
                    "created_utc": c.get("created_utc"), "judge": c["judge"]["name"],
                    "cases": s["cases"], "accuracy": s["accuracy"],
                    "retrieval_hit_at_5": s.get("retrieval_hit_at_5"),
                    "false_refusal": s.get("false_refusal"),
                    "correct_abstention": s.get("correct_abstention"),
                    "latency_ms": s["latency_ms"],
                    "target_version": (c["target"].get("ready") or {}).get("version")}
        else:
            r = _read(d / "redteam.json")
            row |= {"kind": "redteam", "pass_rate": r["pass_rate"], "cases": r["cases"],
                    "categories": {k: v["pass_rate"] for k, v in r["categories"].items()},
                    "target_version": ((r.get("target") or {}).get("ready") or {}).get(
                        "version")}
        out.append(row)
    return out


def _run_dir(run_id: str) -> Path:
    d = find_runs().get(run_id)
    if d is None:
        raise HTTPException(404, f"no run {run_id!r}")
    return d


@app.get("/api/v1/runs/{run_id}")
def get_run(run_id: str) -> dict:
    d = _run_dir(run_id)
    return {name: _read(d / f"{name}.json") for name in ("config", "summary", "redteam")
            if (d / f"{name}.json").exists()}


@app.get("/api/v1/runs/{run_id}/cases")
def run_cases(run_id: str, only_failures: bool = False,
              limit: int = Query(50, ge=1, le=1000)) -> list[dict]:
    d = _run_dir(run_id)
    path = d / "cases.jsonl"
    if not path.exists():
        raise HTTPException(404, "per-case results are not published for this run "
                                 "(dataset not redistributable or summary-only)")
    rows = [json.loads(line) for line in path.read_text("utf-8").splitlines() if line.strip()]
    if only_failures:
        rows = [r for r in rows if not r["correct"]]
    for r in rows:
        r.pop("response", None)
    return rows[:limit]


class StartRun(BaseModel):
    golden: str
    version: str = "v1"
    split: str = Field("test", pattern="^(all|dev|test)$")
    target_url: str | None = None
    judge: str = Field("reference", pattern="^(reference|llm)$")
    scope: str = Field("routed", pattern="^(routed|doc)$")
    limit: int | None = Field(None, ge=1, le=1000)
    label: str = Field("", max_length=60)


@app.post("/api/v1/runs", status_code=202)
def start_run(body: StartRun) -> dict:
    """Start a run in the background; poll GET /api/v1/jobs/{job_id}."""
    from rag_eval import runner
    from rag_eval.judge import get_judge
    from rag_eval.targets import HttpRagTarget

    try:
        items = golden.load(Path(settings.goldens_dir), body.golden, body.version, body.split)
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(404, f"golden set {body.golden}/{body.version} not available") from e
    items = items[:body.limit] if body.limit else items
    manifest = _read(Path(settings.goldens_dir) / body.golden / body.version / "manifest.json")
    job_id = f"job-{int(time.time() * 1000)}"
    target = HttpRagTarget(body.target_url or settings.target_url,
                           timeout=settings.target_timeout_seconds)
    judge = get_judge(body.judge) if body.judge == "reference" else get_judge(
        "llm", role=settings.judge_role)

    def work() -> None:
        try:
            out = runner.run(target, items, judge, runs_dir=Path(settings.runs_dir),
                             golden={"name": body.golden, "version": body.version,
                                     "split": body.split, "cases": len(items),
                                     "items_sha256": manifest["items_sha256"]},
                             label=body.label, scope=body.scope,
                             concurrency=settings.concurrency)
            status = {"status": "done", "run_id": out.name}
        except Exception as e:  # noqa: BLE001 - reported to the caller
            status = {"status": "failed", "error": f"{type(e).__name__}: {e}"[:300]}
        with _lock:
            _jobs[job_id] |= status

    with _lock:
        _jobs[job_id] = {"status": "running", "cases": len(items)}
    RUNS_STARTED.inc()
    threading.Thread(target=work, daemon=True).start()
    return {"job_id": job_id, "cases": len(items)}


@app.get("/api/v1/jobs/{job_id}")
def job(job_id: str) -> dict:
    with _lock:
        if job_id not in _jobs:
            raise HTTPException(404, f"no job {job_id!r}")
        return dict(_jobs[job_id])


class JudgeRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    gold: str = Field(min_length=1, max_length=4000)
    answer: str = Field(max_length=8000)
    answer_type: str = Field("free_text", pattern="^(numeric|yes_no_maybe|free_text|span|"
                                                  "absent|refusal)$")
    refused: bool = False


@app.post("/api/v1/judge")
def judge_one(body: JudgeRequest) -> dict:
    """Grade one answer with the reference judge (deterministic, free)."""
    from rag_eval.judge import ReferenceJudge

    v = ReferenceJudge().judge(body.question, body.gold, body.answer, body.answer_type,
                               body.refused)
    return {"label": v.label, "reason": v.reason, "judge": "reference"}


@app.get("/api/v1/compare", response_class=HTMLResponse)
def compare(runs: Annotated[list[str], Query()]) -> str:
    """Markdown comparison table of golden-set runs (as text/markdown in an HTML body)."""
    import html

    from rag_eval import report, runner

    loaded = [runner.load_run(_run_dir(r)) for r in runs if (_run_dir(r) / "config.json").exists()]
    return f"<pre>{html.escape(report.compare_table(loaded))}</pre>"
