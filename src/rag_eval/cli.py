"""`rag-eval`: golden sets, runs, judge calibration, red team, release gate and reports."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from rag_eval import golden
from rag_eval.config import get_settings

GOLDENS = ["financebench", "pubmedqa", "cuad", "refusal"]


def _p(text: str) -> None:
    sys.stdout.write(text + "\n")


def cmd_fetch(args) -> int:
    raw = Path(args.data_dir) / "raw"
    unknown = set(args.sources) - set(golden.SOURCES)
    if unknown:
        raise SystemExit(f"unknown source(s): {', '.join(sorted(unknown))}")
    for name in args.sources or list(golden.SOURCES):
        _p(f"{name}: {golden.fetch(name, raw)}")
    return 0


def cmd_golden(args) -> int:
    root, raw = Path(args.goldens_dir), Path(args.data_dir) / "raw"
    if args.action == "build":
        builder = golden.BUILDERS[args.name]
        items = builder(raw) if args.name in golden.SOURCES else builder()
        if (root / args.name / args.version).exists() and not args.force:
            new = golden.diff(golden.load(root, args.name, args.version), items)
            _p(json.dumps(new, indent=2))
            _p("exists; pass --force to overwrite, or build a new --version")
            return 1
        _p(f"wrote {golden.save(items, root, args.name, args.version)} ({len(items)} items)")
        return 0
    if args.action == "verify":
        ok_all = True
        for name in [args.name] if args.name else GOLDENS:
            ok, message = golden.verify(root, name, args.version, raw_dir=raw)
            ok_all &= ok
            _p(("ok   " if ok else "FAIL ") + message)
        return 0 if ok_all else 1
    if args.action == "diff":
        _p(json.dumps(golden.diff(golden.load(root, args.name, args.version),
                                  golden.load(root, args.name, args.other)), indent=2))
        return 0
    for name in GOLDENS:                               # list
        manifest = root / name
        for v in sorted(p.name for p in manifest.iterdir()) if manifest.exists() else []:
            m = json.loads((manifest / v / "manifest.json").read_text())
            _p(f"{name}/{v}: {m['count']} items {m['by_answer_type']} {m['by_split']}")
    return 0


def cmd_corpus(args) -> int:
    from rag_eval import redteam

    out = Path(args.out or Path(args.data_dir) / "corpus" / args.name)
    if args.name == "redteam":
        paths = redteam.build_docs(out)
    else:
        items = golden.load(Path(args.goldens_dir), args.name, args.version)
        paths = golden.build_corpus(args.name, Path(args.data_dir) / "raw", out, items)
    _p(f"wrote {len(paths)} PDFs and doc_info.json to {out}")
    return 0


def _target(args):
    from rag_eval import targets

    if args.replay:
        return targets.ReplayTarget(Path(args.replay) / "cases.jsonl")
    if args.prompt_only:
        return targets.PromptOnlyTarget()
    s = get_settings()
    return targets.HttpRagTarget(args.target or s.target_url, timeout=s.target_timeout_seconds)


def _judge(args):
    from rag_eval.judge import get_judge

    return get_judge(args.judge, role=get_settings().judge_role) if args.judge == "llm" \
        else get_judge("reference")


def cmd_run(args) -> int:
    from rag_eval import runner

    root = Path(args.goldens_dir)
    items = golden.load(root, args.golden, args.version, args.split)
    if args.limit:
        items = items[:args.limit]
    manifest = json.loads((root / args.golden / args.version / "manifest.json").read_text())
    meta = {"name": args.golden, "version": args.version, "split": args.split,
            "items_sha256": manifest["items_sha256"], "cases": len(items)}
    out = runner.run(_target(args), items, _judge(args), runs_dir=Path(args.runs_dir),
                     golden=meta, label=args.label, scope=args.scope,
                     concurrency=args.concurrency, run_id=args.run_id)
    summary = json.loads((out / "summary.json").read_text())
    _p(f"run {out}")
    _p(json.dumps({k: summary[k] for k in ("cases", "errors", "accuracy", "false_refusal",
                                            "retrieval_hit_at_5", "citation_hit", "latency_ms")},
                  indent=2))
    return 0


def cmd_calibrate(args) -> int:
    from rag_eval import calibration, judge
    from rag_eval.targets import looks_like_refusal

    j = _judge(args)
    if args.human:
        rows = calibration.import_labels(Path(args.human))
        cases = [{"id": r["id"], "question": r["question"], "gold": r["gold"],
                  "answer": r["answer"], "answer_type": r["answer_type"],
                  "refused": looks_like_refusal(r["answer"]),
                  "alternatives": [], "label": r["human_label"], "kind": "human"}
                 for r in rows]
        source = f"human labels: {args.human}"
    else:
        items, used = [], []
        for name in ["financebench", "pubmedqa", "cuad"]:
            if (Path(args.goldens_dir) / name / "v1" / "items.jsonl").exists():
                items += golden.load(Path(args.goldens_dir), name, "v1")
                used.append(name)
            else:                                   # FinanceBench before `make goldens`
                sys.stderr.write(f"calibrate: {name}/v1 items not built; skipped\n")
        cases = calibration.constructed_set(items, per_domain=args.per_domain)
        source = f"constructed perturbations of {', '.join(used)} v1"
    result = judge.calibrate(j, cases) | {"source": source, "judge_config": j.describe()}
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(result, indent=2))
    _p(json.dumps({k: v for k, v in result.items() if k != "disagreements"}, indent=2))
    return 0


def cmd_label(args) -> int:
    from rag_eval import calibration, runner

    if args.action == "export":
        rows = runner.load_run(Path(args.run))["cases"]
        _p(f"wrote {calibration.export_for_labelling(rows, Path(args.out), n=args.n)}")
        return 0
    from rag_eval.metrics import cohens_kappa
    rows = calibration.import_labels(Path(args.csv))
    human, judge_labels = [r["human_label"] for r in rows], [r["judge_label"] for r in rows]
    agree = sum(h == j for h, j in zip(human, judge_labels, strict=True))
    _p(json.dumps({"labelled": len(rows), "agreement": round(agree / len(rows), 4),
                   "kappa": round(cohens_kappa(human, judge_labels), 4)}, indent=2))
    return 0


def cmd_redteam(args) -> int:
    from rag_eval import redteam

    suite = redteam.load_suite(Path(args.suite))
    target = _target(args)
    results = redteam.run_suite(target, suite)
    summary = redteam.summarise(results) | {"suite_version": suite.get("suite_version"),
                                            "target": target.describe()}
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "redteam.json").write_text(json.dumps(summary, indent=2))
    with (out / "redteam-cases.jsonl").open("w", encoding="utf-8") as handle:
        for r in results:
            handle.write(json.dumps(r.to_dict()) + "\n")
    for cat, res in summary["categories"].items():
        _p(f"{cat:20s} {res['passed']}/{res['cases']}  fail: {', '.join(res['failures'])}")
    _p(f"overall {summary['passed']}/{summary['cases']} -> {out / 'redteam.json'}")
    return 0


def cmd_gate(args) -> int:
    from rag_eval import gate, runner

    cfg = gate.load_gate(Path(args.config), args.profile)
    current = runner.load_run(Path(args.run))
    baseline = runner.load_rows(Path(args.baseline)) if args.baseline else None
    rt = json.loads(Path(args.redteam).read_text()) if args.redteam else None
    cal = json.loads(Path(args.calibration).read_text()) if args.calibration else None
    checks = gate.check_gate(cfg, current["summary"], current_rows=current["cases"],
                             baseline_rows=baseline, redteam=rt, calibration=cal)
    report = gate.render(checks)
    _p(report)
    if args.out:
        Path(args.out).write_text(report + "\n")
    return 0 if all(c.passed for c in checks) else 1


def cmd_baseline(args) -> int:
    from rag_eval import runner

    _p(f"wrote {runner.save_baseline(Path(args.run), Path(args.out))}")
    return 0


def cmd_publish(args) -> int:
    """Copy a run's config and summary (no per-case text) to evals/results/<run_id>/."""
    import shutil

    src = Path(args.run)
    dest = Path(args.out) / src.name
    dest.mkdir(parents=True, exist_ok=True)
    for name in ("config.json", "summary.json", "redteam.json"):
        if (src / name).exists():
            shutil.copy2(src / name, dest / name)
    if args.with_cases:
        shutil.copy2(src / ("cases.jsonl" if (src / "cases.jsonl").exists()
                            else "redteam-cases.jsonl"), dest)
    _p(f"published {src} -> {dest}")
    return 0


def cmd_report(args) -> int:
    from rag_eval import report, runner

    runs = [runner.load_run(Path(r)) for r in args.runs]
    text = report.compare_table(runs)
    _p(text)
    if args.out:
        Path(args.out).write_text(text + "\n")
    return 0


def build_parser() -> argparse.ArgumentParser:
    s = get_settings()
    p = argparse.ArgumentParser(prog="rag-eval", description=__doc__)
    p.add_argument("--data-dir", default=s.data_dir)
    p.add_argument("--goldens-dir", default=s.goldens_dir)
    p.add_argument("--runs-dir", default=s.runs_dir)
    sub = p.add_subparsers(dest="command", required=True)

    f = sub.add_parser("fetch", help="download pinned raw sources (checksums verified)")
    f.add_argument("sources", nargs="*", help=f"any of {', '.join(golden.SOURCES)} (default all)")
    f.set_defaults(fn=cmd_fetch)

    g = sub.add_parser("golden", help="build, verify, diff or list golden sets")
    g.add_argument("action", choices=["build", "verify", "diff", "list"])
    g.add_argument("name", nargs="?", choices=GOLDENS)
    g.add_argument("--version", default="v1")
    g.add_argument("--other", default="v2", help="second version for diff")
    g.add_argument("--force", action="store_true")
    g.set_defaults(fn=cmd_golden)

    c = sub.add_parser("corpus", help="write PDFs for the system under test to ingest")
    c.add_argument("name", choices=["pubmedqa", "cuad", "redteam"])
    c.add_argument("--version", default="v1")
    c.add_argument("--out")
    c.set_defaults(fn=cmd_corpus)

    def target_args(sp):
        sp.add_argument("--target", help=f"base URL (default {s.target_url})")
        sp.add_argument("--prompt-only", action="store_true", help="LLM without retrieval")
        sp.add_argument("--replay", help="re-score a recorded run directory")

    r = sub.add_parser("run", help="evaluate a golden set against a target")
    r.add_argument("--golden", required=True, choices=GOLDENS)
    r.add_argument("--version", default="v1")
    r.add_argument("--split", default="test", choices=["all", "dev", "test"])
    r.add_argument("--scope", default="routed", choices=["routed", "doc"],
                   help="doc: pass the gold evidence documents to the target")
    r.add_argument("--judge", default="reference", choices=["reference", "llm"])
    r.add_argument("--limit", type=int)
    r.add_argument("--label", default="")
    r.add_argument("--run-id")
    r.add_argument("--concurrency", type=int, default=s.concurrency)
    target_args(r)
    r.set_defaults(fn=cmd_run)

    ca = sub.add_parser("calibrate", help="judge agreement with labelled cases")
    ca.add_argument("--judge", default="reference", choices=["reference", "llm"])
    ca.add_argument("--human", help="CSV with human_label filled in (else: constructed set)")
    ca.add_argument("--per-domain", type=int, default=40)
    ca.add_argument("--out")
    ca.set_defaults(fn=cmd_calibrate)

    lb = sub.add_parser("label", help="export run answers for human labelling, import labels")
    lb.add_argument("action", choices=["export", "import"])
    lb.add_argument("--run", help="run directory (export)")
    lb.add_argument("--csv", help="labelled CSV (import)")
    lb.add_argument("--out", default="labels.csv")
    lb.add_argument("-n", type=int, default=40)
    lb.set_defaults(fn=cmd_label)

    rt = sub.add_parser("redteam", help="run the red-team suite against a target")
    rt.add_argument("--suite", default="config/redteam.yaml")
    rt.add_argument("--out", default="runs/redteam")
    target_args(rt)
    rt.set_defaults(fn=cmd_redteam)

    gt = sub.add_parser("gate", help="release gate; exit 1 on any failed check")
    gt.add_argument("--run", required=True)
    gt.add_argument("--baseline", help="run directory or baseline .jsonl")
    gt.add_argument("--redteam", help="redteam.json")
    gt.add_argument("--calibration", help="calibration JSON")
    gt.add_argument("--profile", default="ci-offline")
    gt.add_argument("--config", default="config/gate.yaml")
    gt.add_argument("--out")
    gt.set_defaults(fn=cmd_gate)

    bl = sub.add_parser("baseline", help="save a text-free baseline (ids + outcomes) of a run")
    bl.add_argument("run")
    bl.add_argument("--out", required=True)
    bl.set_defaults(fn=cmd_baseline)

    pb = sub.add_parser("publish", help="copy a run's config and summary to evals/results")
    pb.add_argument("run")
    pb.add_argument("--out", default="evals/results")
    pb.add_argument("--with-cases", action="store_true",
                    help="also copy per-case text (only for redistributable datasets)")
    pb.set_defaults(fn=cmd_publish)

    rp = sub.add_parser("report", help="compare runs as a Markdown table")
    rp.add_argument("runs", nargs="+")
    rp.add_argument("--out")
    rp.set_defaults(fn=cmd_report)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "label" and args.action == "export" and not args.run:
        raise SystemExit("label export needs --run")
    if args.command == "label" and args.action == "import" and not args.csv:
        raise SystemExit("label import needs --csv")
    if args.command == "golden" and args.action in {"build", "diff"} and not args.name:
        raise SystemExit(f"golden {args.action} needs a name")
    return args.fn(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
