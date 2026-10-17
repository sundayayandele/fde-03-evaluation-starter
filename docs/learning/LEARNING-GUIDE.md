# Learning guide: Phase 3, evaluation (weeks 16–18)

## Objectives

By the end of the phase you can:

1. Build versioned golden sets from public benchmarks and your own items, respecting their licences.
2. Report quality with uncertainty: Wilson intervals for rates, a paired bootstrap for version differences.
3. Grade answers with a rule-based and an LLM judge, and show with kappa how far to trust each.
4. Red-team a RAG system for prompt injection, PII leakage, scope and fabrication, and fix what breaks without breaking something else.
5. Gate releases in CI, and write the memo a customer sponsor signs.

## Weekly plan

| Week | Lab | Build | Evidence |
| --- | --- | --- | --- |
| 16 | [Golden sets and metrics](../../labs/week-16-golden-sets-and-metrics/README.md) | `token_f1`, `citation_scores`, `wilson_interval` | Basic vs advanced table with intervals |
| 17 | [Judges and calibration](../../labs/week-17-judges-and-calibration/README.md) | `build_judge_messages`, `perturb_number`, `cohens_kappa` | Calibration table; 40 human labels |
| 18 | [Red team, gate and release memo](../../labs/week-18-redteam-and-release-gate/README.md) | `detect_pii`, `bootstrap_diff_ci`, `check_gate` | Gate failing on v1.0.0 and passing on your fix; the memo |

## How to use the repos

1. Start from the starter (`fde-03-evaluation-starter`): "Use this template", then clone it next to your fde-02.
2. Work through the labs in order; `make exercises` shows what is left.
3. Fix fde-02 in your own fde-02 repo. Keep its tests green, and add tests for your guardrails.
4. Fill the README results table and `docs/RELEASE-READINESS.md` with your measured numbers.
5. Compare with the reference repo only after you have tried each exercise.

## What a hiring manager will look for

- Intervals on every rate, and the discipline of dev vs test, including when you broke it and said so.
- A judge with a calibration figure, not an unexamined LLM grade.
- A red-team finding, its fix, and the regression the fix caused, caught by your own gate.
- A memo that names residual risks and asks for a decision.
