"""Markdown comparison of runs: the table that goes into README results and the memo."""

from __future__ import annotations


def _fmt_rate(block: dict | None) -> str:
    if not block or block.get("rate") is None:
        return "—"
    lo, hi = block["ci95"]
    return f"{block['rate']:.3f} [{lo:.2f}, {hi:.2f}]"


def compare_table(runs: list[dict]) -> str:
    header = ("| Run | Golden (split, n) | Accuracy | Retrieval hit@5 | Cites evidence | "
              "False refusal | Correct abstention | p50 / p95 ms | Cost / q |")
    lines = [header, "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for run in runs:
        c, s = run["config"], run["summary"]
        g = c["golden"]
        cost = s["cost_usd"]["per_question"]
        lines.append(
            f"| {c.get('label') or c['run_id']} | {g['name']}/{g['version']} "
            f"({g['split']}, {s['cases']}) | {_fmt_rate(s['accuracy'])} | "
            f"{_fmt_rate(s.get('retrieval_hit_at_5'))} | {_fmt_rate(s.get('citation_hit'))} | "
            f"{_fmt_rate(s.get('false_refusal'))} | {_fmt_rate(s.get('correct_abstention'))} | "
            f"{s['latency_ms']['p50']:.0f} / {s['latency_ms']['p95']:.0f} | "
            f"{'—' if cost is None else f'${cost:.5f}'} |")
    lines.append("")
    lines.append("Rates with 95% Wilson intervals. Judge: "
                 + ", ".join(sorted({r['config']['judge']['name'] for r in runs})) + ".")
    return "\n".join(lines)
