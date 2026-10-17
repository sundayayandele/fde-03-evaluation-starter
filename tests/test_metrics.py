from __future__ import annotations

import pytest

from rag_eval.metrics import (
    bootstrap_diff_ci,
    citation_scores,
    cohens_kappa,
    figures_present,
    is_correct,
    numeric_match,
    parse_number,
    percentile,
    token_f1,
    wilson_interval,
    yes_no_maybe,
)


@pytest.mark.parametrize("text, expected", [
    ("$1,577 million", (1.577e9, True)),
    ("24.8%", (24.8, False)),
    ("(285)", (285.0, False)),
    ("In FY2018 capex was $1.5 billion", (1.5e9, True)),
    ("2019 and 2020", None),
    ("no figures", None),
])
def test_parse_number(text, expected):
    assert parse_number(text) == expected


@pytest.mark.parametrize("pred, gold, ok", [
    ("$1,577 million", "$1577.00", True),        # unit mismatch tolerated by scale search
    ("1.577 billion", "$1,577 million", True),
    ("$1,892 million", "$1,577 million", False),
    ("0.66", "0.66", True),
    ("nothing", "0.66", False),
])
def test_numeric_match(pred, gold, ok):
    assert numeric_match(pred, gold) is ok


def test_yes_no_maybe():
    assert yes_no_maybe("Yes, the trial shows it.") == "yes"
    assert yes_no_maybe("The answer is: maybe") == "maybe"
    assert yes_no_maybe("It reduced mortality.") is None


def test_figures_present():
    assert figures_present("gain of about $20 billion", "approximately $20 billion gain")
    assert not figures_present("gain of about $30 billion", "approximately $20 billion gain")
    assert figures_present("anything", "no figures here")


def test_is_correct_by_type():
    assert is_correct("It was $285 million", False, "$285 million", "numeric")
    assert not is_correct("It was $285 million", True, "$285 million", "numeric")
    assert is_correct("No.", False, "no", "yes_no_maybe")
    assert is_correct("anything", True, "(decline)", "refusal")
    assert is_correct("The contract has no such clause.", False, "No such clause", "absent")
    assert not is_correct("The clause reads: x", False, "No such clause", "absent")


def test_percentile():
    assert percentile([], 0.5) == 0.0
    assert percentile([1, 2, 3, 4, 100], 0.5) == 3
    assert percentile([1, 2, 3, 4, 100], 0.95) == 100


@pytest.mark.exercise
def test_token_f1():
    assert token_f1("the cat sat", "the cat sat") == 1.0
    assert token_f1("", "") == 1.0
    assert token_f1("cat", "") == 0.0
    assert token_f1("dog", "cat") == 0.0
    precision, recall = 1.0, 2 / 6
    assert token_f1("the cat", "the cat sat on the mat") == pytest.approx(
        2 * precision * recall / (precision + recall))
    assert token_f1("The Cat!", "the cat") == 1.0


@pytest.mark.exercise
def test_free_text_and_span_correctness_use_token_f1():
    gold = "JnJ will make a gain of approximately $20 billion from the separation"
    assert is_correct(gold, False, gold, "free_text")
    assert not is_correct(gold.replace("20", "30"), False, gold, "free_text")
    assert is_correct('The clause reads: "governed by the laws of Delaware"', False,
                      "governed by the laws of Delaware", "span")


@pytest.mark.exercise
def test_citation_scores():
    evidence = [{"doc": "A", "page": 5}, {"doc": "B", "page": None}]
    cites = [{"doc": "A", "page": 5}, {"doc": "A", "page": 6}, {"doc": "B", "page": 9}]
    assert citation_scores(cites, evidence) == {"precision": 2 / 3, "recall": 1.0, "hit": True}
    assert citation_scores([], evidence) == {"precision": 0.0, "recall": 0.0, "hit": False}
    assert citation_scores([{"doc": "A", "page": 1}], []) == {"precision": 0.0, "recall": 1.0,
                                                              "hit": False}


@pytest.mark.exercise
def test_wilson_interval():
    assert wilson_interval(0, 0) == (0.0, 1.0)
    lo, hi = wilson_interval(50, 100)
    assert lo == pytest.approx(0.4038, abs=1e-3) and hi == pytest.approx(0.5962, abs=1e-3)
    lo, hi = wilson_interval(10, 10)
    assert hi == 1.0 and lo == pytest.approx(0.7225, abs=1e-3)


@pytest.mark.exercise
def test_cohens_kappa():
    assert cohens_kappa(["a", "b", "a", "b"], ["a", "b", "a", "b"]) == 1.0
    assert cohens_kappa(["a", "a"], ["a", "a"]) == 1.0
    assert cohens_kappa(["a", "b", "a", "b"], ["b", "a", "b", "a"]) == -1.0
    # 0.7 observed vs 0.5 chance → 0.4
    a = ["y"] * 5 + ["n"] * 5
    b = ["y"] * 4 + ["n"] + ["y"] * 2 + ["n"] * 3
    assert cohens_kappa(a, b) == pytest.approx(0.4)
    with pytest.raises(ValueError):
        cohens_kappa([], [])


@pytest.mark.exercise
def test_bootstrap_diff_ci():
    a, b = [0.0] * 50 + [1.0] * 50, [1.0] * 100
    observed, lo, hi = bootstrap_diff_ci(a, b, n_boot=500)
    assert observed == 0.5 and 0.38 < lo < 0.5 < hi < 0.62
    same = bootstrap_diff_ci([1.0, 0.0] * 20, [1.0, 0.0] * 20, n_boot=200)
    assert same == (0.0, 0.0, 0.0)
    assert bootstrap_diff_ci(a, b, n_boot=300, seed=3) == bootstrap_diff_ci(a, b, n_boot=300,
                                                                            seed=3)
    with pytest.raises(ValueError):
        bootstrap_diff_ci([1.0], [])
