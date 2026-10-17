"""Metrics: answer correctness by type, citations, refusals, uncertainty and agreement."""

from __future__ import annotations

import math
import random
import re
from collections import Counter

# ---- answer correctness -----------------------------------------------------------------

_NUM = re.compile(r"\(?-?\$?\s?\d[\d,]*(?:\.\d+)?\)?\s*%?"
                  r"(?:\s*(?:billion|million|thousand|bn|mn|m|k)\b)?", re.I)
_SCALE = {"billion": 1e9, "bn": 1e9, "million": 1e6, "mn": 1e6, "m": 1e6, "thousand": 1e3,
          "k": 1e3}
_WORD = re.compile(r"[a-z0-9]+")


def parse_number(text: str) -> tuple[float, bool] | None:
    """First number in text as (absolute value, has_unit_word); years after FY are skipped."""
    for m in _NUM.finditer(text):
        raw = m.group(0)
        if re.search(r"FY\s?$", text[max(0, m.start() - 3):m.start()], re.I):
            continue
        digits = re.search(r"\d[\d,]*(?:\.\d+)?", raw).group(0).replace(",", "")
        if re.fullmatch(r"(19|20)\d{2}", digits) and not re.search(r"[$%]", raw):
            continue
        value = float(digits)
        unit = re.search(r"(billion|million|thousand|bn|mn|m|k)\b", raw, re.I)
        if unit:
            value *= _SCALE[unit.group(1).lower()]
        return abs(value), bool(unit)
    return None


def numeric_match(prediction: str, gold: str, rel_tol: float = 0.01) -> bool:
    p, g = parse_number(prediction), parse_number(gold)
    if p is None or g is None:
        return False

    def close(a: float, b: float) -> bool:
        return abs(a - b) <= rel_tol * max(abs(b), 1e-12)

    if close(p[0], g[0]):
        return True
    if p[1] and g[1]:
        return False
    return any(close(p[0] * s, g[0]) for s in (1e3, 1e6, 1e9, 1e-3, 1e-6, 1e-9))


def yes_no_maybe(text: str) -> str | None:
    """The yes/no/maybe verdict an answer commits to, or None."""
    t = text.strip().lower()
    m = re.match(r"^\W*(yes|no|maybe)\b", t) or re.search(
        r"\b(?:answer|verdict|conclusion)\s*(?:is|:)\s*\W*(yes|no|maybe)\b", t)
    return m.group(1) if m else None


def tokens(text: str) -> list[str]:
    return _WORD.findall(text.lower())


def token_f1(prediction: str, gold: str) -> float:
    """SQuAD-style token F1: overlap of lower-cased alphanumeric tokens (multiset).

    precision = common / len(pred_tokens), recall = common / len(gold_tokens),
    F1 = 2PR / (P + R). Both empty → 1.0; exactly one empty → 0.0.
    """
    raise NotImplementedError("TODO week-16 token F1: see labs/")


ABSENT_MARKERS = ("no such clause", "does not contain", "doesn't contain", "has no", "not found",
                  "no clause", "none", "not include", "no provision")


def is_correct(answer: str, refused: bool, gold: str, answer_type: str,
               alternatives: list[str] | None = None) -> bool:
    """Deterministic correctness by answer type (the 'reference judge')."""
    if answer_type == "refusal":
        return refused
    if answer_type == "absent":
        return refused or any(m in answer.lower() for m in ABSENT_MARKERS)
    if refused:
        return False
    if answer_type == "numeric":
        return numeric_match(answer, gold)
    if answer_type == "yes_no_maybe":
        return yes_no_maybe(answer) == gold.strip().lower()
    if answer_type == "span":
        return max(token_f1(answer, g) for g in [gold, *(alternatives or [])]) >= 0.5
    # free_text: word overlap, and every figure in the gold must appear in the answer.
    # Still weak on paraphrase; the LLM judge does better there.
    return token_f1(answer, gold) >= 0.5 and figures_present(answer, gold)


def numbers(text: str) -> list[float]:
    """Every number in text (absolute values, unit words applied, bare years skipped)."""
    out: list[float] = []
    for m in _NUM.finditer(text):
        parsed = parse_number(m.group(0))
        if parsed is not None:
            out.append(parsed[0])
    return out


def figures_present(answer: str, gold: str, rel_tol: float = 0.01) -> bool:
    """True when each figure in gold is matched (within rel_tol) by a figure in answer."""
    found = numbers(answer)
    return all(any(abs(a - g) <= rel_tol * max(abs(g), 1e-12) for a in found)
               for g in numbers(gold))


# ---- citations ----------------------------------------------------------------------------

def citation_scores(citations: list[dict], evidence: list[dict]) -> dict[str, float | bool]:
    """Page-level citation quality against gold evidence.

    A citation {"doc", "page"} matches an evidence item when the docs are equal and either the
    evidence page is None (any page of that doc counts) or the pages are equal.
    Return {"precision": matched citations / citations, "recall": evidence items matched by
    at least one citation / evidence items, "hit": any match}. Precision is 0.0 with no
    citations; recall is 1.0 when there is no evidence (nothing to find).
    """
    raise NotImplementedError("TODO week-16 citation precision and recall: see labs/")


# ---- uncertainty and agreement ------------------------------------------------------------

def wilson_interval(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score interval for a proportion (better than p ± z·SE for small n or
    proportions near 0 or 1). n = 0 → (0.0, 1.0).

    centre = (p + z²/2n) / (1 + z²/n); half = z·sqrt(p(1−p)/n + z²/4n²) / (1 + z²/n)
    """
    raise NotImplementedError("TODO week-16 Wilson interval: see labs/")


def cohens_kappa(a: list[str], b: list[str]) -> float:
    """Agreement between two raters beyond chance: (p_o − p_e) / (1 − p_e).

    p_o = share of items where a and b agree; p_e = Σ_label P_a(label)·P_b(label).
    Return 1.0 when p_e == 1 (both raters always give the same single label).
    """
    if len(a) != len(b) or not a:
        raise ValueError("need two non-empty label lists of equal length")
    raise NotImplementedError("TODO week-17 Cohen's kappa: see labs/")


def bootstrap_diff_ci(a: list[float], b: list[float], n_boot: int = 2000, seed: int = 0,
                      alpha: float = 0.05) -> tuple[float, float, float]:
    """Paired bootstrap for mean(b) − mean(a) over the same cases.

    Resample case indices with replacement n_boot times (random.Random(seed)), compute the
    difference of means for each resample, and return (observed difference, lower, upper)
    using the alpha/2 and 1 − alpha/2 percentiles of the resampled differences.
    """
    if len(a) != len(b) or not a:
        raise ValueError("need two non-empty paired lists of equal length")
    raise NotImplementedError("TODO week-18 paired bootstrap: see labs/")


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(q * (len(ordered) - 1) + 0.5))]
