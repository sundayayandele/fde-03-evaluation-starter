# ADR-008: OpenTelemetry for evaluation traces; Langfuse through its OTLP endpoint

- **Status:** Accepted
- **Date:** 2026-10-16

## Context

When a case fails, an engineer needs to see that request: question, retrieved passages, answer, timings, and the service's own logs for it. The blueprint names Langfuse or OpenTelemetry. Customers differ: some run Datadog, Grafana Tempo or Jaeger; some forbid sending prompts to a SaaS.

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| A. Langfuse SDK | LLM-specific UI: prompts, scores, datasets | Vendor SDK in the harness; a hosted service unless self-hosted |
| **B. OpenTelemetry API + OTLP exporter** | Vendor-neutral; any backend (Jaeger locally, Tempo, Datadog, Langfuse's OTLP endpoint); W3C `traceparent` joins the harness span to the service's | Less LLM-specific UI unless the backend adds it |
| C. Logs only | Nothing to run | No correlation across services |

## Decision

**B.**

- **Spans:** one `eval.case` span per case, with id, domain, answer type, label and latency attributes.
- **Propagation:** the runner sends `traceparent` to the system under test; fde-02 v1.1 echoes the trace id as `X-Trace-Id`.
- **Off by default.** `OTEL_EXPORTER_OTLP_ENDPOINT` turns it on: Jaeger in the Compose `observability` profile, or `https://cloud.langfuse.com/api/public/otel` with `OTEL_EXPORTER_OTLP_HEADERS` for Langfuse.
- **No question or answer text goes into span attributes,** so traces are safe for regulated data. The text stays in `cases.jsonl`, joined by case id.

## Consequences

- Instrumenting fde-02 itself with OpenTelemetry (retrieval, rerank and generation spans) is a later step; its spans would nest under the evaluation's through `traceparent`.
- Aggregate quality goes to Prometheus and Grafana from run files (`eval_*` gauges), not from traces.
- Revisit if a customer standardises on Langfuse's datasets and scores: add an exporter for run summaries, keeping files as the source of truth.
