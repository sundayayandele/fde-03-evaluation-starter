from __future__ import annotations

import json

import pytest

from rag_eval import calibration, judge
from rag_eval.golden import GoldenItem
from tests.conftest import ROOT


class FakeProvider:
    name = "fake"

    def model_for(self, role):
        return f"fake-{role}"


class FakeClient:
    provider = FakeProvider()

    def __init__(self, contents):
        self.contents = list(contents)
        self.calls = []

    def complete(self, messages, **kwargs):
        self.calls.append({"messages": messages, **kwargs})
        return {"content": self.contents.pop(0), "usage": {"prompt_tokens": 10},
                "model": "fake-strong"}


def test_reference_judge_numeric_and_refusal():
    j = judge.ReferenceJudge()
    assert j.judge("q", "$285 million", "It was $285 million [1]", "numeric", False).label \
        == "CORRECT"
    assert j.judge("q", "$285 million", "$300 million", "numeric", False).label == "INCORRECT"
    assert j.judge("q", "$285 million", "I can't answer", "numeric", True).label == "REFUSED"
    assert j.judge("q", "(decline)", "I can't answer", "refusal", True).label == "CORRECT"
    assert j.describe() == {"name": "reference"}


@pytest.mark.exercise
def test_llm_judge_parses_json_and_defaults_to_incorrect():
    rubric = judge.load_rubric(ROOT / "config" / "rubric.yaml")
    client = FakeClient(['{"label": "correct", "reason": "matches"}', "not json",
                         '{"label": "PARTIAL"}'])
    j = judge.LLMJudge(client=client, rubric=rubric)
    assert j.judge("q", "g", "a", "numeric", False).label == "CORRECT"
    assert j.judge("q", "g", "a", "numeric", False).label == "INCORRECT"
    assert j.judge("q", "g", "a", "numeric", False).label == "INCORRECT"
    assert client.calls[0]["response_format"] == {"type": "json_object"}
    assert client.calls[0]["temperature"] == 0
    assert j.describe()["model"] == "fake-strong"
    assert j.describe()["rubric_version"] == rubric["rubric_version"]
    assert isinstance(judge.get_judge("llm", client=client, rubric=rubric), judge.LLMJudge)
    with pytest.raises(ValueError):
        judge.get_judge("oracle")


@pytest.mark.exercise
def test_build_judge_messages():
    rubric = judge.load_rubric(ROOT / "config" / "rubric.yaml")
    messages = judge.build_judge_messages(rubric, "Capex?", "$285 million", "$285m",
                                          "numeric")
    assert [m["role"] for m in messages] == ["system", "user"]
    system, user = messages[0]["content"], messages[1]["content"]
    assert rubric["criteria"]["numeric"].strip() in system
    assert rubric["refused_definition"].strip() in system
    assert '"label"' in system and "JSON" in system
    assert user == "Question: Capex?\nGold answer: $285 million\nAnswer to grade: $285m"
    fallback = judge.build_judge_messages(rubric, "q", "g", "a", "essay")[0]["content"]
    assert rubric["criteria"]["free_text"].strip() in fallback


@pytest.mark.exercise
@pytest.mark.parametrize("text, factor, expected", [
    ("$1,577.00 million", 1.2, "$1,892.40 million"),
    ("24.8%", 1.2, "29.8%"),
    ("FY2018 was 12", 2, "FY2018 was 24"),
    ("In 2019 revenue was 1500 units", 2, "In 2019 revenue was 3000 units"),
    ("no figures", 2, None),
])
def test_perturb_number(text, factor, expected):
    assert calibration.perturb_number(text, factor) == expected


def _items():
    return [
        GoldenItem(id="n1", domain="finance", question="Capex?", answer="$285 million",
                   answer_type="numeric"),
        GoldenItem(id="n2", domain="finance", question="Tiny?", answer="0.01",
                   answer_type="numeric"),
        GoldenItem(id="f1", domain="finance", question="Why?", answer="A gain of $20 billion "
                   "from the separation of the consumer business", answer_type="free_text"),
        GoldenItem(id="f2", domain="finance", question="What?", answer="Demand fell in Europe "
                   "and Asia during the year", answer_type="free_text"),
        GoldenItem(id="y1", domain="health", question="Works?", answer="yes",
                   answer_type="yes_no_maybe", alternatives=["It reduced risk."]),
        GoldenItem(id="s1", domain="legal", question="Law?", answer="governed by Delaware law",
                   answer_type="span"),
        GoldenItem(id="s2", domain="legal", question="Audit?", answer="may audit the books "
                   "once a year", answer_type="span"),
        GoldenItem(id="a1", domain="legal", question="Cap?", answer="No such clause",
                   answer_type="absent"),
    ]


@pytest.mark.exercise
def test_constructed_set_and_reference_calibration():
    cases = calibration.constructed_set(_items(), per_domain=10)
    kinds = {c["id"] for c in cases}
    assert "n1:off-by-20pct" in kinds and "n1:tenfold" in kinds
    assert "n2:off-by-20pct" not in kinds          # 0.01 × 1.2 rounds back to 0.01
    assert {c["label"] for c in cases} == {"CORRECT", "INCORRECT", "REFUSED"}
    result = judge.calibrate(judge.ReferenceJudge(), cases)
    assert result["cases"] == len(cases)
    assert result["agreement"] == 1.0 and result["kappa"] == 1.0
    assert result["disagreements"] == []


@pytest.mark.exercise
def test_calibrate_reports_disagreements():
    always_correct = type("J", (), {"name": "lenient", "judge":
                                    lambda self, *a, **k: judge.Verdict("CORRECT")})()
    cases = calibration.constructed_set(_items(), per_domain=10)
    result = judge.calibrate(always_correct, cases)
    assert result["agreement"] < 0.5 and result["kappa"] == 0.0
    assert result["per_label"]["CORRECT"]["recall"] == 1.0
    assert result["disagreements"][0]["judge"] == "CORRECT"


def test_export_and_import_labels(tmp_path):
    rows = [{"id": f"c{i}", "domain": "finance", "answer_type": "numeric", "question": "q",
             "gold": "1", "answer": "1", "judge_label": "CORRECT" if i % 3 else "INCORRECT"}
            for i in range(30)]
    path = calibration.export_for_labelling(rows, tmp_path / "labels.csv", n=12)
    text = path.read_text().splitlines()
    assert text[0].startswith("id,domain,answer_type") and 10 <= len(text) - 1 <= 12
    filled = [line.replace(",,", ",correct,", 1) if i == 1 else line
              for i, line in enumerate(text)]
    path.write_text("\n".join(filled) + "\n")
    labelled = calibration.import_labels(path)
    assert len(labelled) == 1 and labelled[0]["human_label"] == "CORRECT"


def test_rubric_covers_every_answer_type():
    from rag_eval.golden import ANSWER_TYPES

    rubric = judge.load_rubric(ROOT / "config" / "rubric.yaml")
    assert ANSWER_TYPES <= set(rubric["criteria"])
    assert json.dumps(rubric)                        # serialisable for run configs
