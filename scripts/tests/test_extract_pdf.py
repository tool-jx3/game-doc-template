"""Tests for functions remaining in extract_pdf.py."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from extract_pdf import (
    build_image_filename,
    build_output_stem,
    detect_source_type,
    normalize_layout_profile,
    normalize_page_text_engine,
    write_full_markdown,
)
from _epub_lib import should_print_progress


# ---------------------------------------------------------------------------
# normalize_page_text_engine
# ---------------------------------------------------------------------------


class TestNormalizePageTextEngine:
    def test_valid_values(self):
        assert normalize_page_text_engine("auto") == "auto"
        assert normalize_page_text_engine("ocr") == "ocr"
        assert normalize_page_text_engine("pymupdf") == "pymupdf"
        assert normalize_page_text_engine("markitdown") == "markitdown"

    def test_alias_fitz(self):
        assert normalize_page_text_engine("fitz") == "pymupdf"

    def test_alias_markdown(self):
        assert normalize_page_text_engine("markdown") == "markitdown"

    def test_case_insensitive(self):
        assert normalize_page_text_engine("PyMuPDF") == "pymupdf"
        assert normalize_page_text_engine("AUTO") == "auto"
        assert normalize_page_text_engine("FITZ") == "pymupdf"

    def test_strips_whitespace(self):
        assert normalize_page_text_engine("  pymupdf  ") == "pymupdf"

    def test_none_returns_none(self):
        assert normalize_page_text_engine(None) is None

    def test_invalid_returns_none(self):
        assert normalize_page_text_engine("invalid") is None
        assert normalize_page_text_engine("") is None
        assert normalize_page_text_engine(123) is None


# ---------------------------------------------------------------------------
# normalize_layout_profile
# ---------------------------------------------------------------------------


class TestNormalizeLayoutProfile:
    def test_valid_values(self):
        assert normalize_layout_profile("auto") == "auto"
        assert normalize_layout_profile("single-column") == "single-column"
        assert normalize_layout_profile("double-column") == "double-column"

    def test_aliases(self):
        assert normalize_layout_profile("single") == "single-column"
        assert normalize_layout_profile("single_column") == "single-column"
        assert normalize_layout_profile("double") == "double-column"
        assert normalize_layout_profile("double_column") == "double-column"
        assert normalize_layout_profile("two-column") == "double-column"
        assert normalize_layout_profile("two_column") == "double-column"

    def test_case_insensitive(self):
        assert normalize_layout_profile("Double-Column") == "double-column"
        assert normalize_layout_profile("SINGLE") == "single-column"

    def test_strips_whitespace(self):
        assert normalize_layout_profile("  auto  ") == "auto"

    def test_none_returns_none(self):
        assert normalize_layout_profile(None) is None

    def test_invalid_returns_none(self):
        assert normalize_layout_profile("triple-column") is None
        assert normalize_layout_profile("") is None


# ---------------------------------------------------------------------------
# detect_source_type
# ---------------------------------------------------------------------------


class TestDetectSourceType:
    def test_pdf(self):
        assert detect_source_type(Path("book.pdf")) == "pdf"

    def test_pdf_uppercase(self):
        assert detect_source_type(Path("BOOK.PDF")) == "pdf"

    def test_epub(self):
        assert detect_source_type(Path("book.epub")) == "epub"

    def test_epub_uppercase(self):
        assert detect_source_type(Path("BOOK.EPUB")) == "epub"

    def test_image_file(self):
        assert detect_source_type(Path("page.JPG")) == "image"

    def test_image_directory(self, tmp_path):
        (tmp_path / "page2.jpg").write_text("x", encoding="utf-8")
        (tmp_path / "page10.jpg").write_text("x", encoding="utf-8")
        assert detect_source_type(tmp_path) == "image-dir"

    def test_unsupported_extension(self):
        with pytest.raises(SystemExit):
            detect_source_type(Path("book.docx"))

    def test_no_extension(self):
        with pytest.raises(SystemExit):
            detect_source_type(Path("book"))


# ---------------------------------------------------------------------------
# should_print_progress
# ---------------------------------------------------------------------------


class TestShouldPrintProgress:
    def test_first_page_always(self):
        assert should_print_progress(1, 100, 25) is True

    def test_last_page_always(self):
        assert should_print_progress(100, 100, 25) is True

    def test_interval_match(self):
        assert should_print_progress(25, 100, 25) is True
        assert should_print_progress(50, 100, 25) is True
        assert should_print_progress(75, 100, 25) is True

    def test_non_interval(self):
        assert should_print_progress(2, 100, 25) is False
        assert should_print_progress(13, 100, 25) is False
        assert should_print_progress(99, 100, 25) is False


# ---------------------------------------------------------------------------
# build_image_filename
# ---------------------------------------------------------------------------


class TestBuildImageFilename:
    def test_with_rect(self):
        rect = SimpleNamespace(x0=10.4, y0=20.6, width=100.3, height=200.7)
        result = build_image_filename(1, 0, 0, rect, "png")
        assert result == "page001_img00_occ00_x10_y21_w100_h201.png"

    def test_without_rect(self):
        result = build_image_filename(1, 0, 0, None, "png")
        assert result == "page001_img00_occ00.png"

    def test_multi_digit_indices(self):
        result = build_image_filename(12, 3, 1, None, "jpg")
        assert result == "page012_img03_occ01.jpg"

    def test_with_rect_zero_coords(self):
        rect = SimpleNamespace(x0=0.0, y0=0.0, width=50.0, height=50.0)
        result = build_image_filename(1, 0, 0, rect, "png")
        assert result == "page001_img00_occ00_x0_y0_w50_h50.png"


class TestBuildOutputStem:
    def test_file_uses_stem(self):
        assert build_output_stem(Path("book.pdf"), "pdf") == "book"

    def test_directory_uses_name(self, tmp_path):
        scan_dir = tmp_path / "scan-pages"
        scan_dir.mkdir()
        assert build_output_stem(scan_dir, "image-dir") == "scan-pages"


class TestWriteFullMarkdown:
    def test_skips_empty_pages_and_joins_sections(self, tmp_path):
        output = tmp_path / "book.md"
        result = write_full_markdown(output, ["First page", "", "Second page"], "ocr")
        assert result == output
        assert output.read_text(encoding="utf-8") == "First page\n\nSecond page\n"
