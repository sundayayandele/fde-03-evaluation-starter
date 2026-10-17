"""Calibration sets for judges.

1. Constructed set (offline, labels by construction): for each golden item, candidate answers
   whose correct label is known because of how they were made: the gold restated, the gold
   with its figure perturbed, a flipped verdict, another item's answer, a refusal...
   It tests whether a judge applies the rubric mechanically right. It is NOT human judgement.
2. Human set: a stratified sample of real system answers exported to CSV, labelled by a
   person (`human_label`), imported back. Judge-vs-human kappa is the number that matters.
"""

from __future__ import annotations

import csv
import random
import re
from pathlib import Path

from rag_eval.golden import GoldenItem
from rag_eval.metrics import numeric_match

REFUSAL_TEXT = "I can't answer that from the documents provided."
# The wrong answer to borrow when a domain has no other item to take one from.
_FALLBACK_OTHER = GoldenItem(id="_other", domain="any", question="-", answer_type="free_text",
                             answer="The parties agreed to share costs equally for 42 months.")


def perturb_number(text: str, factor: float) -> str | None:
    """Multiply the first number in `text` (that is not a 4-digit year) by `factor`, keeping
    its formatting style: thousands separators if it had them, the same number of decimals.
    Return None if there is no such number.

    "$1,577.00 million" × 1.2 → "$1,892.40 million"; "24.8%" × 1.2 → "29.8%"
    """
    raise NotImplementedError("TODO week-17 perturb a figure: see labs/")


def candidates(item: GoldenItem, other: GoldenItem) -> list[dict]:
    """Labelled candidate answers for one golden item."""
    gold = item.answer
    out: list[dict] = []

    def add(kind: str, answer: str, label: str, refused: bool = False) -> None:
        out.append({"id": f"{item.id}:{kind}", "kind": kind, "question": item.question,
                    "gold": gold, "answer": answer, "answer_type": item.answer_type,
                    "refused": refused, "alternatives": item.alternatives, "label": label,
                    "domain": item.domain})

    def changed(factor: float) -> str | None:
        """A perturbed gold whose figure really differs (0.01 × 1.2 rounds back to 0.01)."""
        wrong = perturb_number(gold, factor)
        return wrong if wrong and not numeric_match(wrong, gold) else None

    if item.answer_type == "numeric":
        add("restated", f"The figure is {gold} for the period asked [1].", "CORRECT")
        wrong = changed(1.2)
        if wrong:
            add("off-by-20pct", f"The figure is {wrong} [1].", "INCORRECT")
        tenfold = changed(10)
        if tenfold:
            add("tenfold", f"It was {tenfold} [2].", "INCORRECT")
        add("refusal", REFUSAL_TEXT, "REFUSED", refused=True)
    elif item.answer_type == "yes_no_maybe":
        flip = {"yes": "no", "no": "yes", "maybe": "yes"}[gold]
        reason = item.alternatives[0] if item.alternatives else ""
        add("restated", f"{gold.capitalize()}. {reason}", "CORRECT")
        add("flipped", f"{flip.capitalize()}. {reason}", "INCORRECT")
        add("refusal", REFUSAL_TEXT, "REFUSED", refused=True)
    elif item.answer_type == "free_text":
        add("restated", gold, "CORRECT")
        wrong = changed(1.5)
        if wrong:
            add("figure-changed", wrong, "INCORRECT")
        add("other-answer", other.answer, "INCORRECT")
        add("refusal", REFUSAL_TEXT, "REFUSED", refused=True)
    elif item.answer_type == "span":
        add("quoted", f'The clause reads: "{gold}"', "CORRECT")
        add("none-claimed", "The contract has no such clause.", "INCORRECT")
        add("other-clause", f'The clause reads: "{other.answer}"', "INCORRECT")
    elif item.answer_type == "absent":
        add("none-stated", "The contract has no such clause.", "CORRECT")
        add("declined", REFUSAL_TEXT, "CORRECT", refused=True)
        add("invented", f'The clause reads: "{other.answer}"', "INCORRECT")
    elif item.answer_type == "refusal":
        add("declined", REFUSAL_TEXT, "CORRECT", refused=True)
        add("answered", other.answer, "INCORRECT")
    return out


def constructed_set(items: list[GoldenItem], per_domain: int = 40, seed: int = 7) -> list[dict]:
    """Deterministic stratified sample of items per domain, all candidates of each."""
    rng = random.Random(seed)
    by_domain: dict[str, list[GoldenItem]] = {}
    for item in items:
        by_domain.setdefault(item.domain, []).append(item)
    cases: list[dict] = []
    for domain in sorted(by_domain):
        pool = sorted(by_domain[domain], key=lambda i: i.id)
        chosen = rng.sample(pool, min(per_domain, len(pool)))
        same_type = {t: [i for i in pool if i.answer_type == t] for t in {i.answer_type
                                                                            for i in pool}}
        spans = [i for i in pool if i.answer_type == "span"]
        for item in chosen:
            peers = [p for p in (spans if item.answer_type in {"span", "absent"} else
                                 same_type[item.answer_type]) if p.id != item.id
                     and p.answer != item.answer] or [p for p in pool if p.id != item.id]
            cases.extend(candidates(item, rng.choice(peers) if peers else _FALLBACK_OTHER))
    return cases


HUMAN_FIELDS = ["id", "domain", "answer_type", "question", "gold", "answer", "judge_label",
                "human_label", "notes"]


def export_for_labelling(rows: list[dict], path: Path, n: int = 40, seed: int = 11) -> Path:
    """Write a stratified sample of judged run rows to CSV for a person to label."""
    rng = random.Random(seed)
    by_label: dict[str, list[dict]] = {}
    for r in rows:
        by_label.setdefault(r.get("judge_label", "?"), []).append(r)
    sample: list[dict] = []
    for label in sorted(by_label):
        group = by_label[label]
        sample += rng.sample(group, min(len(group), max(1, n * len(group) // len(rows))))
    with Path(path).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=HUMAN_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for r in sample[:n]:
            writer.writerow({**{k: r.get(k, "") for k in HUMAN_FIELDS}, "human_label": ""})
    return Path(path)


def import_labels(path: Path) -> list[dict]:
    """Labelled rows from a CSV; rows without a human_label are skipped."""
    with Path(path).open(newline="", encoding="utf-8") as handle:
        rows = [r for r in csv.DictReader(handle) if r.get("human_label", "").strip()]
    for r in rows:
        r["human_label"] = r["human_label"].strip().upper()
    return rows
