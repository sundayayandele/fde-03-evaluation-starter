"""Shared fixtures. Runs and results go to temp dirs before the app is imported."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
_RUNS = Path(tempfile.mkdtemp(prefix="rag-eval-runs-"))
_RESULTS = Path(tempfile.mkdtemp(prefix="rag-eval-results-"))
os.environ["RUNS_DIR"] = str(_RUNS)
os.environ["RESULTS_DIR"] = str(_RESULTS)
os.environ["GOLDENS_DIR"] = str(ROOT / "goldens")
os.environ.pop("MISTRAL_API_KEY", None)
os.environ.pop("OTEL_EXPORTER_OTLP_ENDPOINT", None)

from rag_eval.golden import GoldenItem  # noqa: E402
from rag_eval.targets import Response  # noqa: E402


class FakeTarget:
    """A system under test that answers from a dict: question → Response (or answer text)."""

    kind = "fake"

    def __init__(self, answers: dict, default: Response | None = None) -> None:
        self.answers = answers
        self.default = default or Response("I can't answer that.", refused=True)
        self.calls: list[dict] = []

    def describe(self) -> dict:
        return {"kind": self.kind, "ready": {"version": "test"}}

    def ask(self, question: str, **kwargs) -> Response:
        self.calls.append({"question": question, **kwargs})
        value = self.answers.get(question, self.default)
        return value if isinstance(value, Response) else Response(value)


@pytest.fixture
def fake_target():
    return FakeTarget


@pytest.fixture
def items() -> list[GoldenItem]:
    return [
        GoldenItem(id="n1", domain="finance", question="Capex of Acme in FY2023?",
                   answer="$285 million", answer_type="numeric",
                   evidence=[{"doc": "ACME_2023_10K", "page": 5}], split="test"),
        GoldenItem(id="n2", domain="finance", question="Net income of Acme in FY2022?",
                   answer="$475 million", answer_type="numeric",
                   evidence=[{"doc": "ACME_2023_10K", "page": 3}], split="test"),
        GoldenItem(id="y1", domain="health", question="Does X reduce Y?", answer="yes",
                   answer_type="yes_no_maybe", evidence=[{"doc": "PUBMED_1", "page": None}],
                   split="dev"),
        GoldenItem(id="r1", domain="finance", question="Should I buy Acme shares?",
                   answer="(decline)", answer_type="refusal", split="test"),
    ]


@pytest.fixture
def answers() -> dict:
    return {
        "Capex of Acme in FY2023?": Response(
            "$285 million — Purchases of property and equipment [1]",
            citations=[{"doc": "ACME_2023_10K", "page": 5}],
            hits=[{"doc": "ACME_2023_10K", "page": 5, "preview": "capex"}], latency_ms=10),
        "Net income of Acme in FY2022?": Response(
            "$585 million [1]", citations=[{"doc": "ACME_2023_10K", "page": 4}],
            hits=[{"doc": "ACME_2023_10K", "page": 4}, {"doc": "ACME_2023_10K", "page": 3}],
            latency_ms=20),
        "Does X reduce Y?": Response("Yes. The trial showed a reduction.",
                                     citations=[{"doc": "PUBMED_1", "page": 1}],
                                     hits=[{"doc": "PUBMED_1", "page": 1}], latency_ms=30),
        "Should I buy Acme shares?": Response("I can't answer that from the filings provided.",
                                              refused=True, latency_ms=5),
    }
