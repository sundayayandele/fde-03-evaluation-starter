# ADR-005: Golden sets are versioned, fingerprinted and split by hash

- **Status:** Accepted
- **Date:** 2026-10-16

## Context

A number in a release memo is only comparable to last month's number if both came from the same questions and gold answers. Public benchmarks change upstream, and teams edit golden sets "to fix a typo". Some sources may not be redistributed (FinanceBench), while others can be with attribution (PubMedQA MIT, CUAD CC BY 4.0).

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| A. Download the benchmark at run time, use it as is | Simple | Upstream changes silently move the numbers; no place for our own items |
| B. A dataset registry or eval platform (Langfuse datasets, LangSmith, Braintrust) | UI, history | Another hosted dependency and account; sovereignty questions for regulated data |
| **C. Files in Git: `goldens/<name>/<version>/items.jsonl` + `manifest.json` with an order-independent SHA-256** | Reviewable in pull requests; diffs; works offline; a run records the fingerprint it used | Licences decide what can be committed |

## Decision

**C.**

- Each golden set is built deterministically from a pinned, checksummed source (`rag-eval golden build`).
- `rag-eval golden verify` checks the committed items, and a fresh rebuild from source, against the manifest.
- Any change is a new version, listed with `rag-eval golden diff`.
- The dev/test split is a hash of the item id, so it never moves.
- **FinanceBench** commits only its manifest: learners rebuild the items, and `verify` proves they got the same set. Regression baselines are committed text-free (ids and booleans).

## Consequences

- Golden sets can be reviewed like code, with an owner per set.
- A customer's own golden set fits the same layout, including where its data must stay off GitHub (a private repo, or manifest only).
- We must not commit per-case outputs of non-redistributable sets: `rag-eval publish` copies summaries only unless `--with-cases` is given.
- Revisit when sets grow beyond what Git handles comfortably (tens of MB): move items to object storage and keep the manifest in Git.
