# Model card: the judges

This repo trains no model. Its models are **judges**, instruments that turn answers into labels. This card documents them as a measurement system.

| | Reference judge | LLM judge |
| --- | --- | --- |
| Version | `rag_eval` 1.0.0, rules in `metrics.is_correct` | `mistral-large-latest` (provider `mistral`, role `strong`), rubric `2026-10-16` |
| Labels | CORRECT, INCORRECT, REFUSED | Same; invalid output becomes INCORRECT |
| Intended use | CI gates; numeric, yes/no/maybe, span, absent and refusal answers | Prose answers (FinanceBench free text) and paraphrase, in release evaluations |
| Out of scope | Grading prose quality, completeness or tone | Regulated data on a non-sovereign provider; grading its own provider's answers without a cross-check |
| Calibration | 390 constructed cases: agreement 1.000 [0.99, 1.00], κ = 1.00 (first version 0.949, two bugs fixed) | Pending: constructed set and 40 human labels (`make eval-llm label-export label-import`) |
| Known limits | Token overlap on free text; the first figure only for numeric answers | Possible leniency and self-preference; drifts with model updates |
| Owner | Repo owner | Repo owner; re-calibrate when the model or rubric changes |

Details: [JUDGE-CALIBRATION.md](../JUDGE-CALIBRATION.md) · method: [EVALUATION.md](EVALUATION.md).
