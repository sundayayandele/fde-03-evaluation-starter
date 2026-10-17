# Evals

| Path | Content |
| --- | --- |
| `results/<run_id>/` | Published runs: `config.json` and `summary.json` always; `cases.jsonl` only for redistributable golden sets (refusal, PubMedQA, CUAD, red team) |
| `results/gates/` | Gate reports behind the README's release-gate table |
| `results/calibration-reference.json` | Reference-judge calibration on the constructed set |
| `baselines/*.jsonl` | Text-free baselines (case id, answer type, correct, refused, hit@5, citation hit) for the regression check |

Produce them with `make eval-offline` (and `make eval-llm` with a key), then `rag-eval publish runs/<id> [--with-cases]` and `rag-eval baseline runs/<id> --out evals/baselines/<name>.jsonl`. The `release-gate` workflow regenerates the runs on every change and compares against `baselines/financebench-test-advanced-v1.1.0.jsonl`.
