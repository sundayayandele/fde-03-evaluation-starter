# Judge calibration

A judge's verdicts are a measurement instrument. Before its numbers go in a memo, show how often it agrees with a reference you trust, and where it does not.

## Two judges

| | Reference judge | LLM judge |
| --- | --- | --- |
| How | Deterministic rules per answer type (see EVALUATION.md) | Mistral (`strong` role), rubric in `config/rubric.yaml`, JSON verdict, temperature 0 |
| Labels | CORRECT, INCORRECT, REFUSED | Same; an invalid or missing label counts as INCORRECT |
| Strength | Free, fast, reproducible, exact on figures | Paraphrase, partial answers, prose |
| Weakness | Brittle on paraphrase; free text uses token overlap | Costs money; drifts with model versions; needs calibration against people |
| Data | Stays local | Sent to Mistral (sovereign; `regulated_data_allowed: true`) |

## Two calibration sets

**1. Constructed (offline, `rag-eval calibrate`).** For each sampled golden item (40 per domain, seed 7), candidate answers whose label is known by construction:

| Answer type | Candidates (label) |
| --- | --- |
| numeric | gold restated (CORRECT); figure × 1.2 (INCORRECT); figure × 10 (INCORRECT); refusal (REFUSED) |
| yes_no_maybe | verdict restated (CORRECT); verdict flipped (INCORRECT); refusal (REFUSED) |
| free_text | gold (CORRECT); gold with its figure × 1.5 (INCORRECT); another item's answer (INCORRECT); refusal (REFUSED) |
| span | span quoted (CORRECT); "no such clause" (INCORRECT); another clause (INCORRECT) |
| absent | "no such clause" (CORRECT); a refusal (CORRECT); an invented clause (INCORRECT) |

It tests whether a judge applies the rubric. It cannot test judgement: every candidate is easy for a human.

**2. Human (`make label-export`, `rag-eval label import`).** A stratified sample of 40 real judged answers goes to a CSV worksheet. A person fills in `human_label` without looking at the judge's label (hide the column while labelling). The import reports agreement and Cohen's kappa between person and judge. **Kappa against people is the number that gates the LLM release** (gate profile `release`: κ ≥ 0.7, "substantial" on the usual scale).

Cohen's kappa = (p_o − p_e) / (1 − p_e), where p_o is the observed agreement and p_e the agreement expected by chance from each rater's label frequencies. Agreement alone flatters a judge on skewed data: one that always says INCORRECT agrees 90% with a set that is 90% INCORRECT, and has κ = 0.

## Results

Measured 2026-10-16. Constructed set from `financebench/v1`, `pubmedqa/v1` and `cuad/v1`; report: `evals/results/calibration-reference.json`.

> TODO week-17 calibration results: complete this section (see labs/).

**What the first version taught.** Calibration found a judge bug (token overlap cannot see that "$20 billion" became "$30 billion") and a construction bug (a perturbation that is not one). Both would have flattered every system scored with them. Run calibration before trusting a judge, and again whenever the judge, its prompt or its model changes.

## Known limits

- **Free text:** the reference judge cannot grade paraphrase; FinanceBench's 97 free-text items need the LLM judge.
- **Self-preference:** a Mistral judge grading Mistral answers may be lenient to its own style. Compare with a second provider on the human set before relying on it. Use only sovereign providers for regulated data.
- **Drift:** pin the judge model ID in the run config (`judge.model`). Re-calibrate when it changes.
