"""Tests for split_chapters module."""

import pytest

from split_chapters import (
    extract_pages,
    generate_frontmatter,
    get_page_range,
    infer_source_stem,
    build_page_text_stats,
)
from pathlib import Path


# ---------------------------------------------------------------------------
# extract_pages
# ---------------------------------------------------------------------------

class TestExtractPages:
    def test_single_page(self):
        content = "<!-- PAGE 1 -->\n\nHello world"
        pages = extract_pages(content)
        assert pages == {1: "Hello world"}

    def test_multiple_pages(self):
        content = (
            "<!-- PAGE 1 -->\n\nFirst page content\n\n"
            "<!-- PAGE 2 -->\n\nSecond page content\n\n"
            "<!-- PAGE 3 -->\n\nThird page content"
        )
        pages = extract_pages(content)
        assert len(pages) == 3
        assert pages[1] == "First page content"
        assert pages[2] == "Second page content"
        assert pages[3] == "Third page content"

    def test_empty_content(self):
        pages = extract_pages("")
        assert pages == {}

    def test_no_page_markers(self):
        pages = extract_pages("Just some text without markers")
        assert pages == {}

    def test_non_sequential_pages(self):
        content = (
            "<!-- PAGE 5 -->\n\nPage five\n\n"
            "<!-- PAGE 10 -->\n\nPage ten"
        )
        pages = extract_pages(content)
        assert len(pages) == 2
        assert pages[5] == "Page five"
        assert pages[10] == "Page ten"

    def test_page_with_multiline_content(self):
        content = "<!-- PAGE 1 -->\n\nLine one\n\nLine two\n\nLine three"
        pages = extract_pages(content)
        assert "Line one" in pages[1]
        assert "Line two" in pages[1]
        assert "Line three" in pages[1]

    def test_page_content_is_stripped(self):
        content = "<!-- PAGE 1 -->\n\n  Hello  \n\n<!-- PAGE 2 -->\n\nWorld"
        pages = extract_pages(content)
        assert pages[1] == "Hello"


# ---------------------------------------------------------------------------
# get_page_range
# ---------------------------------------------------------------------------

class TestGetPageRange:
    def test_single_page_range(self):
        pages = {1: "A", 2: "B", 3: "C"}
        result = get_page_range(pages, 2, 2)
        assert result == "B"

    def test_multi_page_range(self):
        pages = {1: "A", 2: "B", 3: "C"}
        result = get_page_range(pages, 1, 3)
        assert result == "A\n\nB\n\nC"

    def test_missing_pages_in_range(self):
        pages = {1: "A", 3: "C"}
        result = get_page_range(pages, 1, 3)
        assert result == "A\n\nC"

    def test_all_missing(self):
        pages = {1: "A"}
        result = get_page_range(pages, 5, 7)
        assert result == ""

    def test_empty_pages(self):
        result = get_page_range({}, 1, 5)
        assert result == ""


# ---------------------------------------------------------------------------
# generate_frontmatter
# ---------------------------------------------------------------------------

class TestGenerateFrontmatter:
    def test_title_only(self):
        result = generate_frontmatter("My Title")
        assert "title: My Title" in result
        assert result.startswith("---\n")
        assert result.endswith("---\n")
        assert "description" not in result
        assert "sidebar" not in result

    def test_with_description(self):
        result = generate_frontmatter("Title", description="Some desc")
        assert "title: Title" in result
        assert "description: Some desc" in result

    def test_with_order(self):
        result = generate_frontmatter("Title", order=5)
        assert "sidebar:" in result
        assert "order: 5" in result

    def test_with_all_params(self):
        result = generate_frontmatter("Title", description="Desc", order=0)
        assert "title: Title" in result
        assert "description: Desc" in result
        assert "sidebar:" in result
        assert "order: 0" in result

    def test_order_none_omits_sidebar(self):
        result = generate_frontmatter("Title", order=None)
        assert "sidebar" not in result

    def test_empty_description_omitted(self):
        result = generate_frontmatter("Title", description="")
        assert "description" not in result


# ---------------------------------------------------------------------------
# infer_source_stem
# ---------------------------------------------------------------------------

class TestInferSourceStem:
    def test_with_pages_suffix(self):
        assert infer_source_stem(Path("data/markdown/rulebook_pages.md")) == "rulebook"

    def test_without_pages_suffix(self):
        assert infer_source_stem(Path("data/markdown/rulebook.md")) == "rulebook"

    def test_complex_name_with_pages(self):
        assert infer_source_stem(Path("my_game_rules_pages.md")) == "my_game_rules"

    def test_pages_in_middle_not_stripped(self):
        # Only strip _pages at the end of the stem
        assert infer_source_stem(Path("pages_data.md")) == "pages_data"


# ---------------------------------------------------------------------------
# build_page_text_stats
# ---------------------------------------------------------------------------

class TestBuildPageTextStats:
    def test_basic_stats(self):
        pages = {1: "Hello world", 2: "Another page with more text"}
        stats = build_page_text_stats(pages, [])
        assert 1 in stats
        assert 2 in stats
        assert "text_tokens" in stats[1]
        assert "char_count" in stats[1]
        assert stats[1]["char_count"] == len("Hello world")

    def test_empty_pages(self):
        stats = build_page_text_stats({}, [])
        assert stats == {}

    def test_clean_patterns_applied(self):
        pages = {1: "Hello (Order #123) world"}
        stats_without = build_page_text_stats(pages, [])
        stats_with = build_page_text_stats(pages, [r"\(Order #\d+\)"])
        # After cleaning, char count should be smaller
        assert stats_with[1]["char_count"] < stats_without[1]["char_count"]

    def test_text_tokens_positive(self):
        pages = {1: "Some actual text content here"}
        stats = build_page_text_stats(pages, [])
        assert stats[1]["text_tokens"] > 0
