from __future__ import annotations

import _term_lib as tl


def test_canonical_term_key_collapses_whitespace_and_singularizes_last_token(monkeypatch):
    monkeypatch.setattr(tl, "_singularize_token", lambda _token: "Move")
    assert tl.canonical_term_key("  Basic   Moves  ") == "Basic Move"


def test_canonical_term_key_returns_empty_for_blank():
    assert tl.canonical_term_key("   ") == ""


def test_parse_doc_expands_nlp_max_length_for_large_text(monkeypatch):
    class FakeNLP:
        def __init__(self) -> None:
            self.max_length = 1_000_000

        def __call__(self, text: str) -> dict[str, int]:
            if len(text) > self.max_length:
                raise ValueError("text exceeds max_length")
            return {"length": len(text)}

    large_text = "a" * 1_000_010
    fake_nlp = FakeNLP()

    monkeypatch.setattr(tl, "SPACY_AVAILABLE", True)
    monkeypatch.setattr(tl, "get_nlp", lambda: fake_nlp)
    monkeypatch.setattr(tl, "_DOC_CACHE", {})

    doc = tl.parse_doc(large_text)

    assert doc == {"length": len(large_text)}
    assert fake_nlp.max_length >= len(large_text)


def test_extract_candidates_fallback_without_spacy(monkeypatch):
    monkeypatch.setattr(tl, "SPACY_AVAILABLE", False)
    result = tl.extract_candidates({"docs/a.md": "Move move harm move"}, min_frequency=2)
    assert "move" in {item["normalized"] for item in result}


def test_count_term_fallback_case_insensitive(monkeypatch):
    monkeypatch.setattr(tl, "SPACY_AVAILABLE", False)
    monkeypatch.setattr(tl, "INFLECT_AVAILABLE", False)

    total, files = tl.count_term({"docs/a.md": "move MOVE moves"}, "move")

    assert total == 2
    assert files["docs/a.md"] == 2


def test_is_managed_term_requires_flag_or_approved_status():
    assert tl.is_managed_term("Move", {"is_term": True}) is True
    assert tl.is_managed_term("Move", {"status": "approved"}) is True
    assert tl.is_managed_term("Move", {"status": "candidate"}) is False
    assert tl.is_managed_term("Move", None) is False


def test_find_term_spans_matches_cjk_term_inside_cjk_prose():
    # Chinese prose has no inter-word spaces; token-based matching must not be
    # used for CJK terms or embedded occurrences are invisible.
    content = "每位冒險者都會獲得一個屬性值。冒險者可以行動。"
    spans = tl.find_term_spans(content, "冒險者")
    assert [content[start:end] for start, end in spans] == ["冒險者", "冒險者"]


def test_find_term_spans_cjk_matches_without_spacy(monkeypatch):
    monkeypatch.setattr(tl, "SPACY_AVAILABLE", False)
    spans = tl.find_term_spans("這裡出現典獄長一詞。", "典獄長")
    assert len(spans) == 1


def test_count_terms_batch_counts_cjk_terms():
    corpus = {"docs/a.md": "冒險者前進。冒險者休息。守密人觀察。"}
    results = tl.count_terms_batch(corpus, ["冒險者", "守密人"])
    assert results["冒險者"][0] == 2
    assert results["冒險者"][1] == {"docs/a.md": 2}
    assert results["守密人"][0] == 1
