from __future__ import annotations

from _opendataloader_lib import split_pages_content


def test_exact_page_count():
    content = "p1\n---\np2\n---\np3"
    assert split_pages_content(content, 3) == [(1, "p1"), (2, "p2"), (3, "p3")]


def test_tolerates_off_by_two():
    content = "p1\n---\np2\n---\np3"
    result = split_pages_content(content, 5)
    assert result is not None
    assert len(result) == 3


def test_formfeed_separator():
    assert split_pages_content("a\x0cb", 2) == [(1, "a"), (2, "b")]


def test_unsplittable_returns_none():
    assert split_pages_content("single blob of text", 10) is None


def test_empty_pages_filtered():
    content = "p1\n---\n\n---\np2"
    assert split_pages_content(content, 2) == [(1, "p1"), (2, "p2")]
