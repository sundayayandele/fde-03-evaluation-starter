# Decision memo: how to decide that a RAG release is better

**Decision:** gate every fde-02 release on a versioned golden set with confidence intervals, a red team with zero tolerance in critical categories, and a calibrated judge. Do not gate on spot checks or a single average. **Date:** 2026-10-16

## Context

The customer asked "is v1.1 better?" A demo answers with a few good examples; the bar is evidence a sponsor can sign. Constraints:

- no paid API in CI;
- FinanceBench may not be redistributed;
- regulated data only to sovereign providers;
- 71 test questions, so averages are noisy (±11 points).

## Options compared

| Option | What it would have said about v1.0.0 → v1.1.0 | Cost | Verdict |
| --- | --- | --- | --- |
| Spot-check 10 questions by hand | "Looks the same": answers on normal questions did not change | 30 min per release | Misses the injection and PII failures entirely |
| One average (accuracy) | 4.2% → 4.2%: "no change" | Free | Blind to safety and refusals |
| LLM judge on every pull request | Prose quality, at a cost per run and with an unvalidated judge | Cents per run, plus a secret in CI | Use for releases, after calibration |
| **Golden sets + intervals + paired regression + red team + calibrated judge** | v1.0.0 fails on injection and PII; rc1 fails on false refusals (7.0%); v1.1.0 passes 10 of 10 | About 1 min of CPU per run, plus a cached 6-min index build | **Chosen** |

## Why

The two failures that mattered were not averages. One followed injection or one leaked name blocks a release however good the averages are. And the first fix created a new failure (false refusals) that only a measured check caught.

## Consequences

- Every fde-02 change runs the `release-gate` workflow, which needs a cached FinanceBench index on the CI runner (about 6 minutes to build when the ingestion code changes).
- Thresholds have owners: changing one needs a CHANGELOG line or an ADR.
- Before AI-written answers ship, the LLM judge must agree with human labels (κ ≥ 0.7).
