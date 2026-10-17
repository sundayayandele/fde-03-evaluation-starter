"""OpenTelemetry tracing for evaluation runs.

One trace per run, one span per case (`eval.case`) with the question id, answer type, label,
latency and cost as attributes. The W3C `traceparent` header goes to the system under test,
so an instrumented service (fde-02 v1.1 logs it) joins the same trace.

Off by default. Set OTEL_EXPORTER_OTLP_ENDPOINT (e.g. http://localhost:4318 for the
collector in compose, or Langfuse's OTLP endpoint https://cloud.langfuse.com/api/public/otel
with OTEL_EXPORTER_OTLP_HEADERS="Authorization=Basic <base64 public:secret>").
"""

from __future__ import annotations

import os
from contextlib import contextmanager

from opentelemetry import trace
from opentelemetry.propagate import inject

_configured = False


def setup(service_name: str = "rag-eval", endpoint: str | None = None,
          exporter=None) -> trace.Tracer:
    """Configure a tracer provider once. With no endpoint and no exporter, spans are no-ops."""
    global _configured
    endpoint = endpoint or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not _configured and (endpoint or exporter is not None):
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor

        provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
        if exporter is None:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            exporter = OTLPSpanExporter(endpoint=f"{endpoint.rstrip('/')}/v1/traces")
            provider.add_span_processor(BatchSpanProcessor(exporter))
        else:
            provider.add_span_processor(SimpleSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        _configured = True
    return trace.get_tracer("rag_eval")


@contextmanager
def case_span(tracer: trace.Tracer, case_id: str, **attributes):
    """A span for one case; yields (span, headers carrying traceparent)."""
    with tracer.start_as_current_span("eval.case") as span:
        span.set_attribute("eval.case_id", case_id)
        for key, value in attributes.items():
            if value is not None:
                span.set_attribute(f"eval.{key}", value)
        headers: dict[str, str] = {}
        inject(headers)
        yield span, headers


def shutdown() -> None:
    provider = trace.get_tracer_provider()
    if hasattr(provider, "shutdown"):
        provider.shutdown()
