from __future__ import annotations

import io
import json
import zipfile

import pytest

from rag_eval import golden
from rag_eval.golden import GoldenItem
from tests.conftest import ROOT


def test_item_validation():
    with pytest.raises(ValueError, match="answer_type"):
        GoldenItem(id="x", domain="finance", question="q?", answer="a", answer_type="essay")
    with pytest.raises(ValueError, match="empty"):
        GoldenItem(id="x", domain="finance", question="  ", answer="a", answer_type="numeric")


def test_split_is_deterministic_and_balanced():
    splits = [golden.split_of(f"item-{i}") for i in range(400)]
    assert splits == [golden.split_of(f"item-{i}") for i in range(400)]
    assert 160 < splits.count("dev") < 240


def test_save_load_verify_diff(tmp_path, items):
    golden.save(items, tmp_path, "toy", "v1")
    assert [i.id for i in golden.load(tmp_path, "toy", "v1")] == ["n1", "n2", "y1", "r1"]
    assert [i.id for i in golden.load(tmp_path, "toy", "v1", split="dev")] == ["y1"]
    ok, message = golden.verify(tmp_path, "toy", "v1")
    assert ok and "match" in message
    manifest = json.loads((tmp_path / "toy" / "v1" / "manifest.json").read_text())
    assert manifest["by_answer_type"] == {"numeric": 2, "refusal": 1, "yes_no_maybe": 1}
    # editing an item breaks the fingerprint
    path = tmp_path / "toy" / "v1" / "items.jsonl"
    path.write_text(path.read_text().replace("$285 million", "$286 million"))
    assert not golden.verify(tmp_path, "toy", "v1")[0]
    changed = items[:1] + [GoldenItem(**{**items[1].to_dict(), "answer": "$1"})] + items[3:]
    assert golden.diff(items, changed) == {"added": [], "removed": ["y1"], "changed": ["n2"]}


def test_fingerprint_ignores_order(items):
    assert golden.items_sha256(items) == golden.items_sha256(list(reversed(items)))


def test_committed_goldens_verify():
    """PubMedQA, CUAD and refusal items are committed; FinanceBench ships only a manifest."""
    for name in ("pubmedqa", "cuad", "refusal"):
        ok, message = golden.verify(ROOT / "goldens", name, "v1")
        assert ok, message
    assert (ROOT / "goldens" / "financebench" / "v1" / "manifest.json").exists()


def test_refusal_set_is_hand_written_and_stable():
    items = golden.build_refusal()
    assert len(items) == 30 and {i.answer_type for i in items} == {"refusal"}
    assert {i.tags[0] for i in items} == {"no-company", "no-period", "out-of-domain", "advice",
                                          "personal", "false-premise"}


def _patch_source(monkeypatch, name, path, data: bytes, **extra):
    spec = dict(golden.SOURCES[name]) | {"sha256": golden._sha256(data)} | extra
    monkeypatch.setitem(golden.SOURCES, name, spec)
    target = path / spec["file"]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)


def test_build_financebench_converts_pages_to_one_based(tmp_path, monkeypatch):
    rows = [{"financebench_id": "financebench_id_03029", "question": "Capex?", "answer": "$1577",
             "doc_name": "3M_2018_10K", "question_type": "metrics-generated",
             "evidence": [{"evidence_page_num": 59}]},
            {"financebench_id": "financebench_id_00001", "question": "Why?",
             "answer": "Because demand fell sharply in the period", "doc_name": "X_2020_10K",
             "question_type": "novel-generated", "evidence": []}]
    data = "\n".join(json.dumps(r) for r in rows).encode()
    _patch_source(monkeypatch, "financebench", tmp_path, data)
    items = golden.build_financebench(tmp_path)
    assert items[0].id == "fb-03029" and items[0].answer_type == "numeric"
    assert items[0].evidence == [{"doc": "3M_2018_10K", "page": 60}]
    assert items[1].answer_type == "free_text"


def test_build_pubmedqa_keeps_label_mix(tmp_path, monkeypatch):
    data = {str(1000 + i): {"QUESTION": f"Does drug {i} work?", "final_decision": label,
                            "LONG_ANSWER": "Because.", "YEAR": "2010",
                            "CONTEXTS": ["c1", "c2"], "LABELS": ["BACKGROUND", "RESULTS"]}
            for i, label in enumerate(["yes"] * 6 + ["no"] * 3 + ["maybe"])}
    _patch_source(monkeypatch, "pubmedqa", tmp_path, json.dumps(data).encode())
    items = golden.build_pubmedqa(tmp_path, n=5)
    labels = sorted(i.answer for i in items)
    assert labels == ["maybe", "no", "no", "yes", "yes"]     # every stratum kept, n respected
    assert items[0].evidence[0]["page"] is None              # any page of the abstract counts
    pdfs = golden.build_corpus("pubmedqa", tmp_path, tmp_path / "corpus", items)
    assert len(pdfs) == len(items)
    info = json.loads((tmp_path / "corpus" / "doc_info.json").read_text())
    assert info[f"PUBMED_{items[0].source['id']}"]["doc_type"] == "abstract"


def test_build_cuad_locates_span_pages(tmp_path, monkeypatch):
    context = "MASTER AGREEMENT\nThis Agreement shall be governed by the laws of Delaware.\n" \
              + "\n".join(f"Section {n}. Filler text for page layout." for n in range(80))
    test_json = json.dumps({"data": [{"title": "ACME_MASTER", "paragraphs": [{
        "context": context, "qas": [
            {"question": 'Highlight the parts (if any) of this contract related to "Governing '
                         'Law" that should be reviewed by a lawyer.',
             "answers": [{"text": "This Agreement shall be governed by the laws of Delaware."}]},
            {"question": 'Highlight the parts (if any) of this contract related to "Audit '
                         'Rights" that should be reviewed by a lawyer.', "answers": []},
            {"question": 'Highlight the parts (if any) of this contract related to "Parties" '
                         'that should be reviewed by a lawyer.', "answers": []}]}]}]}).encode()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        z.writestr("test.json", test_json)
    _patch_source(monkeypatch, "cuad", tmp_path, buffer.getvalue(),
                  member_sha256=golden._sha256(test_json))
    items = {i.tags[0]: i for i in golden.build_cuad(tmp_path)}
    assert set(items) == {"Governing Law", "Audit Rights"}
    assert items["Governing Law"].answer_type == "span"
    assert items["Governing Law"].evidence == [{"doc": "CUAD_000", "page": 1}]
    assert items["Audit Rights"].answer_type == "absent"
    assert golden.build_corpus("cuad", tmp_path, tmp_path / "c", list(items.values()))


def test_fetch_verifies_checksum(tmp_path, monkeypatch):
    import httpx

    payload = b'{"1": {}}'
    spec = dict(golden.SOURCES["pubmedqa"]) | {"sha256": golden._sha256(payload)}
    monkeypatch.setitem(golden.SOURCES, "pubmedqa", spec)
    ok = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200,
                                                                              content=payload)))
    assert golden.fetch("pubmedqa", tmp_path, client=ok).read_bytes() == payload
    assert golden.fetch("pubmedqa", tmp_path).exists()           # cached, no download
    (tmp_path / spec["file"]).unlink()
    bad = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200,
                                                                               content=b"x")))
    with pytest.raises(ValueError, match="checksum"):
        golden.fetch("pubmedqa", tmp_path, client=bad)
