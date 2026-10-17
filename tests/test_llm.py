from pathlib import Path

import httpx
import pytest

from rag_eval.llm import (
    DataResidencyError,
    LLMClient,
    LLMConfigError,
    Provider,
    load_providers,
)

ROOT = Path(__file__).resolve().parent.parent


def test_providers_file_lists_all_five_vendors():
    default, providers = load_providers(ROOT / "config" / "providers.yaml")
    assert default == "mistral"
    assert {"mistral", "openai", "deepseek", "qwen", "kimi", "selfhosted"} <= set(providers)
    assert providers["mistral"].regulated_data_allowed
    assert not providers["deepseek"].regulated_data_allowed


def _provider(**overrides):
    base = dict(name="test", base_url="https://llm.test/v1", api_key_env="TEST_LLM_KEY",
                regulated_data_allowed=False, models={"default": "m-small"})
    base.update(overrides)
    return Provider(**base)


def _transport(captured):
    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"choices": [{"message": {"content": "hi"}}]})
    return httpx.MockTransport(handler)


def test_chat_sends_openai_compatible_payload(monkeypatch):
    monkeypatch.setenv("TEST_LLM_KEY", "secret")
    captured = []
    client = LLMClient(_provider(), transport=_transport(captured))
    assert client.chat([{"role": "user", "content": "hello"}]) == "hi"
    request = captured[0]
    assert request.url.path == "/v1/chat/completions"
    assert request.headers["authorization"] == "Bearer secret"
    assert b'"model":"m-small"' in request.content


def test_regulated_data_blocked_for_non_sovereign_provider(monkeypatch):
    monkeypatch.setenv("TEST_LLM_KEY", "secret")
    client = LLMClient(_provider(), transport=_transport([]))
    with pytest.raises(DataResidencyError):
        client.chat([{"role": "user", "content": "x"}], contains_regulated_data=True)


def test_unpinned_model_is_rejected(monkeypatch):
    monkeypatch.setenv("TEST_LLM_KEY", "secret")
    client = LLMClient(_provider(models={"default": "PIN_AT_BUILD_TIME"}),
                       transport=_transport([]))
    with pytest.raises(LLMConfigError, match="not pinned"):
        client.chat([{"role": "user", "content": "x"}])


def test_missing_api_key(monkeypatch):
    monkeypatch.delenv("TEST_LLM_KEY", raising=False)
    with pytest.raises(LLMConfigError, match="TEST_LLM_KEY"):
        LLMClient(_provider())
