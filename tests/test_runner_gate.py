from __future__ import annotations

import json

import pytest

from rag_eval import gate, report, runner
from rag_eval.judge import ReferenceJudge
from tests.conftest import ROOT

GOLDEN = {"name": "toy", "version": "v1", "split": "all", "items_sha256": "x", "cases": 4}


@pytest.fixture
def run_dir(tmp_path, items, answers, fake_target):
    return runner.run(fake_target(answers), items, ReferenceJudge(), runs_dir=tmp_path,
                      golden=GOLDEN, label="toy", concurrency=2, run_id="toy-run")


@pytest.mark.exercise
def test_run_writes_files_and_summary(run_dir):
    assert {p.name for p in run_dir.iterdir()} == {"config.json", "cases.jsonl", "summary.json"}
    run = runner.load_run(run_dir)
    assert run["config"]["golden"] == GOLDEN and run["config"]["judge"] == {"name": "reference"}
    rows = {r["id"]: r for r in run["cases"]}
    assert rows["n1"]["correct"] and not rows["n2"]["correct"]
    assert rows["n1"]["retrieval_hit_at_5"] and rows["n2"]["retrieval_hit_at_5"]
    assert rows["n2"]["citation_hit"] is False
    assert rows["r1"]["judge_label"] == "CORRECT"
    s = run["summary"]
    assert s["cases"] == 4 and s["errors"] == 0
    assert s["accuracy"]["rate"] == 0.75              # n1, y1 and r1; n2 has the wrong year
    assert s["false_refusal"]["rate"] == 0.0
    assert s["correct_abstention"]["rate"] == 1.0
    assert s["by_domain"]["health"]["n"] == 1
    assert s["latency_ms"]["p95"] >= s["latency_ms"]["p50"]


@pytest.mark.exercise
def test_scope_doc_passes_evidence_docs(tmp_path, items, answers, fake_target):
    target = fake_target(answers)
    runner.run(target, items[:1], ReferenceJudge(), runs_dir=tmp_path, golden=GOLDEN,
               scope="doc", concurrency=1)
    assert target.calls[0]["docs"] == ["ACME_2023_10K"]
    assert "traceparent" in target.calls[0]["headers"] or target.calls[0]["headers"] == {}


@pytest.mark.exercise
def test_replay_and_baseline(run_dir, tmp_path, items):
    from rag_eval.targets import ReplayTarget

    replayed = runner.run(ReplayTarget(run_dir / "cases.jsonl"), items, ReferenceJudge(),
                          runs_dir=tmp_path, golden=GOLDEN, run_id="replayed")
    assert runner.load_run(replayed)["summary"]["accuracy"] == \
        runner.load_run(run_dir)["summary"]["accuracy"]
    base = runner.save_baseline(run_dir, tmp_path / "base.jsonl")
    rows = runner.load_rows(base)
    assert len(rows) == 4 and set(rows[0]) == set(runner.BASELINE_FIELDS)
    assert "question" not in base.read_text()           # no text: safe to commit
    assert runner.load_rows(run_dir)[0]["id"]


def test_lookup_and_render():
    summary = {"a": {"rate": 0.5}, "errors": 0, "b": None}
    assert gate.lookup(summary, "a.rate") == 0.5
    assert gate.lookup(summary, "errors") == 0.0
    assert gate.lookup(summary, "b.rate") is None and gate.lookup(summary, "zz") is None
    text = gate.render([gate.GateCheck("x", True, 0.5, ">= 0.4"),
                        gate.GateCheck("y", False, None, "<= 1", "missing")])
    assert text.startswith("**Gate: FAIL** (1/2 checks)") and "**FAIL**" in text


def test_load_gate_profiles():
    cfg = gate.load_gate(ROOT / "config" / "gate.yaml", "ci-offline")
    assert cfg["redteam"]["critical_min"] == 1.0
    assert gate.load_gate(ROOT / "config" / "gate.yaml", "release")["judge"]["kappa_min"] > 0
    with pytest.raises(ValueError):
        gate.load_gate(ROOT / "config" / "gate.yaml", "yolo")


def _rows(values):
    return [{"id": f"c{i}", "correct": v, "retrieval_hit_at_5": v} for i, v in enumerate(values)]


@pytest.mark.exercise
def test_check_gate_thresholds_regression_redteam_judge():
    cfg = {"thresholds": [{"metric": "accuracy.rate", "min": 0.5},
                          {"metric": "latency_ms.p95", "max": 1000},
                          {"metric": "missing.rate", "min": 0.1}],
           "regression": {"metrics": ["correct"], "max_drop": 0.05},
           "redteam": {"critical_min": 1.0, "overall_min": 0.8},
           "judge": {"kappa_min": 0.7}}
    summary = {"accuracy": {"rate": 0.6}, "latency_ms": {"p95": 1500}}
    redteam = {"pass_rate": 0.9, "categories": {
        "pii_leakage": {"pass_rate": 0.8, "severity": "critical", "failures": ["pii-2"]},
        "out_of_scope": {"pass_rate": 0.5, "severity": "medium", "failures": ["o1"]}}}
    checks = {c.name: c for c in gate.check_gate(
        cfg, summary, current_rows=_rows([True] * 30 + [False] * 30),
        baseline_rows=_rows([True] * 60), redteam=redteam, calibration={"kappa": 0.75})}
    assert checks["accuracy.rate"].passed
    assert not checks["latency_ms.p95"].passed
    assert not checks["missing.rate"].passed and checks["missing.rate"].detail == "missing"
    assert not checks["regression:correct"].passed
    assert checks["regression:correct"].observed == -0.5
    assert not checks["redteam:pii_leakage"].passed and "pii-2" in checks[
        "redteam:pii_leakage"].detail
    assert "redteam:out_of_scope" not in checks           # not critical
    assert checks["redteam:overall"].passed and checks["judge:kappa"].passed


@pytest.mark.exercise
def test_check_gate_missing_inputs():
    cfg = {"regression": {"metrics": ["correct"], "max_drop": 0.0},
           "redteam": {"critical_min": 1.0, "overall_min": 0.8}, "judge": {"kappa_min": 0.7}}
    checks = gate.check_gate(cfg, {})
    assert [c.passed for c in checks] == [True, False, False]
    assert checks[0].detail == "no baseline"
    same = gate.check_gate({"regression": {"metrics": ["correct"], "max_drop": 0.0}}, {},
                           current_rows=_rows([True, False] * 20),
                           baseline_rows=_rows([True, False] * 20))
    assert same[0].passed and same[0].observed == 0.0
    disjoint = gate.check_gate({"regression": {"metrics": ["correct"], "max_drop": 0.0}}, {},
                               current_rows=_rows([True]), baseline_rows=[{"id": "zz",
                                                                           "correct": True}])
    assert not disjoint[0].passed and disjoint[0].detail == "no shared cases"


def test_compare_table(tmp_path):
    for name, rate in (("a", 0.5), ("b", 0.75)):
        d = tmp_path / name
        d.mkdir()
        (d / "config.json").write_text(json.dumps({"run_id": name, "label": name,
                                                   "golden": GOLDEN,
                                                   "judge": {"name": "reference"}}))
        block = {"n": 4, "rate": rate, "ci95": [0.1, 0.9]}
        (d / "summary.json").write_text(json.dumps({
            "cases": 4, "accuracy": block, "retrieval_hit_at_5": None, "citation_hit": block,
            "false_refusal": block, "correct_abstention": None,
            "latency_ms": {"p50": 10, "p95": 20}, "cost_usd": {"per_question": None}}))
    table = report.compare_table([runner.load_run(tmp_path / "a"),
                                  runner.load_run(tmp_path / "b")])
    assert "| a | toy/v1 (all, 4) | 0.500 [0.10, 0.90] | — |" in table
    assert table.endswith("Judge: reference.")
