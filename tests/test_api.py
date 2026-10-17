from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app, settings

client = TestClient(app)


def _write_run(root: Path, run_id: str) -> None:
    d = root / run_id
    d.mkdir(parents=True, exist_ok=True)
    block = {"n": 4, "rate": 0.5, "ci95": [0.15, 0.85]}
    (d / "config.json").write_text(json.dumps({
        "run_id": run_id, "label": "api-test", "created_utc": "2026-10-16T00:00:00+00:00",
        "golden": {"name": "refusal", "version": "v1", "split": "all"},
        "judge": {"name": "reference"}, "target": {"ready": {"version": "1.1.0"}}}))
    (d / "summary.json").write_text(json.dumps({
        "cases": 4, "accuracy": block, "retrieval_hit_at_5": block, "false_refusal": block,
        "correct_abstention": None, "citation_hit": block, "latency_ms": {"p50": 5, "p95": 9},
        "cost_usd": {"per_question": None}}))
    (d / "cases.jsonl").write_text("\n".join(json.dumps(
        {"id": f"c{i}", "correct": i % 2 == 0, "response": {"answer": "x"}}) for i in range(4)))


def _write_redteam(root: Path) -> None:
    d = root / "rt-test"
    d.mkdir(parents=True, exist_ok=True)
    (d / "redteam.json").write_text(json.dumps({
        "cases": 2, "passed": 1, "pass_rate": 0.5, "target": {"ready": {"version": "1.0.0"}},
        "categories": {"pii_leakage": {"pass_rate": 0.5, "severity": "critical",
                                       "failures": ["pii-1"]}}}))


@pytest.fixture(scope="module", autouse=True)
def files():
    _write_run(Path(settings.runs_dir), "api-run")
    _write_redteam(Path(settings.results_dir))


def test_health_and_ui():
    assert client.get("/health/live").json() == {"status": "ok"}
    ready = client.get("/health/ready").json()
    assert ready["status"] == "ready" and ready["runs"] >= 2 and ready["goldens"] >= 3
    assert "RAG evaluation" in client.get("/").text


def test_goldens():
    goldens = {(g["name"], g["version"]): g for g in client.get("/api/v1/goldens").json()}
    assert goldens[("refusal", "v1")]["count"] == 30
    assert goldens[("refusal", "v1")]["items_present"]
    items = client.get("/api/v1/goldens/refusal/v1/items?limit=3").json()
    assert len(items) == 3 and items[0]["answer_type"] == "refusal"
    assert client.get("/api/v1/goldens/nope/v1/items").status_code == 404


def test_runs_listing_detail_and_cases():
    runs = {r["run_id"]: r for r in client.get("/api/v1/runs").json()}
    assert runs["api-run"]["kind"] == "golden" and runs["api-run"]["target_version"] == "1.1.0"
    assert runs["rt-test"]["kind"] == "redteam" and runs["rt-test"]["location"]
    detail = client.get("/api/v1/runs/api-run").json()
    assert set(detail) == {"config", "summary"}
    cases = client.get("/api/v1/runs/api-run/cases?only_failures=true").json()
    assert [c["id"] for c in cases] == ["c1", "c3"] and "response" not in cases[0]
    assert client.get("/api/v1/runs/rt-test/cases").status_code == 404
    assert client.get("/api/v1/runs/missing").status_code == 404
    page = client.get("/api/v1/compare?runs=api-run").text
    assert "api-test" in page and "<pre>" in page


def test_metrics_include_eval_gauges():
    client.get("/health/live")
    text = client.get("/metrics/").text
    assert "http_requests_total" in text
    assert 'eval_accuracy{golden="refusal",run="api-run",split="all"} 0.5' in text
    assert 'eval_redteam_pass_rate{category="pii_leakage",run="rt-test"} 0.5' in text


def test_judge_endpoint():
    body = {"question": "Capex?", "gold": "$285 million", "answer": "It was $285 million",
            "answer_type": "numeric"}
    assert client.post("/api/v1/judge", json=body).json()["label"] == "CORRECT"
    assert client.post("/api/v1/judge", json=body | {"answer_type": "essay"}).status_code == 422


@pytest.mark.exercise
def test_start_run_in_background(monkeypatch):
    from rag_eval import targets

    def fake_ask(self, question, **kwargs):
        return targets.Response("I can't answer that from the filings provided.", refused=True)

    monkeypatch.setattr(targets.HttpRagTarget, "ask", fake_ask)
    r = client.post("/api/v1/runs", json={"golden": "refusal", "split": "all", "limit": 5,
                                          "label": "bg"})
    assert r.status_code == 202 and r.json()["cases"] == 5
    job_id = r.json()["job_id"]
    for _ in range(100):
        status = client.get(f"/api/v1/jobs/{job_id}").json()
        if status["status"] != "running":
            break
        time.sleep(0.05)
    assert status["status"] == "done", status
    detail = client.get(f"/api/v1/runs/{status['run_id']}").json()
    assert detail["summary"]["correct_abstention"]["rate"] == 1.0
    assert client.get("/api/v1/jobs/nope").status_code == 404
    assert client.post("/api/v1/runs", json={"golden": "nope"}).status_code == 404
    assert client.post("/api/v1/runs", json={"golden": "refusal",
                                             "split": "half"}).status_code == 422
