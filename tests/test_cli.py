from __future__ import annotations

import json

import pytest

from rag_eval import cli, runner
from rag_eval.judge import ReferenceJudge
from tests.conftest import ROOT


def run_cli(*args) -> int:
    return cli.main(["--goldens-dir", str(ROOT / "goldens"), *args])


def test_golden_list_and_verify(capsys):
    assert run_cli("golden", "list") == 0
    out = capsys.readouterr().out
    assert "refusal/v1: 30 items" in out and "pubmedqa/v1: 200 items" in out
    assert run_cli("golden", "verify", "refusal") == 0
    assert "ok   refusal/v1" in capsys.readouterr().out


def test_golden_build_refuses_to_overwrite(tmp_path, capsys):
    root = tmp_path / "g"
    assert cli.main(["--goldens-dir", str(root), "golden", "build", "refusal"]) == 0
    assert cli.main(["--goldens-dir", str(root), "golden", "build", "refusal"]) == 1
    assert "exists" in capsys.readouterr().out
    assert cli.main(["--goldens-dir", str(root), "golden", "diff", "refusal",
                     "--other", "v1"]) == 0
    with pytest.raises(SystemExit):
        cli.main(["golden", "build"])


def test_corpus_redteam(tmp_path, capsys):
    assert run_cli("corpus", "redteam", "--out", str(tmp_path)) == 0
    assert (tmp_path / "HALDEN_2025_ANNUAL.pdf").exists()


@pytest.mark.exercise
def test_run_replay_gate_report_baseline_publish(tmp_path, items, answers, fake_target,
                                                 capsys, monkeypatch):
    monkeypatch.chdir(ROOT)
    golden_meta = {"name": "refusal", "version": "v1", "split": "all", "items_sha256": "x"}
    recorded = runner.run(fake_target(answers), items, ReferenceJudge(), runs_dir=tmp_path,
                          golden=golden_meta, run_id="recorded")
    base = tmp_path / "base.jsonl"
    assert cli.main(["baseline", str(recorded), "--out", str(base)]) == 0
    # The gate passes against itself on regression; thresholds decide the rest.
    gate_cfg = tmp_path / "gate.yaml"
    gate_cfg.write_text("profiles:\n  t:\n    thresholds:\n      - {metric: errors, max: 0}\n"
                        "    regression:\n      metrics: [correct]\n      max_drop: 0.0\n")
    assert cli.main(["gate", "--run", str(recorded), "--baseline", str(base), "--profile", "t",
                     "--config", str(gate_cfg), "--out", str(tmp_path / "gate.md")]) == 0
    assert "**Gate: PASS**" in (tmp_path / "gate.md").read_text()
    gate_cfg.write_text("profiles:\n  t:\n    thresholds:\n"
                        "      - {metric: accuracy.rate, min: 0.99}\n")
    assert cli.main(["gate", "--run", str(recorded), "--profile", "t",
                     "--config", str(gate_cfg)]) == 1
    assert cli.main(["report", str(recorded), "--out", str(tmp_path / "r.md")]) == 0
    assert "| recorded |" in (tmp_path / "r.md").read_text()
    assert cli.main(["publish", str(recorded), "--out", str(tmp_path / "pub")]) == 0
    assert sorted(p.name for p in (tmp_path / "pub" / "recorded").iterdir()) == [
        "config.json", "summary.json"]


@pytest.mark.exercise
def test_run_command_against_replay(tmp_path, capsys, monkeypatch):
    """`rag-eval run --replay` re-scores a recorded run of the committed refusal set."""
    from rag_eval import golden
    from rag_eval.targets import Response

    items = golden.load(ROOT / "goldens", "refusal", "v1")
    target = type("T", (), {"describe": lambda self: {"kind": "t"},
                            "ask": lambda self, q, **k: Response("I can't answer that.",
                                                                 refused=True)})()
    recorded = runner.run(target, items, ReferenceJudge(), runs_dir=tmp_path,
                          golden={"name": "refusal"}, run_id="rec")
    assert run_cli("--runs-dir", str(tmp_path), "run", "--golden", "refusal", "--split", "all",
                   "--replay", str(recorded), "--run-id", "again", "--limit", "10") == 0
    summary = json.loads((tmp_path / "again" / "summary.json").read_text())
    assert summary["cases"] == 10 and summary["correct_abstention"]["rate"] == 1.0


@pytest.mark.exercise
def test_calibrate_and_label_commands(tmp_path, capsys):
    out = tmp_path / "cal.json"
    assert run_cli("calibrate", "--per-domain", "5", "--out", str(out)) == 0
    result = json.loads(out.read_text())
    assert result["judge"] == "reference" and result["cases"] > 10
    rows = [{"id": f"c{i}", "domain": "finance", "answer_type": "numeric", "question": "q",
             "gold": "$1", "answer": "$1" if i % 2 else "$2",
             "judge_label": "CORRECT" if i % 2 else "INCORRECT"} for i in range(10)]
    run_dir = tmp_path / "r"
    run_dir.mkdir()
    (run_dir / "cases.jsonl").write_text("\n".join(json.dumps(r) for r in rows))
    (run_dir / "config.json").write_text("{}")
    (run_dir / "summary.json").write_text("{}")
    csv = tmp_path / "labels.csv"
    assert cli.main(["label", "export", "--run", str(run_dir), "--out", str(csv), "-n", "10"]) \
        == 0
    lines = csv.read_text().splitlines()
    filled = [lines[0]] + [line.replace(",,", ",CORRECT,", 1) if "$1" in line.split(",")[5]
                           else line.replace(",,", ",INCORRECT,", 1) for line in lines[1:]]
    csv.write_text("\n".join(filled) + "\n")
    capsys.readouterr()
    assert cli.main(["label", "import", "--csv", str(csv)]) == 0
    assert json.loads(capsys.readouterr().out)["kappa"] == 1.0
    assert run_cli("calibrate", "--human", str(csv), "--out", str(out)) == 0
    assert json.loads(out.read_text())["source"].startswith("human labels")


def test_fetch_rejects_unknown_source():
    with pytest.raises(SystemExit):
        cli.main(["fetch", "imagenet"])
