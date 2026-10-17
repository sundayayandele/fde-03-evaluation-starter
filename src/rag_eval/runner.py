"""Run a golden set against a target, judge every answer, and store the run as files.

runs/<run_id>/
  config.json    target description, golden set name/version/sha256, judge, settings, date
  cases.jsonl    one line per case: item fields, the full response, label, scores
  summary.json   aggregate metrics with 95% intervals
"""

from __future__ import annotations

import datetime as dt
import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from rag_eval import __version__
from rag_eval.golden import GoldenItem
from rag_eval.metrics import citation_scores, percentile, wilson_interval
from rag_eval.targets import Response

ANSWERABLE = {"numeric", "free_text", "yes_no_maybe", "span"}


def retrieval_hit(hits: list[dict], evidence: list[dict], k: int) -> bool | None:
    """Did any of the top-k retrieved passages land on gold evidence? None without hits."""
    if not hits or not evidence:
        return None
    return citation_scores(hits[:k], evidence)["hit"]


def score_case(item: GoldenItem, response: Response, judge) -> dict:
    verdict = judge.judge(question=item.question, gold=item.answer, answer=response.answer,
                          answer_type=item.answer_type, refused=response.refused,
                          alternatives=item.alternatives)
    cites = citation_scores(response.citations, item.evidence) if item.evidence else None
    return {
        "id": item.id, "domain": item.domain, "split": item.split,
        "answer_type": item.answer_type, "question": item.question, "gold": item.answer,
        "answer": response.answer, "judge_label": verdict.label, "judge_reason": verdict.reason,
        "correct": verdict.label == "CORRECT",
        "refused": response.refused,
        "citation_precision": cites["precision"] if cites else None,
        "citation_recall": cites["recall"] if cites else None,
        "citation_hit": cites["hit"] if cites else None,
        "retrieval_hit_at_5": retrieval_hit(response.hits, item.evidence, 5),
        "latency_ms": round(response.latency_ms, 1), "cost_usd": response.cost_usd,
        "error": response.error, "response": response.to_dict(),
    }


def _rate(values: list[bool]) -> dict:
    n, k = len(values), sum(values)
    lo, hi = wilson_interval(k, n)
    return {"n": n, "rate": round(k / n, 4) if n else None, "ci95": [round(lo, 4), round(hi, 4)]}


def _mean(values: list[float | None]) -> float | None:
    vals = [v for v in values if v is not None]
    return round(sum(vals) / len(vals), 4) if vals else None


def summarise(rows: list[dict]) -> dict:
    answerable = [r for r in rows if r["answer_type"] in ANSWERABLE]
    unanswerable = [r for r in rows if r["answer_type"] not in ANSWERABLE]
    costs = [r["cost_usd"] for r in rows if r["cost_usd"] is not None]
    by_type: dict[str, dict] = {}
    for t in sorted({r["answer_type"] for r in rows}):
        by_type[t] = _rate([r["correct"] for r in rows if r["answer_type"] == t])
    by_domain: dict[str, dict] = {}
    for d in sorted({r["domain"] for r in rows}):
        by_domain[d] = _rate([r["correct"] for r in rows if r["domain"] == d])
    hits5 = [r["retrieval_hit_at_5"] for r in rows if r["retrieval_hit_at_5"] is not None]
    return {
        "cases": len(rows),
        "errors": sum(1 for r in rows if r["error"]),
        "accuracy": _rate([r["correct"] for r in rows]),
        "accuracy_answerable": _rate([r["correct"] for r in answerable]),
        "by_answer_type": by_type,
        "by_domain": by_domain,
        "false_refusal": _rate([r["refused"] for r in answerable]),
        "correct_abstention": _rate([r["correct"] for r in unanswerable]) if unanswerable
        else None,
        "retrieval_hit_at_5": _rate(hits5) if hits5 else None,
        "citation_precision": _mean([r["citation_precision"] for r in answerable]),
        "citation_hit": _rate([bool(r["citation_hit"]) for r in answerable
                               if r["citation_hit"] is not None]),
        "latency_ms": {"p50": percentile([r["latency_ms"] for r in rows], 0.5),
                       "p95": percentile([r["latency_ms"] for r in rows], 0.95)},
        "cost_usd": {"total": round(sum(costs), 6) if costs else None,
                     "per_question": round(sum(costs) / len(costs), 6) if costs else None},
    }


def run(target, items: list[GoldenItem], judge, *, runs_dir: Path, golden: dict,
        label: str = "", scope: str = "routed", concurrency: int = 4, tracer=None,
        run_id: str | None = None) -> Path:
    """Evaluate `items` and write the run; returns the run directory."""
    from rag_eval import tracing

    tracer = tracer or tracing.setup()
    run_id = run_id or (dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%SZ") + "-"
                        + (label or uuid.uuid4().hex[:6]))
    out = Path(runs_dir) / run_id
    out.mkdir(parents=True, exist_ok=True)

    def one(item: GoldenItem) -> dict:
        docs = sorted({e["doc"] for e in item.evidence}) if scope == "doc" else None
        with tracing.case_span(tracer, item.id, domain=item.domain,
                               answer_type=item.answer_type) as (span, headers):
            response = target.ask(item.question, docs=docs, headers=headers, case_id=item.id)
            row = score_case(item, response, judge)
            span.set_attribute("eval.label", row["judge_label"])
            span.set_attribute("eval.latency_ms", row["latency_ms"])
            if row["error"]:
                span.set_attribute("eval.error", row["error"])
        return row

    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
        rows = list(pool.map(one, items))
    summary = summarise(rows)
    config = {"run_id": run_id, "label": label, "harness_version": __version__,
              "created_utc": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
              "target": target.describe(), "golden": golden, "judge": judge.describe(),
              "scope": scope, "concurrency": concurrency, "cases": len(rows)}
    (out / "config.json").write_text(json.dumps(config, indent=2))
    with (out / "cases.jsonl").open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    return out


BASELINE_FIELDS = ("id", "answer_type", "correct", "refused", "retrieval_hit_at_5",
                   "citation_hit")


def save_baseline(run_dir: Path, out: Path) -> Path:
    """Per-case outcomes without any text (ids and booleans), safe to commit for any dataset:
    the regression gate needs only these."""
    run = load_run(run_dir)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    header = {"baseline_of": run["config"]["run_id"], "golden": run["config"]["golden"],
              "target": {k: v for k, v in run["config"]["target"].items() if k != "url"},
              "summary": {k: run["summary"][k] for k in ("accuracy", "retrieval_hit_at_5",
                                                          "false_refusal")}}
    with out.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps({"_header": header}) + "\n")
        for row in run["cases"]:
            handle.write(json.dumps({k: row.get(k) for k in BASELINE_FIELDS}) + "\n")
    return out


def load_rows(path: Path) -> list[dict]:
    """Case rows from a run directory or a baseline .jsonl file."""
    path = Path(path)
    if path.is_dir():
        return load_run(path)["cases"]
    rows = [json.loads(line) for line in path.read_text("utf-8").splitlines() if line.strip()]
    return [r for r in rows if "_header" not in r]


def load_run(path: Path) -> dict:
    path = Path(path)
    cases = path / "cases.jsonl"            # absent in published runs (evals/results)
    rows = [json.loads(line) for line in cases.read_text("utf-8").splitlines()
            if line.strip()] if cases.exists() else []
    return {"config": json.loads((path / "config.json").read_text()),
            "summary": json.loads((path / "summary.json").read_text()), "cases": rows}
