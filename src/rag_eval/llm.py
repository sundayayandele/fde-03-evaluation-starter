"""Provider-agnostic chat client for OpenAI-compatible endpoints.

Mistral is the default. DeepSeek, OpenAI, Qwen, Kimi and self-hosted vLLM are
switched in through config/providers.yaml, without code changes.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
import yaml


class LLMConfigError(RuntimeError):
    """Raised when the provider configuration is missing or unusable."""


class DataResidencyError(RuntimeError):
    """Raised when regulated data would be sent to a provider not allowed to receive it."""


@dataclass(frozen=True)
class Provider:
    name: str
    base_url: str
    api_key_env: str
    regulated_data_allowed: bool
    models: dict[str, str] = field(default_factory=dict)
    # USD per million tokens, by model: {"model": {"input": x, "output": y}} (assumed prices)
    prices: dict[str, dict[str, float]] = field(default_factory=dict)

    def cost_usd(self, model: str, prompt_tokens: int, completion_tokens: int = 0) -> float | None:
        price = self.prices.get(model)
        if not price:
            return None
        return (prompt_tokens * price.get("input", 0.0)
                + completion_tokens * price.get("output", 0.0)) / 1_000_000

    def model_for(self, role: str) -> str:
        if role not in self.models:
            raise LLMConfigError(f"Provider '{self.name}' has no model for role '{role}'")
        model = self.models[role]
        if model == "PIN_AT_BUILD_TIME":
            raise LLMConfigError(
                f"Model for role '{role}' on provider '{self.name}' is not pinned yet. "
                "Set it in config/providers.yaml and record it in an ADR."
            )
        return model


def load_providers(path: str | Path) -> tuple[str, dict[str, Provider]]:
    path = Path(path)
    if not path.exists():
        raise LLMConfigError(f"Providers file not found: {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    providers = {
        name: Provider(
            name=name,
            base_url=spec["base_url"].rstrip("/"),
            api_key_env=spec["api_key_env"],
            regulated_data_allowed=bool(spec.get("regulated_data_allowed", False)),
            models=dict(spec.get("models", {})),
            prices={k: dict(v) for k, v in (spec.get("prices") or {}).items()},
        )
        for name, spec in (raw.get("providers") or {}).items()
    }
    default = raw.get("default", "mistral")
    if default not in providers:
        raise LLMConfigError(f"Default provider '{default}' is not defined")
    return default, providers


class LLMClient:
    """Minimal chat-completions client. One instance per provider."""

    def __init__(
        self,
        provider: Provider,
        *,
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        api_key = os.getenv(provider.api_key_env, "")
        if not api_key:
            raise LLMConfigError(f"Environment variable {provider.api_key_env} is not set")
        self.provider = provider
        self._http = httpx.Client(
            base_url=provider.base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
            transport=transport,
        )

    def _check(self, contains_regulated_data: bool) -> None:
        if contains_regulated_data and not self.provider.regulated_data_allowed:
            raise DataResidencyError(
                f"Provider '{self.provider.name}' may not receive regulated data. "
                "Use mistral or selfhosted for this request."
            )

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        role: str = "default",
        contains_regulated_data: bool = False,
        **params: Any,
    ) -> str:
        return self.complete(messages, role=role,
                             contains_regulated_data=contains_regulated_data,
                             **params)["content"] or ""

    def complete(self, messages: list[dict], *, role: str = "default",
                 contains_regulated_data: bool = False, **params: Any) -> dict:
        """One chat completion. Returns {"content", "tool_calls", "usage", "model"}."""
        self._check(contains_regulated_data)
        model = self.provider.model_for(role)
        response = self._http.post("/chat/completions",
                                   json={"model": model, "messages": messages, **params})
        response.raise_for_status()
        body = response.json()
        message = body["choices"][0]["message"]
        return {"content": message.get("content"), "tool_calls": message.get("tool_calls") or [],
                "usage": body.get("usage") or {}, "model": model}

    def stream(self, messages: list[dict], *, role: str = "default",
               contains_regulated_data: bool = False, **params: Any) -> Iterator[dict]:
        """Stream a chat completion. Yields {"delta": str} events, then {"usage": {...}}
        (when the provider reports it) as the last event."""
        self._check(contains_regulated_data)
        payload = {"model": self.provider.model_for(role), "messages": messages,
                   "stream": True, **params}
        usage: dict = {}
        with self._http.stream("POST", "/chat/completions", json=payload) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                chunk = json.loads(data)
                if chunk.get("usage"):
                    usage = chunk["usage"]
                for choice in chunk.get("choices", []):
                    delta = (choice.get("delta") or {}).get("content")
                    if delta:
                        yield {"delta": delta}
        yield {"usage": usage}

    def embed(self, texts: list[str], *, role: str = "embed", batch_size: int = 64,
              contains_regulated_data: bool = False) -> tuple[list[list[float]], dict]:
        """Embeddings for texts, in order. Returns (vectors, summed usage)."""
        self._check(contains_regulated_data)
        model = self.provider.model_for(role)
        vectors: list[list[float]] = []
        usage = {"prompt_tokens": 0}
        for start in range(0, len(texts), batch_size):
            response = self._http.post("/embeddings", json={
                "model": model, "input": texts[start:start + batch_size]})
            response.raise_for_status()
            body = response.json()
            vectors.extend(d["embedding"] for d in sorted(body["data"], key=lambda d: d["index"]))
            usage["prompt_tokens"] += (body.get("usage") or {}).get("prompt_tokens", 0)
        return vectors, usage

    def close(self) -> None:
        self._http.close()


def client_for(provider_name: str | None = None, providers_file: str | Path | None = None,
               **kwargs: Any) -> LLMClient:
    from rag_eval.config import get_settings

    settings = get_settings()
    default, providers = load_providers(providers_file or settings.llm_providers_file)
    name = provider_name or settings.llm_provider or default
    if name not in providers:
        raise LLMConfigError(f"Unknown provider '{name}'. Known: {sorted(providers)}")
    return LLMClient(providers[name], timeout=settings.llm_timeout_seconds, **kwargs)
