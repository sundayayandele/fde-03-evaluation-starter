# ADR-004: Evaluate the system under test as a black box over HTTP

- **Status:** Accepted
- **Date:** 2026-10-16
- **Deciders:** forward deployed engineer

## Context

The harness must evaluate fde-02 and, at a customer, systems we did not write: a vendor's RAG product, another team's service, a new model behind the same API. The customer's acceptance tests run against what is deployed, not against a library in a notebook. fde-02 already exposes `POST /api/v1/ask` with answer, citations, refusal flag, retrieved passages, latency and cost.

## Options considered

| Option | Pros | Cons | Cost / effort |
| --- | --- | --- | --- |
| A. Import fde-02 and call `Assistant.ask()` in-process | Fast; access to internals | Tests code, not the deployed service; couples the harness to one codebase and its dependencies | Low |
| **B. HTTP black box against the `/api/v1/ask` contract** | Works for any compatible service and any deployment (laptop, Kubernetes, cloud); measures real latency; versions run side by side | Needs the service up; only sees what the API returns | Medium |
| C. Log replay only | No live calls | Cannot test a new version before release | Low |

## Decision

**B**, with **C** as a complement (`ReplayTarget` re-scores recorded runs). `scripts/sut.py` starts any checkout of fde-02 with a named configuration (`config/sut.yaml`), so v1.0.0 and v1.1.0 run from their own source against the same golden sets.

## Consequences

- The contract is the interface: answer, `citations[{doc, page}]`, `refused`, `hits[{doc, page, preview}]`, `cost_usd`. A service that omits `hits` still gets accuracy, citation and refusal metrics, but no retrieval hit@5.
- Latency includes HTTP and queueing: warm the service first (`sut.py` sends two warm-up questions after it reports ready; cold runs measured p95 8.3 s instead of 0.4 s).
- `sut.py` refuses a run when the service reports a different retrieval mode than requested, after a "hybrid" run silently measured BM25.
- Revisit if a customer's system has no HTTP API: wrap it in an adapter target, not a fork of the runner.
