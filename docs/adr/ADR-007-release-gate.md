# ADR-007: Release gate = thresholds + paired-bootstrap regression + red-team criticals + judge κ

- **Status:** Accepted
- **Date:** 2026-10-16

## Context

"Did it get worse?" has to be answered on every change to fde-02, automatically, without paying for an API, and with the noise of a 71-question benchmark (±11 points per rate). Some failures are not averages: one leaked SSN or one followed injection is a release blocker however good the averages are.

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| A. Absolute thresholds only | Simple | Misses a drop that stays above the threshold |
| B. Compare means with the previous run | Catches drops | Noise: on 71 cases, 1–2 questions swing it |
| **C. Thresholds, plus a paired bootstrap of per-case outcomes against a committed baseline (fail when the drop > `max_drop` or the 95% CI is entirely below 0), plus red-team critical categories at 100%, plus judge κ** | Catches real drops, tolerates noise, encodes "never" rules; runs offline | More moving parts; thresholds are judgement calls and need owners |

## Decision

**C.**

- Profiles live in `config/gate.yaml`: `ci-offline` for every pull request and weekly, `release` for an LLM release candidate.
- `rag-eval gate` exits 1 on any failed check and writes a Markdown report for the CI summary.
- Baselines are text-free files (`evals/baselines/`), so they are safe to commit for any dataset.

## Consequences

- **Measured:** the gate failed v1.0.0 on the red team, and failed v1.1.0-rc1 on false refusals (7.0% > 5%). That rc1 regression was introduced by the fix for the red team. v1.1.0 passed 10 of 10.
- **Two lessons from rc1.** The gate's metrics did not catch the over-masking of figures; reading the masked text did. And extractive accuracy is too low to move.
- **When versions differ on a single case,** the bootstrap interval touches 0, so `max_drop` decides; it is a business tolerance, set with the customer.
- Change a threshold only with a CHANGELOG line or an ADR saying why.
- Revisit `ci-offline` once the LLM evaluation runs: accuracy thresholds belong in `release` only after the LLM judge is calibrated.
