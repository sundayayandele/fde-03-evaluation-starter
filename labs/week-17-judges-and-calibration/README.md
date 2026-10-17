# Week 17: Judges and calibration

**Goal:** grade answers that exact match cannot, and prove that your grader agrees with the truth before anyone reads its numbers.

## Brief

FinanceBench answers look like "$1,577 million", "USD 1.577 billion" or "about 1.6bn in FY2018". Most of its questions want prose. The customer's risk team asks: "Your AI grades your AI. Why should we believe it?" Your answer is a calibration report: agreement and kappa against labels you trust, with the disagreements listed.

## Concepts

- A rule-based reference judge per answer type.
- A rubric-based LLM judge: JSON mode, temperature 0, invalid output counted as INCORRECT.
- Constructed calibration sets, where labels are known by construction.
- Human labels; agreement vs Cohen's kappa (chance correction).
- Judge drift, self-preference, sovereignty of the judge's data.

## Steps

1. Read `config/rubric.yaml` and `judge.py`. Implement `build_judge_messages(rubric, question, gold, answer, answer_type)`.
2. Implement `perturb_number(text, factor)` in `calibration.py`. It multiplies the first non-year figure and keeps its format.
3. Implement `cohens_kappa(a, b)` in `metrics.py`.
4. `pytest -m exercise tests/test_judge_calibration.py tests/test_metrics.py`.
5. `rag-eval calibrate`. Read the disagreements, if any. The reference solution's first version scored 94.9%: find in `docs/JUDGE-CALIBRATION.md` which two bugs that exposed, and why each would have flattered every system scored with it.
6. With a key: `rag-eval calibrate --judge llm --out runs/calibration-llm.json`. Compare kappa per answer type with the reference judge.
7. Export 40 answers (`make label-export` after an LLM run, or `rag-eval label export --run runs/<any run>`). Label them yourself without looking at `judge_label` (hide the column), then `make label-import`.

## Check

```bash
pytest -m exercise tests/test_judge_calibration.py
rag-eval calibrate      # agreement and kappa printed
```

## Evidence

- Your calibration table.
- Three disagreements, with whether you side with the judge or with the label.
- A one-paragraph answer to the risk team.

## Stretch

Run the LLM judge with a second provider on your 40 labels (`LLM_PROVIDER=openai`, public data only). Does the Mistral judge favour Mistral answers?
