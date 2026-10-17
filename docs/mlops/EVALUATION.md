# Evaluation methodology

How `rag-eval` turns a system's answers into numbers you can defend in front of a customer.

## Unit of evaluation

A **case** is one golden item sent to the system under test (SUT) as a black box: `POST /api/v1/ask {question, docs?}`. The response gives the answer, its citations (document and page), whether it refused, the retrieved passages, latency and cost. Everything is stored in `runs/<id>/cases.jsonl`, so a run can be re-scored later without calling the SUT again (`--replay`): new metrics, a new judge, a new gate.

## Golden sets

| Set | Domain | Items (dev / test) | Answer types | Evidence |
| --- | --- | --- | --- | --- |
| `financebench/v1` | Finance: 10-K, 10-Q, 8-K, earnings | 150 (79 / 71) | numeric 53, free_text 97 | Page (0-based in the source, converted to 1-based) |
| `pubmedqa/v1` | Health: abstracts | 200 (97 / 103), stratified sample of the 1,000 expert-labelled | yes_no_maybe | The abstract (any page) |
| `cuad/v1` | Legal: commercial contracts | 200 (106 / 94): 20 test contracts × 10 categories | span 84, absent 116 | Pages that contain the span |
| `refusal/v1` | Finance scope | 30 (13 / 17), hand-written | refusal | None: the right answer is to decline |

The **split** is a hash of the item id (`split_of`), so it never changes when a set is rebuilt. Tune on dev, report on test, and say so when that discipline is broken (see the README caveat about v1.1.0).

**Versioning.** `goldens/<name>/<version>/manifest.json` holds counts and an order-independent SHA-256 of the items (`items_sha256`). `rag-eval golden verify` checks the committed items against it and, when the raw source is present, rebuilds from source and checks again. Any change to an item is a new version (`v2`), and `golden diff` lists what was added, removed or changed. Runs record the fingerprint they used, so two runs are comparable only when it matches.

## Metrics

| Metric | Definition | Notes |
| --- | --- | --- |
| Accuracy | Share of cases the judge labels CORRECT | By answer type and domain in `summary.json` |
| Retrieval hit@5 | A top-5 retrieved passage is on a gold evidence page | Evidence page `None` matches any page of the document |
| Cites evidence | At least one citation matches gold evidence | Plus citation precision (matched / cited) |
| False refusal | Answerable cases the SUT declined | numeric, free_text, yes_no_maybe, span |
| Correct abstention | Unanswerable cases (absent, refusal) handled correctly | "No such clause" counts for absent |
| Latency | p50 and p95 of client-side time, including HTTP | Warm the SUT first (`scripts/sut.py` does) |
| Cost | Sum and mean of the SUT's reported `cost_usd` | At the assumed prices in `config/providers.yaml` |

**Answer correctness (reference judge):**

| Answer type | Correct when |
| --- | --- |
| numeric | The first figure matches within 1%. Unit words are applied, and a scale of 10³ / 10⁶ / 10⁹ is tolerated when only one side states a unit |
| yes_no_maybe | The answer opens with (or states) the gold verdict |
| span | Token F1 ≥ 0.5 against the gold span or an alternative |
| absent | The answer says the clause is missing, or declines |
| free_text | Token F1 ≥ 0.5 **and** every figure in the gold appears in the answer |
| refusal | The SUT declined |

## Uncertainty

- **One rate:** a 95% **Wilson** interval. It behaves at 0% and 100%, where p ± 1.96·SE gives nonsense. With n = 71, an interval spans about ±11 points around 50%.
- **Two versions on the same cases:** a **paired bootstrap** of the difference (2,000 resamples, fixed seed). Pairing removes the between-question variance that dominates small benchmarks. The gate fails when the observed drop exceeds `max_drop`, or when the whole interval is below zero.
- **What the bootstrap cannot do:** when versions differ on a single case, every resample moves the same way and the interval touches 0. Small changes are therefore decided by `max_drop`, a business tolerance, not by the interval.

## Configurations compared

`config/sut.yaml` names every SUT configuration, so a run label is enough to reproduce it:

| Name | Retrieval | Answers |
| --- | --- | --- |
| `basic` | BM25 over all filings | Extractive |
| `basic-routed` | + company and year routing | Extractive |
| `advanced` | Hybrid BM25 + LSA, query rewrite, lexical rerank, routing | Extractive |
| `advanced-llm` | Same | Mistral, with the ratio tool |
| `advanced-open` | Same; finance scope guard off | Extractive (PubMedQA, CUAD) |
| prompt-only | No retrieval | `PromptOnlyTarget`: the model alone |

`scripts/sut.py` refuses to start a run when the SUT reports a different retrieval mode than the configuration asks for. fde-02 falls back to BM25 when the index lacks dense vectors, and a run labelled "hybrid" once measured BM25 that way.

## Tracing

Each case is an OpenTelemetry span `eval.case` with the case id, domain, answer type, label and latency. The runner injects the W3C `traceparent` header into the request; fde-02 v1.1 echoes the trace id as `X-Trace-Id`. Set `OTEL_EXPORTER_OTLP_ENDPOINT` to send spans to Jaeger (Compose `observability` profile) or to Langfuse's OTLP endpoint. See ADR-008.

## Threats to validity

- **Contamination:** FinanceBench, PubMedQA and CUAD are public, and a hosted LLM may have seen them. The prompt-only baseline measures how much the model knows without documents. Treat a high prompt-only score as a warning about the benchmark, not as praise for the model.
- **Tuning on the test half:** fde-02's glossary and aliases were written while looking at FinanceBench failures (fde-02 README). v1.1.0's scope fixes were found on the test half.
- **Same author for attack and defence:** the red team and the guardrails were written by one person. Rotate the red team, and add attacks you did not design the defences for.
- **Extractive answers floor the accuracy numbers.** Answer accuracy says little about the LLM product until `make eval-llm` runs.
