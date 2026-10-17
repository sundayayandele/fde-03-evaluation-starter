from __future__ import annotations

import json

import httpx
import pytest

from rag_eval import targets, tracing


def _sut(captured):
    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        if request.url.path == "/health/ready":
            return httpx.Response(200, json={"status": "ready", "version": "1.1.0"})
        body = json.loads(request.content)
        if "boom" in body["question"]:
            return httpx.Response(500, json={"detail": "error"})
        return httpx.Response(200, json={
            "answer": "$285 million [1]", "refused": False, "mode": "extractive",
            "citations": [{"doc": "A", "page": 5, "ref": 1}],
            "hits": [{"doc": "A", "page": 5, "preview": "capex", "score": 1.0}],
            "usage": {}, "cost_usd": None, "refusal_reason": None})
    return httpx.MockTransport(handler)


def test_http_target_maps_the_contract():
    captured = []
    t = targets.HttpRagTarget("http://sut", transport=_sut(captured))
    r = t.ask("Capex?", docs=["A"], headers={"traceparent": "00-" + "a" * 32 + "-" + "b" * 16
                                             + "-01"}, case_id="ignored")
    assert r.answer == "$285 million [1]" and r.citations == [{"doc": "A", "page": 5}]
    assert r.hits == [{"doc": "A", "page": 5, "preview": "capex"}]
    assert r.raw["mode"] == "extractive" and r.error is None
    sent = json.loads(captured[0].content)
    assert sent == {"question": "Capex?", "docs": ["A"]}
    assert captured[0].headers["traceparent"].startswith("00-aaaa")
    assert t.describe()["ready"]["version"] == "1.1.0"
    failed = t.ask("boom")
    assert failed.answer == "" and failed.error.startswith("HTTPStatusError")
    t.close()


def test_http_target_describe_survives_errors():
    def down(request):
        raise httpx.ConnectError("refused")
    t = targets.HttpRagTarget("http://sut", transport=httpx.MockTransport(down))
    assert t.describe()["ready_error"] == "ConnectError"
    assert t.ask("q").error.startswith("ConnectError")


class FakeProvider:
    name = "fake"

    def model_for(self, role):
        return "fake-model"

    def cost_usd(self, model, prompt, completion):
        return (prompt + completion) * 1e-6


class FakeClient:
    provider = FakeProvider()

    def __init__(self, text):
        self.text, self.messages = text, None

    def complete(self, messages, **kwargs):
        self.messages = messages
        return {"content": self.text, "usage": {"prompt_tokens": 100, "completion_tokens": 20},
                "model": "fake-model"}


def test_prompt_only_and_oracle_targets():
    client = FakeClient("I can't answer that.")
    r = targets.PromptOnlyTarget(client=client).ask("Capex of 3M in FY2018?")
    assert r.refused and r.cost_usd == pytest.approx(120e-6) and r.raw["model"] == "fake-model"
    assert client.messages[1]["content"] == "Capex of 3M in FY2018?"
    oracle = targets.OracleContextTarget(client=FakeClient("$1,577 million"))
    r = oracle.ask("Capex?", context="Purchases of PP&E (1,577)")
    assert r.answer == "$1,577 million" and "only the context" in oracle.client.messages[0][
        "content"]
    assert targets.PromptOnlyTarget(client=client).describe() == {"kind": "prompt-only",
                                                                   "model": "fake-model"}


def test_looks_like_refusal():
    assert targets.looks_like_refusal("I cannot answer that from these documents.")
    assert not targets.looks_like_refusal("Revenue was $5 billion.")


def test_replay_target(tmp_path):
    path = tmp_path / "cases.jsonl"
    path.write_text(json.dumps({"id": "c1", "response": targets.Response("hi").to_dict()}) + "\n")
    t = targets.ReplayTarget(path)
    assert t.ask("anything", case_id="c1").answer == "hi"
    assert t.ask("anything", case_id="c2").error.startswith("no recorded response")
    assert t.describe()["cases"] == 1


def test_case_span_records_attributes_and_propagates_context():
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    exporter = InMemorySpanExporter()
    tracer = tracing.setup("rag-eval-test", exporter=exporter)
    with tracing.case_span(tracer, "fb-1", domain="finance", skipped=None) as (span, headers):
        span.set_attribute("eval.label", "CORRECT")
    spans = exporter.get_finished_spans()
    assert spans and spans[-1].name == "eval.case"
    attrs = dict(spans[-1].attributes)
    assert attrs["eval.case_id"] == "fb-1" and attrs["eval.domain"] == "finance"
    assert "eval.skipped" not in attrs
    trace_id = format(spans[-1].context.trace_id, "032x")
    assert headers["traceparent"].split("-")[1] == trace_id
