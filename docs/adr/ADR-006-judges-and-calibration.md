# ADR-006: A deterministic reference judge and a calibrated LLM judge

- **Status:** Accepted
- **Date:** 2026-10-16

## Context

Exact match fails on almost every RAG answer ("$1,577 million" vs "USD 1.577 billion in FY2018"). LLM judges handle paraphrase but cost money, change with model versions, and are known to be lenient or biased. A customer will ask why they should believe the judge.

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| A. Human grading only | The ground truth | Slow and expensive; does not run in CI |
| B. LLM judge only | Handles prose | Unverified instrument; costs on every pull request; no offline CI |
| **C. Reference judge (rules per answer type) for CI, an LLM judge with a rubric for prose, both calibrated: constructed cases offline, human labels for the LLM judge** | CI runs free and offline; the LLM judge's numbers come with an agreement figure | Two judges to maintain; human labelling is a recurring task |

## Decision

**C.**

- **Rubric:** `config/rubric.yaml`, versioned, with criteria per answer type and a definition of REFUSED.
- **LLM judge:** JSON mode, temperature 0, on the `strong` role (Mistral Large, sovereign). Any invalid label counts as INCORRECT, never CORRECT.
- **Calibration:** reported as agreement (Wilson CI), Cohen's κ, per-label precision and recall, a confusion matrix and the list of disagreements.
- **Release thresholds:** the reference judge needs κ ≥ 0.8 on the constructed set (`ci-offline`). The LLM judge needs κ ≥ 0.7 against human labels (`release`).

## Consequences

- Calibration found two bugs in the first reference judge (94.9% → 100% agreement): bugs that would have flattered every system scored with it.
- The constructed set tests rule-following only. Human labels are required before an LLM-judged number goes in a memo.
- Pin the judge model in run configs; re-calibrate when it changes.
- Revisit with a second-provider judge if the Mistral judge shows self-preference on the human set.
