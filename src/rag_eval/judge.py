"""Judges: a deterministic reference judge and a rubric-based LLM judge, plus calibration.

A judge maps (question, gold, answer) to CORRECT, INCORRECT or REFUSED. Its numbers are only
trusted after calibration: agreement and Cohen's kappa against labelled cases.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import yaml

from rag_eval.metrics import cohens_kappa, is_correct, wilson_interval

LABELS = ("CORRECT", "INCORRECT", "REFUSED")


@dataclass
class Verdict:
    label: str
    reason: str = ""
    usage: dict | None = None
    model: str | None = None


def load_rubric(path: Path = Path("config/rubric.yaml")) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


class ReferenceJudge:
    """Deterministic: numeric match, yes/no/maybe, token-F1 spans. Free, fast, brittle on prose."""

    name = "reference"

    def describe(self) -> dict:
        return {"name": self.name}

    def judge(self, question: str, gold: str, answer: str, answer_type: str, refused: bool,
              alternatives: list[str] | None = None) -> Verdict:
        if refused and answer_type not in {"absent", "refusal"}:
            return Verdict("REFUSED", "answer declined")
        ok = is_correct(answer, refused, gold, answer_type, alternatives)
        return Verdict("CORRECT" if ok else "INCORRECT", f"{answer_type} rule")


def build_judge_messages(rubric: dict, question: str, gold: str, answer: str,
                         answer_type: str) -> list[dict[str, str]]:
    """Messages for the LLM judge.

    system: "You grade answers against a gold answer." + the criteria for `answer_type`
            (rubric["criteria"][answer_type]) + rubric["refused_definition"] + the instruction
            'Reply with JSON only: {"label": "CORRECT" | "INCORRECT" | "REFUSED", "reason": "<one
            sentence>"}'
    user:   "Question: ...\\nGold answer: ...\\nAnswer to grade: ..."
    Unknown answer types fall back to the free_text criteria.
    """
    raise NotImplementedError("TODO week-17 judge prompt: see labs/")


class LLMJudge:
    """Rubric-based judge on a Mistral (or other) model, JSON verdicts, temperature 0."""

    name = "llm"

    def __init__(self, client=None, role: str = "strong", rubric: dict | None = None) -> None:
        from rag_eval.llm import client_for
        self.client = client or client_for()
        self.role = role
        self.rubric = rubric or load_rubric()

    def describe(self) -> dict:
        return {"name": self.name, "model": self.client.provider.model_for(self.role),
                "provider": self.client.provider.name,
                "rubric_version": self.rubric.get("rubric_version")}

    def judge(self, question: str, gold: str, answer: str, answer_type: str, refused: bool,
              alternatives: list[str] | None = None) -> Verdict:
        out = self.client.complete(build_judge_messages(self.rubric, question, gold, answer,
                                                        answer_type),
                                   role=self.role, temperature=0,
                                   response_format={"type": "json_object"})
        try:
            data = json.loads(out["content"])
            label = str(data.get("label", "")).upper()
        except (ValueError, TypeError, AttributeError):
            data, label = {}, ""
        if label not in LABELS:
            label = "INCORRECT"
        return Verdict(label, str(data.get("reason", ""))[:300], out["usage"], out["model"])


def get_judge(name: str, **kwargs):
    if name == "reference":
        return ReferenceJudge()
    if name == "llm":
        return LLMJudge(**kwargs)
    raise ValueError(f"unknown judge {name!r}; use reference or llm")


def calibrate(judge, cases: list[dict]) -> dict:
    """Agreement of `judge` with labelled cases ({question, gold, answer, answer_type, refused,
    alternatives, label}). Returns agreement (with Wilson CI), Cohen's kappa, confusion and
    per-label precision/recall, overall and per answer type."""
    predicted, expected, per_type = [], [], {}
    disagreements = []
    for c in cases:
        v = judge.judge(c["question"], c["gold"], c["answer"], c["answer_type"], c["refused"],
                        c.get("alternatives"))
        predicted.append(v.label)
        expected.append(c["label"])
        per_type.setdefault(c["answer_type"], []).append(v.label == c["label"])
        if v.label != c["label"]:
            disagreements.append({"id": c["id"], "expected": c["label"], "judge": v.label,
                                  "answer": c["answer"][:200], "gold": c["gold"][:200],
                                  "kind": c.get("kind")})
    n = len(cases)
    agree = sum(p == e for p, e in zip(predicted, expected, strict=True))
    confusion = Counter(f"{e}->{p}" for p, e in zip(predicted, expected, strict=True))
    per_label = {}
    for label in LABELS:
        tp = sum(p == e == label for p, e in zip(predicted, expected, strict=True))
        pp, pe = predicted.count(label), expected.count(label)
        per_label[label] = {"precision": round(tp / pp, 4) if pp else None,
                            "recall": round(tp / pe, 4) if pe else None, "support": pe}
    low, high = wilson_interval(agree, n)
    return {"judge": judge.name, "cases": n, "agreement": round(agree / n, 4),
            "agreement_ci95": [round(low, 4), round(high, 4)],
            "kappa": round(cohens_kappa(expected, predicted), 4),
            "by_answer_type": {t: round(sum(v) / len(v), 4) for t, v in sorted(per_type.items())},
            "per_label": per_label, "confusion": dict(sorted(confusion.items())),
            "disagreements": disagreements}
