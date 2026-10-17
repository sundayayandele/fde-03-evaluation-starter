# Week 16: Golden sets and metrics

**Goal:** turn "the demo looked good" into numbers with error bars: versioned golden sets in three domains, and the metrics a customer will ask about.

## Brief

The customer's head of operations asks three questions: how often does the assistant find the right page, how often is the answer right, and how sure are you? She also wants to know whether the answer would change next month if someone "fixed" the test questions. You need golden sets that cannot drift silently, and metrics that carry their own uncertainty.

## Concepts

- Golden sets: versioning, fingerprints, a dev/test split by hash.
- Licences decide what you may commit.
- Answer types: numeric, yes/no/maybe, span, absent, refusal, free text.
- Token F1; citation precision and recall at page level; retrieval hit@k.
- Binomial uncertainty, and why Wilson beats p ± 1.96·SE at 0% and 100%.

## Steps

1. `make goldens`: downloads the pinned FinanceBench, PubMedQA and CUAD files, checks their SHA-256, builds FinanceBench's items locally and verifies every set. Read `golden.py:SOURCES`, then answer: why is FinanceBench's `items.jsonl` in `.gitignore`?
2. `rag-eval golden list`. Open `goldens/cuad/v1/items.jsonl`: what is an `absent` item, and why does legal review care more about those than about spans?
3. Implement `token_f1(prediction, gold)` in `metrics.py` (SQuAD-style, multiset overlap).
4. Implement `citation_scores(citations, evidence)`: page-level precision, recall and hit. An evidence page `None` matches any page of that document.
5. Implement `wilson_interval(successes, n)`.
6. `pytest tests/test_metrics.py -m exercise`.
7. Start fde-02 (`make sut-up CONFIG=basic`) and run `rag-eval run --golden financebench --split test --label mine-basic`. Then `make sut-down`, `make sut-up CONFIG=advanced`, and the same run labelled `mine-advanced`. Compare them with `rag-eval report runs/*mine*`.

## Check

```bash
pytest -m exercise tests/test_metrics.py
rag-eval golden verify
```

## Evidence

- Your basic vs advanced table with intervals.
- One sentence on whether the difference is larger than the noise.
- Your answer to "why is FinanceBench not in Git?"

## Stretch

Add a `v2` of the refusal set with five questions of your own. Show `rag-eval golden diff refusal --version v1 --other v2`, and say which new questions fde-02 fails.
