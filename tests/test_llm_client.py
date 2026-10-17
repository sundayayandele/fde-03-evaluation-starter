import json

import httpx
import pytest

from rag_eval.llm import LLMClient, Provider

PROVIDER = Provider("mistral", "https://api.example/v1", "TEST_KEY", True,
                    {"default": "small", "embed": "embed-1"},
                    {"small": {"input": 0.1, "output": 0.3}})


def _client(handler, monkeypatch):
    monkeypatch.setenv("TEST_KEY", "secret")
    return LLMClient(PROVIDER, transport=httpx.MockTransport(handler))


def test_complete_returns_usage_and_tool_calls(monkeypatch):
    def handler(request):
        body = json.loads(request.content)
        assert body["model"] == "small" and body["tools"] == [{"x": 1}]
        assert request.headers["authorization"] == "Bearer secret"
        return httpx.Response(200, json={"choices": [{"message": {
            "content": None, "tool_calls": [{"id": "1"}]}}],
            "usage": {"prompt_tokens": 7, "completion_tokens": 2}})
    out = _client(handler, monkeypatch).complete([{"role": "user", "content": "hi"}],
                                                tools=[{"x": 1}])
    assert out == {"content": None, "tool_calls": [{"id": "1"}],
                   "usage": {"prompt_tokens": 7, "completion_tokens": 2}, "model": "small"}


def test_stream_parses_sse(monkeypatch):
    lines = [
        'data: {"choices":[{"delta":{"content":"Hel"}}]}',
        'data: {"choices":[{"delta":{"content":"lo"}}]}',
        'data: {"choices":[{"delta":{}}],"usage":{"prompt_tokens":3,"completion_tokens":2}}',
        "data: [DONE]",
    ]

    def handler(request):
        assert json.loads(request.content)["stream"] is True
        return httpx.Response(200, content="\n\n".join(lines).encode(),
                              headers={"content-type": "text/event-stream"})
    events = list(_client(handler, monkeypatch).stream([{"role": "user", "content": "x"}]))
    assert [e.get("delta") for e in events[:2]] == ["Hel", "lo"]
    assert events[-1] == {"usage": {"prompt_tokens": 3, "completion_tokens": 2}}


def test_embed_batches_and_orders(monkeypatch):
    seen = []

    def handler(request):
        body = json.loads(request.content)
        seen.append(len(body["input"]))
        data = [{"index": i, "embedding": [float(len(t))]} for i, t in enumerate(body["input"])]
        return httpx.Response(200, json={"data": list(reversed(data)),
                                         "usage": {"prompt_tokens": len(body["input"])}})
    vectors, usage = _client(handler, monkeypatch).embed(["a", "bb", "ccc"], batch_size=2)
    assert vectors == [[1.0], [2.0], [3.0]] and seen == [2, 1] and usage == {"prompt_tokens": 3}


def test_cost():
    assert PROVIDER.cost_usd("small", 1_000_000, 1_000_000) == pytest.approx(0.4)
    assert PROVIDER.cost_usd("unknown", 10) is None
