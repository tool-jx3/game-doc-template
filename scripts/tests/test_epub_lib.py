"""Tests for _epub_lib module."""

import pytest
from pathlib import PurePosixPath

from _epub_lib import (
    EPUB_DOCUMENT_MEDIA_TYPES,
    SAFE_FILENAME_RE,
    build_epub_image_filename,
    normalize_epub_internal_path,
    sanitize_filename_component,
    should_print_progress,
)


# ---------------------------------------------------------------------------
# normalize_epub_internal_path
# ---------------------------------------------------------------------------


class TestNormalizeEpubInternalPath:
    def test_simple_relative(self):
        result = normalize_epub_internal_path(PurePosixPath("OEBPS"), "chapter1.xhtml")
        assert result == "OEBPS/chapter1.xhtml"

    def test_dot_base(self):
        result = normalize_epub_internal_path(PurePosixPath("."), "chapter1.xhtml")
        assert result == "chapter1.xhtml"

    def test_empty_base(self):
        result = normalize_epub_internal_path(PurePosixPath(""), "chapter1.xhtml")
        assert result == "chapter1.xhtml"

    def test_strips_fragment(self):
        result = normalize_epub_internal_path(PurePosixPath("OEBPS"), "ch1.xhtml#section2")
        assert result == "OEBPS/ch1.xhtml"

    def test_strips_query(self):
        result = normalize_epub_internal_path(PurePosixPath("OEBPS"), "ch1.xhtml?v=1")
        assert result == "OEBPS/ch1.xhtml"

    def test_strips_fragment_and_query(self):
        result = normalize_epub_internal_path(PurePosixPath("OEBPS"), "ch1.xhtml?v=1#s")
        assert result == "OEBPS/ch1.xhtml"

    def test_url_decoding(self):
        result = normalize_epub_internal_path(PurePosixPath("OEBPS"), "my%20file.xhtml")
        assert result == "OEBPS/my file.xhtml"

    def test_empty_href(self):
        result = normalize_epub_internal_path(PurePosixPath("OEBPS"), "")
        assert result == ""

    def test_fragment_only(self):
        result = normalize_epub_internal_path(PurePosixPath("OEBPS"), "#section")
        assert result == ""

    def test_parent_traversal(self):
        result = normalize_epub_internal_path(PurePosixPath("OEBPS/text"), "../images/fig.png")
        assert result == "OEBPS/images/fig.png"

    def test_nested_base(self):
        result = normalize_epub_internal_path(PurePosixPath("OEBPS/content"), "ch1.xhtml")
        assert result == "OEBPS/content/ch1.xhtml"

    def test_whitespace_stripped(self):
        result = normalize_epub_internal_path(PurePosixPath("OEBPS"), "  ch1.xhtml  ")
        assert result == "OEBPS/ch1.xhtml"


# ---------------------------------------------------------------------------
# sanitize_filename_component
# ---------------------------------------------------------------------------


class TestSanitizeFilenameComponent:
    def test_simple_name(self):
        assert sanitize_filename_component("hello") == "hello"

    def test_spaces_replaced(self):
        assert sanitize_filename_component("my image") == "my_image"

    def test_special_chars(self):
        assert sanitize_filename_component("fig (1)") == "fig_1"

    def test_unicode_replaced(self):
        # "圖片" -> "_" after regex, strip("._") -> "", fallback to "image"
        assert sanitize_filename_component("圖片") == "image"

    def test_dots_and_dashes_kept(self):
        assert sanitize_filename_component("my-file.v2") == "my-file.v2"

    def test_empty_string(self):
        assert sanitize_filename_component("") == "image"

    def test_only_special_chars(self):
        assert sanitize_filename_component("!!!") == "image"

    def test_leading_trailing_dots_stripped(self):
        assert sanitize_filename_component(".hidden.") == "hidden"


# ---------------------------------------------------------------------------
# build_epub_image_filename
# ---------------------------------------------------------------------------


class TestBuildEpubImageFilename:
    def test_basic(self):
        result = build_epub_image_filename(1, 0, "OEBPS/images/figure1.png")
        assert result == "page001_img00_figure1.png"

    def test_no_extension(self):
        result = build_epub_image_filename(2, 1, "OEBPS/images/noext")
        assert result == "page002_img01_noext.bin"

    def test_uppercase_extension_lowered(self):
        result = build_epub_image_filename(3, 0, "images/Photo.JPG")
        assert result == "page003_img00_Photo.jpg"

    def test_special_chars_in_stem(self):
        result = build_epub_image_filename(1, 0, "images/my image (1).png")
        assert result == "page001_img00_my_image_1.png"

    def test_large_page_numbers(self):
        result = build_epub_image_filename(999, 99, "x/fig.png")
        assert result == "page999_img99_fig.png"


# ---------------------------------------------------------------------------
# should_print_progress
# ---------------------------------------------------------------------------


class TestShouldPrintProgress:
    def test_first_page(self):
        assert should_print_progress(1, 100, 10) is True

    def test_last_page(self):
        assert should_print_progress(100, 100, 10) is True

    def test_interval_hit(self):
        assert should_print_progress(20, 100, 10) is True

    def test_interval_miss(self):
        assert should_print_progress(3, 100, 10) is False

    def test_single_page(self):
        # page 1 is both first and last
        assert should_print_progress(1, 1, 5) is True


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


class TestConstants:
    def test_epub_document_media_types(self):
        assert "application/xhtml+xml" in EPUB_DOCUMENT_MEDIA_TYPES
        assert "text/html" in EPUB_DOCUMENT_MEDIA_TYPES

    def test_safe_filename_re(self):
        assert SAFE_FILENAME_RE.sub("_", "hello world!") == "hello_world_"
        assert SAFE_FILENAME_RE.sub("_", "safe-name.txt") == "safe-name.txt"
