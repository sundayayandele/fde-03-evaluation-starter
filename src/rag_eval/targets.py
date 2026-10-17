"""Systems under test. Every target turns a question into a `Response` the metrics can score.

- HttpRagTarget:   any service with fde-02's `POST /api/v1/ask` contract (black box).
- PromptOnlyTarget: an LLM with no retrieval (the "prompt-only" baseline).
- OracleContextTarget: an LLM given the gold evidence text (an upper bound for answer quality).
- ReplayTarget:    answers recorded earlier, so evaluations can be re-scored offline.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

import httpx

REFUSAL_MARKERS = ("can't answer", "cannot answer", "not able to answer", "unable to answer",
                   "no information", "not contain", "don't have enough", "do not have enough")


@dataclass
class Response:
    answer: str
    citations: list[dict] = field(default_factory=list)   # [{"doc", "page"}]
    hits: list[dict] = field(default_factory=list)        # retrieved passages, ranked
    refused: bool = False
    latency_ms: float = 0.0
    usage: dict = field(default_factory=dict)
    cost_usd: float | None = None
    error: str | None = None
    raw: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def looks_like_refusal(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in REFUSAL_MARKERS)


class HttpRagTarget:
    """Calls an fde-02-compatible RAG service. Propagates W3C trace context when tracing is on."""

    kind = "http"

    def __init__(self, base_url: str, *, timeout: float = 120.0,
                 transport: httpx.BaseTransport | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self._http = httpx.Client(base_url=self.base_url, timeout=timeout, transport=transport)

    def describe(self) -> dict:
        info: dict = {"kind": self.kind, "url": self.base_url}
        try:
            info["ready"] = self._http.get("/health/ready").json()
        except (httpx.HTTPError, ValueError) as e:
            info["ready_error"] = type(e).__name__
        return info

    def ask(self, question: str, *, docs: list[str] | None = None, headers: dict | None = None,
            **_) -> Response:
        t0 = time.perf_counter()
        try:
            r = self._http.post("/api/v1/ask", json={"question": question, "docs": docs},
                                headers=headers or {})
            r.raise_for_status()
            body = r.json()
        except (httpx.HTTPError, ValueError) as e:
            return Response("", latency_ms=(time.perf_counter() - t0) * 1000,
                            error=f"{type(e).__name__}: {str(e)[:200]}")
        return Response(
            answer=body.get("answer", ""),
            citations=[{"doc": c.get("doc"), "page": c.get("page")}
                       for c in body.get("citations", [])],
            refused=bool(body.get("refused")),
            latency_ms=(time.perf_counter() - t0) * 1000,
            usage=body.get("usage") or {}, cost_usd=body.get("cost_usd"),
            hits=[{"doc": h.get("doc"), "page": h.get("page"), "preview": h.get("preview", "")}
                  for h in body.get("hits") or []],
            raw={k: body.get(k) for k in ("mode", "model", "refusal_reason", "timings_ms",
                                          "invalid_citations", "tool_calls")})

    def close(self) -> None:
        self._http.close()


PROMPT_ONLY_SYSTEM = (
    "You are a careful analyst. Answer the question concisely from your own knowledge. "
    "If you do not know, say \"I can't answer that\". Do not invent figures.")


class PromptOnlyTarget:
    """The LLM alone, no documents: shows what retrieval adds."""

    kind = "prompt-only"

    def __init__(self, client=None, role: str = "default") -> None:
        from rag_eval.llm import client_for
        self.client = client or client_for()
        self.role = role

    def describe(self) -> dict:
        return {"kind": self.kind, "model": self.client.provider.model_for(self.role)}

    def _ask(self, messages: list[dict]) -> Response:
        t0 = time.perf_counter()
        try:
            out = self.client.complete(messages, role=self.role, temperature=0)
        except httpx.HTTPError as e:
            return Response("", error=type(e).__name__)
        text = out["content"] or ""
        usage = out["usage"] or {}
        return Response(text, refused=looks_like_refusal(text),
                        latency_ms=(time.perf_counter() - t0) * 1000, usage=usage,
                        cost_usd=self.client.provider.cost_usd(
                            out["model"], usage.get("prompt_tokens", 0),
                            usage.get("completion_tokens", 0)), raw={"model": out["model"]})

    def ask(self, question: str, **_) -> Response:
        return self._ask([{"role": "system", "content": PROMPT_ONLY_SYSTEM},
                          {"role": "user", "content": question}])


class OracleContextTarget(PromptOnlyTarget):
    """The LLM given the gold evidence: an upper bound for what retrieval could enable."""

    kind = "oracle-context"

    def ask(self, question: str, *, context: str = "", **_) -> Response:
        return self._ask([{"role": "system", "content": PROMPT_ONLY_SYSTEM.replace(
            "from your own knowledge", "using only the context")},
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"}])


class ReplayTarget:
    """Responses recorded in a run's cases.jsonl, keyed by case id: re-score without calling
    anything (new metrics, a new judge, a new gate)."""

    kind = "replay"

    def __init__(self, cases_path: Path) -> None:
        self.responses: dict[str, Response] = {}
        for line in Path(cases_path).read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                self.responses[row["id"]] = Response(**row["response"])
        self.path = str(cases_path)

    def describe(self) -> dict:
        return {"kind": self.kind, "path": self.path, "cases": len(self.responses)}

    def ask(self, question: str, *, case_id: str = "", **_) -> Response:
        if case_id not in self.responses:
            return Response("", error=f"no recorded response for {case_id}")
        return self.responses[case_id]
