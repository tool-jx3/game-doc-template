from __future__ import annotations

import argparse
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import _term_lib as tl
import _style_decisions_lib as sdl
import clean_sample_data as csd
import draft as dr
import extract_pdf as ep
import init_create_progress as icp
import init_handoff_gate as ihg
import split_chapters as sc
import style_decisions as sd
import term_edit as te
import term_generate as tg
import term_read as tr
import validate_style_decisions as vsd
import validate_glossary as vg


class TestCleanSampleData(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.markdown_dir = self.root / "data" / "markdown"
        self.docs_dir = self.root / "docs" / "src" / "content" / "docs"
        self.glossary_path = self.root / "glossary.json"
        self.markdown_dir.mkdir(parents=True)
        self.docs_dir.mkdir(parents=True)

        self.patchers = [
            patch.object(csd, "PROJECT_ROOT", self.root),
            patch.object(csd, "MARKDOWN_DIR", self.markdown_dir),
            patch.object(csd, "DOCS_CONTENT_DIR", self.docs_dir),
            patch.object(csd, "GLOSSARY_PATH", self.glossary_path),
        ]
        for p in self.patchers:
            p.start()

    def tearDown(self) -> None:
        for p in reversed(self.patchers):
            p.stop()
        self.tmp.cleanup()

    def test_clean_markdown_data_apply_removes_non_gitkeep(self) -> None:
        (self.markdown_dir / ".gitkeep").write_text("", encoding="utf-8")
        (self.markdown_dir / "a.md").write_text("x", encoding="utf-8")
        sub = self.markdown_dir / "images"
        sub.mkdir()
        (sub / "i.png").write_text("x", encoding="utf-8")

        csd.clean_markdown_data(apply=True)

        self.assertTrue((self.markdown_dir / ".gitkeep").exists())
        self.assertFalse((self.markdown_dir / "a.md").exists())
        self.assertFalse(sub.exists())

    def test_clean_docs_content_only_removes_md_and_mdx(self) -> None:
        (self.docs_dir / "a.md").write_text("x", encoding="utf-8")
        (self.docs_dir / "b.mdx").write_text("x", encoding="utf-8")
        (self.docs_dir / "c.txt").write_text("x", encoding="utf-8")

        csd.clean_docs_content(apply=True)

        self.assertFalse((self.docs_dir / "a.md").exists())
        self.assertFalse((self.docs_dir / "b.mdx").exists())
        self.assertTrue((self.docs_dir / "c.txt").exists())

    def test_clean_glossary_resets_to_meta_only(self) -> None:
        self.glossary_path.write_text(
            json.dumps(
                {
                    "_meta": {"description": "custom", "updated": "now"},
                    "Move": {"zh": "動作"},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        csd.clean_glossary(apply=True)
        payload = json.loads(self.glossary_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["_meta"]["description"], "custom")
        self.assertEqual(payload["_meta"]["updated"], "")
        self.assertEqual(set(payload.keys()), {"_meta"})


class TestExtractPdf(unittest.TestCase):
    @staticmethod
    def _create_sample_epub(root: Path) -> Path:
        epub_path = root / "sample.epub"
        container_xml = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""
        content_opf = """<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>Sample</dc:title>
    <dc:identifier id="bookid">sample-book</dc:identifier>
  </metadata>
  <manifest>
    <item id="chap1" href="chap1.xhtml" media-type="application/xhtml+xml"/>
    <item id="chap2" href="chap2.xhtml" media-type="application/xhtml+xml"/>
    <item id="art" href="image/art.png" media-type="image/png"/>
  </manifest>
  <spine>
    <itemref idref="chap1"/>
    <itemref idref="chap2"/>
  </spine>
</package>
"""
        chapter_xhtml = """<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml"><body><p>placeholder</p></body></html>
"""
        with zipfile.ZipFile(epub_path, "w") as archive:
            archive.writestr("mimetype", "application/epub+zip")
            archive.writestr("META-INF/container.xml", container_xml)
            archive.writestr("OEBPS/content.opf", content_opf)
            archive.writestr("OEBPS/chap1.xhtml", chapter_xhtml)
            archive.writestr("OEBPS/chap2.xhtml", chapter_xhtml)
            archive.writestr("OEBPS/image/art.png", b"pngdata")
        return epub_path

    def test_parse_args_defaults_to_auto_strategy(self) -> None:
        with patch.object(sys, "argv", ["extract_pdf.py", "sample.pdf"]):
            args = ep.parse_args()
        self.assertEqual(args.page_text_engine, "auto")
        self.assertEqual(args.layout_profile, "auto")
        self.assertFalse(args.skip_full_markitdown)

    def test_detect_source_type_supports_epub(self) -> None:
        self.assertEqual(ep.detect_source_type(Path("sample.epub")), "epub")

    def test_classify_page_layout_detects_double_column(self) -> None:
        words = []
        for line_no in range(8):
            y = 10 + line_no * 12
            left_words = ["left", "column", "body", "sample", "text"]
            right_words = ["right", "column", "body", "sample", "text"]
            for word_no, word in enumerate(left_words):
                x0 = 20 + word_no * 28
                words.append((x0, y, x0 + 26, y + 8, word, 0, line_no, word_no))
            for word_no, word in enumerate(right_words):
                x0 = 240 + word_no * 28
                words.append((x0, y, x0 + 26, y + 8, word, 1, line_no, word_no))

        result = ep.classify_page_layout(words, page_width=400)
        self.assertEqual(result["layout_profile"], "double-column")

    def test_classify_page_layout_detects_single_column(self) -> None:
        words = []
        for line_no in range(8):
            y = 10 + line_no * 12
            line_words = ["single", "column", "body", "sample", "text", "continues", "here"]
            for word_no, word in enumerate(line_words):
                x0 = 20 + word_no * 50
                words.append((x0, y, x0 + 40, y + 8, word, 0, line_no, word_no))

        result = ep.classify_page_layout(words, page_width=400)
        self.assertEqual(result["layout_profile"], "single-column")

    def test_analyze_pymupdf_text_noise_flags_layout_noise(self) -> None:
        noisy_text = "\n".join(
            f"Body text line {i}                Sidebar Heading" for i in range(20)
        )
        clean_text = "\n".join(
            f"This is a normal body line number {i} with regular spacing." for i in range(20)
        )

        noisy = ep.analyze_pymupdf_text_noise(noisy_text)
        clean = ep.analyze_pymupdf_text_noise(clean_text)

        self.assertTrue(noisy["is_noisy"])
        self.assertGreater(noisy["whitespace_ratio"], 0.08)
        self.assertFalse(clean["is_noisy"])

    def test_load_document_extraction_settings_prefers_per_document(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "style-decisions.json").write_text(
                json.dumps(
                    {
                        "document_format": {
                            "layout_profile": "single-column",
                            "documents": {
                                "Household_1.2": {
                                    "layout_profile": "double-column",
                                    "page_text_engine": "markitdown",
                                }
                            },
                        }
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            settings = ep.load_document_extraction_settings(root, "Household_1.2")
        self.assertEqual(settings["layout_profile"], "double-column")
        self.assertEqual(settings["page_text_engine"], "markitdown")

    def test_resolve_page_text_strategy_uses_document_override(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            pdf_path = root / "Household_1.2.pdf"
            pdf_path.write_bytes(b"pdf")
            (root / "style-decisions.json").write_text(
                json.dumps(
                    {
                        "document_format": {
                            "documents": {
                                "Household_1.2": {
                                    "layout_profile": "double-column",
                                    "page_text_engine": "markitdown",
                                }
                            }
                        }
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            with patch.object(ep, "MarkItDown", object()):
                strategy = ep.resolve_page_text_strategy(
                    pdf_path,
                    root,
                    requested_engine="auto",
                    requested_layout="auto",
                )
        self.assertEqual(strategy["layout_profile"], "double-column")
        self.assertEqual(strategy["page_text_engine"], "markitdown")
        self.assertEqual(strategy["page_text_engine_source"], "style-decisions")

    def test_resolve_page_text_strategy_auto_detects_double_column(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            pdf_path = root / "sample.pdf"
            pdf_path.write_bytes(b"pdf")
            with (
                patch.object(ep, "MarkItDown", object()),
                patch.object(
                    ep,
                    "detect_layout_profile",
                    return_value={
                        "layout_profile": "double-column",
                        "confidence": 0.9,
                        "source": "auto-detect",
                        "sampled_pages": [{"page": 20, "layout_profile": "double-column"}],
                    },
                ),
            ):
                strategy = ep.resolve_page_text_strategy(
                    pdf_path,
                    root,
                    requested_engine="auto",
                    requested_layout="auto",
                )
        self.assertEqual(strategy["layout_profile"], "double-column")
        self.assertEqual(strategy["page_text_engine"], "markitdown")
        self.assertEqual(strategy["layout_profile_source"], "auto-detect")

    def test_resolve_page_text_strategy_prefers_markitdown_when_pymupdf_probe_is_noisy(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            pdf_path = root / "sample.pdf"
            pdf_path.write_bytes(b"pdf")
            with (
                patch.object(ep, "MarkItDown", object()),
                patch.object(
                    ep,
                    "detect_layout_profile",
                    return_value={
                        "layout_profile": "single-column",
                        "confidence": 0.9,
                        "source": "auto-detect",
                        "sampled_pages": [{"page": 20, "layout_profile": "single-column"}],
                    },
                ),
                patch.object(
                    ep,
                    "probe_pymupdf_text_quality",
                    return_value={
                        "prefer_markitdown": True,
                        "source": "pymupdf-quality-probe",
                        "sampled_pages": [{"page": 20, "is_noisy": True, "whitespace_ratio": 0.22}],
                        "informative_pages": 6,
                        "noisy_pages": 4,
                        "required_noisy_pages": 2,
                    },
                ),
            ):
                strategy = ep.resolve_page_text_strategy(
                    pdf_path,
                    root,
                    requested_engine="auto",
                    requested_layout="auto",
                )
        self.assertEqual(strategy["layout_profile"], "single-column")
        self.assertEqual(strategy["page_text_engine"], "markitdown")
        self.assertEqual(strategy["page_text_engine_source"], "pymupdf-quality-probe")
        self.assertTrue(strategy["quality_probe"]["prefer_markitdown"])

    def test_resolve_page_text_strategy_keeps_pymupdf_when_pymupdf_probe_is_clean(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            pdf_path = root / "sample.pdf"
            pdf_path.write_bytes(b"pdf")
            with (
                patch.object(ep, "MarkItDown", object()),
                patch.object(
                    ep,
                    "detect_layout_profile",
                    return_value={
                        "layout_profile": "single-column",
                        "confidence": 0.9,
                        "source": "auto-detect",
                        "sampled_pages": [{"page": 20, "layout_profile": "single-column"}],
                    },
                ),
                patch.object(
                    ep,
                    "probe_pymupdf_text_quality",
                    return_value={
                        "prefer_markitdown": False,
                        "source": "pymupdf-quality-probe",
                        "sampled_pages": [{"page": 20, "is_noisy": False, "whitespace_ratio": 0.0}],
                        "informative_pages": 6,
                        "noisy_pages": 0,
                        "required_noisy_pages": 2,
                    },
                ),
            ):
                strategy = ep.resolve_page_text_strategy(
                    pdf_path,
                    root,
                    requested_engine="auto",
                    requested_layout="auto",
                )
        self.assertEqual(strategy["layout_profile"], "single-column")
        self.assertEqual(strategy["page_text_engine"], "pymupdf")
        self.assertEqual(strategy["page_text_engine_source"], "layout-profile")
        self.assertFalse(strategy["quality_probe"]["prefer_markitdown"])

    def test_resolve_page_text_strategy_defaults_for_epub(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            epub_path = self._create_sample_epub(root)
            strategy = ep.resolve_page_text_strategy(
                epub_path,
                root,
                requested_engine="auto",
                requested_layout="auto",
            )
        self.assertEqual(strategy["source_type"], "epub")
        self.assertEqual(strategy["page_text_engine"], "markitdown")
        self.assertEqual(strategy["page_text_engine_source"], "epub-default")
        self.assertEqual(strategy["layout_profile_source"], "epub-default")

    def test_extract_with_markitdown_missing_dependency(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            with patch.object(ep, "MarkItDown", None):
                result = ep.extract_with_markitdown(Path("sample.pdf"), out)
            self.assertIsNone(result)

    def test_extract_with_markitdown_writes_output(self) -> None:
        class FakeResult:
            text_content = "hello"

        class FakeMarkItDown:
            def convert(self, _: str) -> FakeResult:
                return FakeResult()

        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            with patch.object(ep, "MarkItDown", FakeMarkItDown):
                result = ep.extract_with_markitdown(Path("sample.pdf"), out)
            self.assertIsNotNone(result)
            self.assertEqual(result.read_text(encoding="utf-8"), "hello")

    def test_extract_with_pages_writes_page_markers(self) -> None:
        class FakePage:
            def __init__(self, text: str) -> None:
                self.text = text

            def get_text(self, mode: str = "text", sort: bool = True) -> str:
                return self.text

        class FakeDoc(list):
            def close(self) -> None:
                pass

        class FakePyMuPDF:
            @staticmethod
            def open(_: str) -> FakeDoc:
                return FakeDoc([FakePage("p1"), FakePage("p2")])

        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            with patch.object(ep, "pymupdf", FakePyMuPDF):
                result = ep.extract_with_pages(Path("sample.pdf"), out)
            content = result.read_text(encoding="utf-8")
            self.assertIn("<!-- PAGE 1 -->", content)
            self.assertIn("<!-- PAGE 2 -->", content)
            self.assertIn("p1", content)
            self.assertIn("p2", content)

    def test_extract_with_pages_markitdown_engine_writes_page_markers(self) -> None:
        page_texts = ["p1", "p2"]

        class FakeDoc(list):
            def close(self) -> None:
                pass

        class FakeSingleDoc:
            def insert_pdf(self, doc: object, from_page: int = 0, to_page: int = 0) -> None:
                self._page_idx = from_page

            def save(self, path: str) -> None:
                Path(path).write_text(f"fake-pdf-{self._page_idx}", encoding="utf-8")

            def close(self) -> None:
                pass

        class FakePyMuPDF:
            @staticmethod
            def open(path: str | None = None) -> FakeDoc | FakeSingleDoc:
                if path is not None:
                    return FakeDoc([None, None])  # 2 pages
                return FakeSingleDoc()

        class FakeResult:
            def __init__(self, text: str) -> None:
                self.text_content = text

        call_count = 0

        class FakeMarkItDown:
            def convert(self, path: str) -> FakeResult:
                nonlocal call_count
                text = page_texts[call_count]
                call_count += 1
                return FakeResult(text)

        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            with patch.object(ep, "pymupdf", FakePyMuPDF), \
                 patch.object(ep, "MarkItDown", FakeMarkItDown):
                result = ep.extract_with_pages(Path("sample.pdf"), out, page_text_engine="markitdown")
            content = result.read_text(encoding="utf-8")
            self.assertIn("<!-- PAGE 1 -->", content)
            self.assertIn("<!-- PAGE 2 -->", content)

    def test_extract_with_pages_epub_writes_virtual_page_markers(self) -> None:
        markdown_by_name = {
            "chap1.xhtml": "# Intro\nAlpha\n![art](image/art.png)\n## Details\nBeta",
            "chap2.xhtml": "# Outro\nGamma",
        }

        class FakeResult:
            def __init__(self, text: str) -> None:
                self.text_content = text

        class FakeMarkItDown:
            def convert(self, path: str) -> FakeResult:
                return FakeResult(markdown_by_name[Path(path).name])

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            epub_path = self._create_sample_epub(root)
            out = root / "out"
            out.mkdir()
            with patch.object(ep, "MarkItDown", FakeMarkItDown):
                result = ep.extract_with_pages(epub_path, out)
            content = result.read_text(encoding="utf-8")
            self.assertIn("<!-- PAGE 1 -->", content)
            self.assertIn("<!-- PAGE 2 -->", content)
            self.assertIn("<!-- PAGE 3 -->", content)
            self.assertIn("# Intro", content)
            self.assertIn("## Details", content)
            self.assertNotIn("![art]", content)

    def test_extract_images_writes_files_and_manifest(self) -> None:
        class FakeRect:
            def __init__(self, x0: float, y0: float, width: float, height: float) -> None:
                self.x0 = x0
                self.y0 = y0
                self.width = width
                self.height = height

        class FakePageRect:
            def __init__(self, width: float, height: float) -> None:
                self.width = width
                self.height = height

        class FakePage:
            rect = FakePageRect(100, 200)

            def get_images(self, full: bool = False) -> list[tuple[int]]:
                return [(1,), (2,)]

            def get_image_rects(self, xref: int, transform: bool = False) -> list[FakeRect]:
                return [FakeRect(10 * xref, 20 * xref, 30 * xref, 40 * xref)]

        class FakeDoc(list):
            def extract_image(self, xref: int) -> dict[str, object]:
                return {"image": f"img{xref}".encode("utf-8"), "ext": "png"}

            def close(self) -> None:
                pass

        class FakePyMuPDF:
            @staticmethod
            def open(_: str) -> FakeDoc:
                return FakeDoc([FakePage()])

        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            with (
                patch.object(ep, "pymupdf", FakePyMuPDF),
                patch.object(
                    ep,
                    "analyze_image_bytes",
                    side_effect=[
                        {
                            "visual_hash": "1111",
                            "dominant_color_ratio": 0.91,
                            "sampled_pixel_count": 64,
                        },
                        {
                            "visual_hash": "2222",
                            "dominant_color_ratio": 0.34,
                            "sampled_pixel_count": 64,
                        },
                    ],
                ),
            ):
                images = ep.extract_images(Path("sample.pdf"), out)
            self.assertEqual(len(images), 2)
            manifest = json.loads(
                (out / "images" / "sample" / "manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(len(manifest["images"]), 2)
            self.assertEqual(manifest["images"][0]["page"], 1)
            self.assertEqual(manifest["images"][0]["x"], 10)
            self.assertEqual(manifest["images"][0]["file_size"], 4)
            self.assertEqual(manifest["images"][0]["visual_hash"], "1111")
            self.assertEqual(manifest["images"][0]["coverage_ratio"], 0.06)
            self.assertTrue(
                (out / "images" / "sample" / manifest["images"][0]["filename"]).exists()
            )

    def test_extract_images_epub_writes_files_and_manifest(self) -> None:
        markdown_by_name = {
            "chap1.xhtml": "# Intro\nAlpha\n![art](image/art.png)\n## Details\nBeta",
            "chap2.xhtml": "# Outro\nGamma",
        }

        class FakeResult:
            def __init__(self, text: str) -> None:
                self.text_content = text

        class FakeMarkItDown:
            def convert(self, path: str) -> FakeResult:
                return FakeResult(markdown_by_name[Path(path).name])

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            epub_path = self._create_sample_epub(root)
            out = root / "out"
            out.mkdir()
            with (
                patch.object(ep, "MarkItDown", FakeMarkItDown),
                patch.object(
                    ep,
                    "analyze_image_bytes",
                    return_value={
                        "visual_hash": "abcd",
                        "dominant_color_ratio": 0.5,
                        "sampled_pixel_count": 64,
                    },
                ),
            ):
                images = ep.extract_images(epub_path, out)

            self.assertEqual(len(images), 1)
            manifest = json.loads(
                (out / "images" / "sample" / "manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["source_type"], "epub")
            self.assertEqual(manifest["images"][0]["page"], 1)
            self.assertEqual(manifest["images"][0]["source_path"], "OEBPS/image/art.png")
            self.assertEqual(manifest["images"][0]["visual_hash"], "abcd")
            self.assertTrue(
                (out / "images" / "sample" / manifest["images"][0]["filename"]).exists()
            )


class TestDraftWorkflow(unittest.TestCase):
    def test_cmd_path_creates_empty_draft_and_manifest_entry(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with patch.object(dr, "ROOT", root):
                dr.cmd_path("docs/src/content/docs/rules/basic.md", "translate")
            draft = (
                root
                / ".claude"
                / "skills"
                / "translate"
                / ".state"
                / "drafts"
                / "docs"
                / "src"
                / "content"
                / "docs"
                / "rules"
                / "basic.md"
            )
            self.assertTrue(draft.exists())
            self.assertEqual(draft.read_text(encoding="utf-8"), "")
            manifest = json.loads(
                (
                    root
                    / ".claude"
                    / "skills"
                    / "translate"
                    / ".state"
                    / "draft-manifest.json"
                ).read_text(encoding="utf-8")
            )
            self.assertIn("docs/src/content/docs/rules/basic.md", manifest["entries"])

    def test_cmd_writeback_uses_manifest_and_removes_entry(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "docs" / "src" / "content" / "docs" / "rules" / "basic.md"
            draft = (
                root
                / ".claude"
                / "skills"
                / "translate"
                / ".state"
                / "drafts"
                / "docs"
                / "src"
                / "content"
                / "docs"
                / "rules"
                / "basic.md"
            )
            draft.parent.mkdir(parents=True, exist_ok=True)
            draft.write_text("---\ntitle: 測試\n---\n內容\n", encoding="utf-8")
            manifest_path = root / ".claude" / "skills" / "translate" / ".state" / "draft-manifest.json"
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "entries": {
                            "docs/src/content/docs/rules/basic.md": {
                                "source": "docs/src/content/docs/rules/basic.md",
                                "draft": ".claude/skills/translate/.state/drafts/docs/src/content/docs/rules/basic.md",
                                "updated": "2026-03-09T00:00:00+00:00",
                            }
                        }
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            with patch.object(dr, "ROOT", root):
                dr.cmd_writeback("docs/src/content/docs/rules/basic.md", "translate")
            self.assertTrue(source.exists())
            self.assertEqual(
                source.read_text(encoding="utf-8"),
                "---\ntitle: 測試\n---\n內容\n",
            )
            self.assertFalse(draft.exists())
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["entries"], {})

    def test_cmd_writeback_uses_manifest_draft_path(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "docs" / "src" / "content" / "docs" / "rules" / "basic.md"
            draft = root / "custom-drafts" / "basic.md"
            draft.parent.mkdir(parents=True, exist_ok=True)
            draft.write_text("內容\n", encoding="utf-8")
            manifest_path = root / ".claude" / "skills" / "translate" / ".state" / "draft-manifest.json"
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "entries": {
                            "docs/src/content/docs/rules/basic.md": {
                                "source": "docs/src/content/docs/rules/basic.md",
                                "draft": "custom-drafts/basic.md",
                                "updated": "2026-03-09T00:00:00+00:00",
                            }
                        }
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            with patch.object(dr, "ROOT", root):
                dr.cmd_writeback("docs/src/content/docs/rules/basic.md", "translate")
            self.assertTrue(source.exists())
            self.assertEqual(source.read_text(encoding="utf-8"), "內容\n")
            self.assertFalse(draft.exists())

    def test_cmd_writeback_preserves_image_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "docs" / "src" / "content" / "docs" / "rules" / "basic.md"
            draft = (
                root
                / ".claude"
                / "skills"
                / "translate"
                / ".state"
                / "drafts"
                / "docs"
                / "src"
                / "content"
                / "docs"
                / "rules"
                / "basic.md"
            )
            draft.parent.mkdir(parents=True, exist_ok=True)
            expected = (
                "---\n"
                "title: 測試\n"
                "---\n"
                "段落前。\n\n"
                "![第 1 頁插圖](../../assets/extracted/book/page001_img00.png)\n\n"
                "段落後。\n"
            )
            draft.write_text(expected, encoding="utf-8")
            manifest_path = root / ".claude" / "skills" / "translate" / ".state" / "draft-manifest.json"
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "entries": {
                            "docs/src/content/docs/rules/basic.md": {
                                "source": "docs/src/content/docs/rules/basic.md",
                                "draft": ".claude/skills/translate/.state/drafts/docs/src/content/docs/rules/basic.md",
                                "updated": "2026-03-09T00:00:00+00:00",
                            }
                        }
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            with patch.object(dr, "ROOT", root):
                dr.cmd_writeback("docs/src/content/docs/rules/basic.md", "translate")
            self.assertEqual(source.read_text(encoding="utf-8"), expected)

    def test_cmd_writeback_fails_without_manifest_entry(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            draft = (
                root
                / ".claude"
                / "skills"
                / "translate"
                / ".state"
                / "drafts"
                / "docs"
                / "src"
                / "content"
                / "docs"
                / "rules"
                / "basic.md"
            )
            draft.parent.mkdir(parents=True, exist_ok=True)
            draft.write_text("內容\n", encoding="utf-8")
            with patch.object(dr, "ROOT", root):
                with self.assertRaises(SystemExit):
                    dr.cmd_writeback("docs/src/content/docs/rules/basic.md", "translate")


class TestStyleDecisions(unittest.TestCase):
    def test_cmd_init_creates_default_file(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            style_path = root / "style-decisions.json"
            schema_path = root / "style-decisions.schema.json"
            schema_path.write_text(
                (ROOT / "style-decisions.schema.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )

            args = argparse.Namespace(
                style=style_path,
                schema=schema_path,
                force=False,
                description="測試 style decisions",
            )
            sd.cmd_init(args)

            payload = json.loads(style_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["_meta"]["description"], "測試 style decisions")
            self.assertEqual(payload["translation_mode"]["mode"], "full")

    def test_cmd_set_document_format_for_document(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            style_path = root / "style-decisions.json"
            schema_path = root / "style-decisions.schema.json"
            schema_path.write_text(
                (ROOT / "style-decisions.schema.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            sdl.save_style_decisions(
                style_path,
                sdl.default_style_decisions_payload(),
                schema_path=schema_path,
            )

            args = argparse.Namespace(
                style=style_path,
                schema=schema_path,
                document_key="Household_1.2",
                layout_profile="double-column",
                page_text_engine="markitdown",
                aside_note=None,
                aside_tip=None,
                aside_caution=None,
                aside_danger=None,
                cards_usage=None,
                tabs_usage=None,
                tables_convention=None,
                dice_tables_convention=None,
            )
            sd.cmd_set_document_format(args)

            payload = json.loads(style_path.read_text(encoding="utf-8"))
            entry = payload["document_format"]["documents"]["Household_1.2"]
            self.assertEqual(entry["layout_profile"], "double-column")
            self.assertEqual(entry["page_text_engine"], "markitdown")

    def test_cmd_add_translation_note_upserts_by_key(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            style_path = root / "style-decisions.json"
            schema_path = root / "style-decisions.schema.json"
            schema_path.write_text(
                (ROOT / "style-decisions.schema.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            sdl.save_style_decisions(
                style_path,
                sdl.default_style_decisions_payload(),
                schema_path=schema_path,
            )

            first = argparse.Namespace(
                style=style_path,
                schema=schema_path,
                document_key=None,
                key="tone",
                topic="語氣",
                note="保持冷靜、正式。",
            )
            second = argparse.Namespace(
                style=style_path,
                schema=schema_path,
                document_key=None,
                key="tone",
                topic="語氣",
                note="保持冷靜、正式，避免過度口語。",
            )
            sd.cmd_add_translation_note(first)
            sd.cmd_add_translation_note(second)

            payload = json.loads(style_path.read_text(encoding="utf-8"))
            notes = payload["translation_notes"]["global"]
            self.assertEqual(len(notes), 1)
            self.assertEqual(notes[0]["note"], "保持冷靜、正式，避免過度口語。")

    def test_validate_style_decisions_reports_invalid_payload(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            style_path = root / "style-decisions.json"
            schema_path = root / "style-decisions.schema.json"
            style_path.write_text(
                json.dumps({"_meta": {"description": "x", "updated": ""}, "repository": {"visibility": "internal"}}, ensure_ascii=False),
                encoding="utf-8",
            )
            schema_path.write_text(
                (ROOT / "style-decisions.schema.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )

            args = argparse.Namespace(style=style_path, schema=schema_path)
            with patch.object(vsd, "parse_args", return_value=args):
                with self.assertRaises(SystemExit):
                    vsd.main()


class TestSplitChapters(unittest.TestCase):
    def test_extract_pages(self) -> None:
        content = "<!-- PAGE 1 -->\n\nA\n\n<!-- PAGE 2 -->\n\nB"
        pages = sc.extract_pages(content)
        self.assertEqual(pages[1], "A")
        self.assertEqual(pages[2], "B")

    def test_split_chapters_writes_expected_file(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "data" / "markdown" / "book_pages.md"
            src.parent.mkdir(parents=True)
            src.write_text(
                "<!-- PAGE 1 -->\n\nHello REMOVE\n\n<!-- PAGE 2 -->\n\nWorld",
                encoding="utf-8",
            )
            config = {
                "source": "data/markdown/book_pages.md",
                "output_dir": "docs/src/content/docs",
                "clean_patterns": ["REMOVE"],
                "chapters": {
                    "rules": {
                        "title": "Rules",
                        "order": 1,
                        "files": {
                            "index": {
                                "title": "Overview",
                                "description": "Desc",
                                "pages": [1, 2],
                                "order": 0,
                            }
                        },
                    }
                },
            }

            sc.split_chapters(config, root)
            out = root / "docs" / "src" / "content" / "docs" / "rules" / "index.md"
            data = out.read_text(encoding="utf-8")
            self.assertIn("title: Overview", data)
            self.assertIn("description: Desc", data)
            self.assertIn("Hello", data)
            self.assertNotIn("REMOVE", data)

    def test_split_chapters_copies_images_and_skips_repeated_file_sizes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "data" / "markdown" / "book_pages.md"
            src.parent.mkdir(parents=True)
            src.write_text(
                "<!-- PAGE 1 -->\n\n" + ("Hello world " * 60) + "\n\n<!-- PAGE 2 -->\n\n" + ("World text " * 60) + "\n\n<!-- PAGE 3 -->\n\n" + ("Background page " * 60),
                encoding="utf-8",
            )

            images_dir = root / "data" / "markdown" / "images" / "book"
            images_dir.mkdir(parents=True)
            unique_name = "page001_img00_occ00_x10_y20_w120_h180.png"
            background_name = "page001_img01_occ00_x0_y0_w800_h1000.png"
            repeated_backgrounds = [
                background_name,
                "page002_img01_occ00_x0_y0_w800_h1000.png",
                "page003_img01_occ00_x0_y0_w800_h1000.png",
            ]
            (images_dir / unique_name).write_bytes(b"unique-image")
            for filename in repeated_backgrounds:
                (images_dir / filename).write_bytes(b"same-size")

            manifest = {
                "pdf": "book.pdf",
                "images_dir": "images/book",
                "images": [
                    {
                        "page": 1,
                        "filename": unique_name,
                        "path": f"images/book/{unique_name}",
                        "x": 10,
                        "y": 20,
                        "width": 120,
                        "height": 180,
                        "file_size": len(b"unique-image"),
                    },
                    {
                        "page": 1,
                        "filename": repeated_backgrounds[0],
                        "path": f"images/book/{repeated_backgrounds[0]}",
                        "x": 0,
                        "y": 0,
                        "width": 800,
                        "height": 1000,
                        "coverage_ratio": 0.92,
                        "file_size": len(b"same-size"),
                    },
                    {
                        "page": 2,
                        "filename": repeated_backgrounds[1],
                        "path": f"images/book/{repeated_backgrounds[1]}",
                        "x": 0,
                        "y": 0,
                        "width": 800,
                        "height": 1000,
                        "coverage_ratio": 0.92,
                        "file_size": len(b"same-size"),
                    },
                    {
                        "page": 3,
                        "filename": repeated_backgrounds[2],
                        "path": f"images/book/{repeated_backgrounds[2]}",
                        "x": 0,
                        "y": 0,
                        "width": 800,
                        "height": 1000,
                        "coverage_ratio": 0.92,
                        "file_size": len(b"same-size"),
                    },
                ],
            }
            (images_dir / "manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            config = {
                "source": "data/markdown/book_pages.md",
                "output_dir": "docs/src/content/docs",
                "images": {
                    "enabled": True,
                    "assets_dir": "docs/src/assets/extracted",
                    "repeat_file_size_threshold": 3,
                },
                "chapters": {
                    "rules": {
                        "title": "Rules",
                        "order": 1,
                        "files": {
                            "index": {
                                "title": "Overview",
                                "description": "Desc",
                                "pages": [1, 2],
                                "order": 0,
                            }
                        },
                    }
                },
            }

            sc.split_chapters(config, root)

            out = root / "docs" / "src" / "content" / "docs" / "rules" / "index.md"
            asset = root / "docs" / "src" / "assets" / "extracted" / "book" / unique_name
            data = out.read_text(encoding="utf-8")

            self.assertTrue(asset.exists())
            self.assertIn(f"../../assets/extracted/book/{unique_name}", data)
            self.assertNotIn(repeated_backgrounds[0], data)

    def test_split_chapters_supports_nested_file_paths(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "data" / "markdown" / "book_pages.md"
            src.parent.mkdir(parents=True)
            src.write_text(
                "<!-- PAGE 1 -->\n\nIntro\n\n<!-- PAGE 2 -->\n\nDamage rules",
                encoding="utf-8",
            )
            config = {
                "source": "data/markdown/book_pages.md",
                "output_dir": "docs/src/content/docs",
                "chapters": {
                    "rules": {
                        "title": "Rules",
                        "order": 1,
                        "files": {
                            "combat/damage": {
                                "title": "Damage",
                                "description": "Combat damage rules",
                                "pages": [2, 2],
                                "order": 1,
                            }
                        },
                    }
                },
            }

            sc.split_chapters(config, root)

            out = root / "docs" / "src" / "content" / "docs" / "rules" / "combat" / "damage.md"
            self.assertTrue(out.exists())
            data = out.read_text(encoding="utf-8")
            self.assertIn("title: Damage", data)
            self.assertIn("Damage rules", data)

    def test_split_chapters_skips_repeated_visual_backgrounds(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "data" / "markdown" / "book_pages.md"
            src.parent.mkdir(parents=True)
            src.write_text(
                "<!-- PAGE 1 -->\n\n" + ("Hello world " * 60) + "\n\n<!-- PAGE 2 -->\n\n" + ("World text " * 60),
                encoding="utf-8",
            )

            images_dir = root / "data" / "markdown" / "images" / "book"
            images_dir.mkdir(parents=True)
            foreground_name = "page001_img00_occ00_x10_y20_w120_h180.png"
            background_a = "page001_img01_occ00_x0_y0_w780_h980.png"
            background_b = "page002_img01_occ00_x0_y0_w720_h960.png"
            (images_dir / foreground_name).write_bytes(b"unique-image")
            (images_dir / background_a).write_bytes(b"bg-image-a")
            (images_dir / background_b).write_bytes(b"bg-image-b-larger")

            manifest = {
                "pdf": "book.pdf",
                "images_dir": "images/book",
                "images": [
                    {
                        "page": 1,
                        "filename": foreground_name,
                        "path": f"images/book/{foreground_name}",
                        "x": 10,
                        "y": 20,
                        "width": 120,
                        "height": 180,
                        "coverage_ratio": 0.08,
                        "file_size": len(b"unique-image"),
                        "visual_hash": "fg-1",
                        "dominant_color_ratio": 0.42,
                    },
                    {
                        "page": 1,
                        "filename": background_a,
                        "path": f"images/book/{background_a}",
                        "x": 0,
                        "y": 0,
                        "width": 780,
                        "height": 980,
                        "coverage_ratio": 0.92,
                        "file_size": len(b"bg-image-a"),
                        "visual_hash": "bg-repeat",
                        "dominant_color_ratio": 0.51,
                    },
                    {
                        "page": 2,
                        "filename": background_b,
                        "path": f"images/book/{background_b}",
                        "x": 0,
                        "y": 0,
                        "width": 720,
                        "height": 960,
                        "coverage_ratio": 0.88,
                        "file_size": len(b"bg-image-b-larger"),
                        "visual_hash": "bg-repeat",
                        "dominant_color_ratio": 0.49,
                    },
                ],
            }
            (images_dir / "manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            config = {
                "source": "data/markdown/book_pages.md",
                "output_dir": "docs/src/content/docs",
                "images": {
                    "enabled": True,
                    "assets_dir": "docs/src/assets/extracted",
                    "repeat_file_size_threshold": 99,
                    "repeat_visual_threshold": 2,
                    "background_min_coverage_ratio": 0.6,
                },
                "chapters": {
                    "rules": {
                        "title": "Rules",
                        "order": 1,
                        "files": {
                            "index": {
                                "title": "Overview",
                                "description": "Desc",
                                "pages": [1, 2],
                                "order": 0,
                            }
                        },
                    }
                },
            }

            sc.split_chapters(config, root)

            out = root / "docs" / "src" / "content" / "docs" / "rules" / "index.md"
            data = out.read_text(encoding="utf-8")

            self.assertIn(f"../../assets/extracted/book/{foreground_name}", data)
            self.assertNotIn(background_a, data)
            self.assertNotIn(background_b, data)

    def test_split_chapters_keeps_full_page_image_when_page_text_is_sparse(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "data" / "markdown" / "book_pages.md"
            src.parent.mkdir(parents=True)
            src.write_text(
                "<!-- PAGE 1 -->\n\nIllustration caption only",
                encoding="utf-8",
            )

            images_dir = root / "data" / "markdown" / "images" / "book"
            images_dir.mkdir(parents=True)
            art_name = "page001_img00_occ00_x0_y0_w800_h1000.png"
            (images_dir / art_name).write_bytes(b"art-image")

            manifest = {
                "pdf": "book.pdf",
                "images_dir": "images/book",
                "images": [
                    {
                        "page": 1,
                        "filename": art_name,
                        "path": f"images/book/{art_name}",
                        "x": 0,
                        "y": 0,
                        "width": 800,
                        "height": 1000,
                        "coverage_ratio": 0.92,
                        "file_size": len(b"art-image"),
                        "visual_hash": "full-art",
                        "dominant_color_ratio": 0.95,
                    },
                    {
                        "page": 2,
                        "filename": "page002_img00_occ00_x0_y0_w800_h1000.png",
                        "path": "images/book/page002_img00_occ00_x0_y0_w800_h1000.png",
                        "x": 0,
                        "y": 0,
                        "width": 800,
                        "height": 1000,
                        "coverage_ratio": 0.92,
                        "file_size": len(b"art-image"),
                        "visual_hash": "full-art",
                        "dominant_color_ratio": 0.95,
                    },
                ],
            }
            (images_dir / "page002_img00_occ00_x0_y0_w800_h1000.png").write_bytes(b"art-image")
            (images_dir / "manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            config = {
                "source": "data/markdown/book_pages.md",
                "output_dir": "docs/src/content/docs",
                "images": {
                    "enabled": True,
                    "assets_dir": "docs/src/assets/extracted",
                    "repeat_file_size_threshold": 2,
                    "repeat_visual_threshold": 2,
                    "background_min_coverage_ratio": 0.6,
                    "background_min_text_tokens": 80,
                },
                "chapters": {
                    "rules": {
                        "title": "Rules",
                        "order": 1,
                        "files": {
                            "index": {
                                "title": "Overview",
                                "description": "Desc",
                                "pages": [1, 1],
                                "order": 0,
                            }
                        },
                    }
                },
            }

            sc.split_chapters(config, root)

            out = root / "docs" / "src" / "content" / "docs" / "rules" / "index.md"
            data = out.read_text(encoding="utf-8")
            self.assertIn(art_name, data)

    def test_split_chapters_skips_edge_anchored_half_page_backgrounds(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "data" / "markdown" / "book_pages.md"
            src.parent.mkdir(parents=True)
            src.write_text(
                "<!-- PAGE 1 -->\n\n" + ("Dense rules text " * 70) + "\n\n<!-- PAGE 2 -->\n\n" + ("Dense rules text " * 70),
                encoding="utf-8",
            )

            images_dir = root / "data" / "markdown" / "images" / "book"
            images_dir.mkdir(parents=True)
            bg1 = "page001_img00_occ00_x300_y0_w133_h650.jpeg"
            bg2 = "page002_img00_occ00_x300_y0_w133_h650.jpeg"
            fg = "page001_img01_occ00_x40_y80_w120_h180.png"
            (images_dir / bg1).write_bytes(b"edge-bg-a")
            (images_dir / bg2).write_bytes(b"edge-bg-b")
            (images_dir / fg).write_bytes(b"foreground")

            manifest = {
                "pdf": "book.pdf",
                "images_dir": "images/book",
                "images": [
                    {
                        "page": 1,
                        "filename": bg1,
                        "path": f"images/book/{bg1}",
                        "x": 300,
                        "y": 0,
                        "width": 133,
                        "height": 650,
                        "page_width": 432,
                        "page_height": 648,
                        "coverage_ratio": 0.309,
                        "file_size": len(b"edge-bg-a"),
                        "visual_hash": "edge-bg",
                        "dominant_color_ratio": 0.6,
                    },
                    {
                        "page": 2,
                        "filename": bg2,
                        "path": f"images/book/{bg2}",
                        "x": 300,
                        "y": 0,
                        "width": 133,
                        "height": 650,
                        "page_width": 432,
                        "page_height": 648,
                        "coverage_ratio": 0.309,
                        "file_size": len(b"edge-bg-b"),
                        "visual_hash": "edge-bg",
                        "dominant_color_ratio": 0.58,
                    },
                    {
                        "page": 1,
                        "filename": fg,
                        "path": f"images/book/{fg}",
                        "x": 40,
                        "y": 80,
                        "width": 120,
                        "height": 180,
                        "page_width": 432,
                        "page_height": 648,
                        "coverage_ratio": 0.077,
                        "file_size": len(b"foreground"),
                        "visual_hash": "fg",
                        "dominant_color_ratio": 0.3,
                    },
                ],
            }
            (images_dir / "manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            config = {
                "source": "data/markdown/book_pages.md",
                "output_dir": "docs/src/content/docs",
                "images": {
                    "enabled": True,
                    "assets_dir": "docs/src/assets/extracted",
                    "repeat_file_size_threshold": 99,
                    "repeat_visual_threshold": 2,
                    "background_min_coverage_ratio": 0.6,
                    "background_min_text_tokens": 80,
                    "background_edge_min_area_ratio": 0.18,
                    "background_edge_min_span_ratio": 0.7,
                },
                "chapters": {
                    "rules": {
                        "title": "Rules",
                        "order": 1,
                        "files": {
                            "index": {
                                "title": "Overview",
                                "description": "Desc",
                                "pages": [1, 2],
                                "order": 0,
                            }
                        },
                    }
                },
            }

            sc.split_chapters(config, root)

            out = root / "docs" / "src" / "content" / "docs" / "rules" / "index.md"
            data = out.read_text(encoding="utf-8")
            self.assertIn(fg, data)
            self.assertNotIn(bg1, data)
            self.assertNotIn(bg2, data)


class TestTermGenerate(unittest.TestCase):
    def test_main_filters_managed_terms(self) -> None:
        args = argparse.Namespace(
            root=None,
            glossary=Path("glossary.json"),
            min_frequency=2,
            limit=10,
            json=False,
        )
        captured: dict[str, object] = {}

        def capture_save(_: Path, payload: dict[str, object]) -> None:
            captured["payload"] = payload

        with (
            patch.object(tg, "parse_args", return_value=args),
            patch.object(tg, "resolve_root", return_value=tg.PROJECT_ROOT),
            patch.object(tg, "load_glossary", return_value={"_meta": {}, "Move": {"status": "approved"}}),
            patch.object(tg, "build_corpus", return_value=({"docs/a.md": "x"}, "fp")),
            patch.object(
                tg,
                "extract_candidates",
                return_value=[
                    {"term": "Move", "normalized": "move", "count": 5},
                    {"term": "Harm", "normalized": "harm", "count": 3},
                ],
            ),
            patch.object(tg, "save_json", side_effect=capture_save),
        ):
            tg.main()

        payload = captured["payload"]
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["candidates"][0]["term"], "Harm")


class TestTermEdit(unittest.TestCase):
    @staticmethod
    def make_args(**overrides: object) -> argparse.Namespace:
        base = {
            "glossary": Path("glossary.json"),
            "root": Path("."),
            "term": "Stress",
            "cal": False,
            "show": False,
            "list": False,
            "remove": False,
            "set_zh": "壓力",
            "notes": "",
            "status": "approved",
            "mark_term": True,
            "unmark_term": False,
            "forbidden": [],
            "keep_english": False,
            "force": False,
        }
        base.update(overrides)
        return argparse.Namespace(**base)

    def test_mutate_term_requires_cal_for_unmanaged(self) -> None:
        glossary = {"_meta": {"updated": ""}}
        args = self.make_args(force=False)
        with patch.object(te, "has_fresh_cal", return_value=False):
            changed = te.mutate_term(args, glossary)
        self.assertFalse(changed)

    def test_mutate_term_force_updates_entry(self) -> None:
        glossary = {"_meta": {"updated": ""}}
        args = self.make_args(force=True)

        with (
            patch.object(te, "load_json", return_value=None),
            patch.object(te, "save_glossary"),
        ):
            changed = te.mutate_term(args, glossary)

        self.assertTrue(changed)
        self.assertIn("Stress", glossary)
        self.assertEqual(glossary["Stress"]["zh"], "壓力")

    def test_run_calculation_managed_term_skips_scan(self) -> None:
        args = self.make_args(cal=True)
        glossary = {"_meta": {"updated": ""}, "Stress": {"status": "approved"}}
        saved: dict[str, object] = {}

        def capture(_: Path, payload: dict[str, object]) -> None:
            saved["payload"] = payload

        with (
            patch.object(te, "ensure_cache_dir"),
            patch.object(te, "load_json", return_value={"terms": {}}),
            patch.object(te, "save_json", side_effect=capture),
        ):
            te.run_calculation(args, glossary)

        payload = saved["payload"]["terms"]["Stress"]
        self.assertTrue(payload["managed"])
        self.assertTrue(payload["skipped_full_scan"])


class TestTermRead(unittest.TestCase):
    def test_load_or_build_index_uses_cache_when_fingerprint_matches(self) -> None:
        with (
            patch.object(tr, "build_corpus", return_value=({"docs/a.md": "x"}, "fp")),
            patch.object(tr, "load_json", return_value={"fingerprint": "fp", "corpus": {"docs/a.md": "x"}}),
            patch.object(tr, "save_json") as save_json,
        ):
            corpus, fp = tr.load_or_build_index(Path("."), force=False)
        self.assertEqual(fp, "fp")
        self.assertEqual(corpus, {"docs/a.md": "x"})
        save_json.assert_not_called()

    def test_main_fail_on_missing_terms(self) -> None:
        args = argparse.Namespace(
            root=None,
            glossary=Path("glossary.json"),
            schema=Path("glossary.schema.json"),
            json=False,
            reindex=False,
            unknown_min_frequency=3,
            unknown_limit=20,
            fail_on_forbidden=False,
            fail_on_missing=True,
            no_schema_validate=True,
        )

        with (
            patch.object(tr, "parse_args", return_value=args),
            patch.object(tr, "resolve_root", return_value=tr.PROJECT_ROOT),
            patch.object(tr, "load_glossary", return_value={"_meta": {}, "Move": {"status": "approved", "is_term": True}}),
            patch.object(tr, "load_or_build_index", return_value=({}, "fp")),
            patch.object(tr, "count_terms_batch", return_value={"Move": (0, {})}),
            patch.object(tr, "extract_candidates", return_value=[]),
        ):
            with self.assertRaises(SystemExit):
                tr.main()


class TestValidateGlossary(unittest.TestCase):
    def test_main_success(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            glossary = root / "glossary.json"
            schema = root / "schema.json"
            glossary.write_text(json.dumps({"_meta": {"description": "x", "updated": ""}}), encoding="utf-8")
            schema.write_text(json.dumps({"type": "object"}), encoding="utf-8")

            args = argparse.Namespace(glossary=glossary, schema=schema)
            with patch.object(vg, "parse_args", return_value=args):
                vg.main()

    def test_main_missing_glossary_raises(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            schema = root / "schema.json"
            schema.write_text(json.dumps({"type": "object"}), encoding="utf-8")
            args = argparse.Namespace(glossary=root / "missing.json", schema=schema)
            with patch.object(vg, "parse_args", return_value=args):
                with self.assertRaises(SystemExit):
                    vg.main()


class TestTermLib(unittest.TestCase):
    def test_canonical_term_key_collapses_whitespace_and_last_token(self) -> None:
        with patch.object(tl, "_singularize_token", return_value="Move"):
            result = tl.canonical_term_key("  Basic   Moves  ")
        self.assertEqual(result, "Basic Move")

    def test_parse_doc_expands_nlp_max_length_for_large_text(self) -> None:
        class FakeNLP:
            def __init__(self) -> None:
                self.max_length = 1_000_000

            def __call__(self, text: str) -> dict[str, int]:
                if len(text) > self.max_length:
                    raise ValueError("text exceeds max_length")
                return {"length": len(text)}

        large_text = "a" * 1_000_010
        fake_nlp = FakeNLP()
        with (
            patch.object(tl, "SPACY_AVAILABLE", True),
            patch.object(tl, "get_nlp", return_value=fake_nlp),
            patch.dict(tl._DOC_CACHE, {}, clear=True),
        ):
            doc = tl.parse_doc(large_text)

        self.assertEqual(doc, {"length": len(large_text)})
        self.assertGreaterEqual(fake_nlp.max_length, len(large_text))

    def test_extract_candidates_fallback_without_spacy(self) -> None:
        corpus = {"docs/a.md": "Move move harm move"}
        with patch.object(tl, "SPACY_AVAILABLE", False):
            result = tl.extract_candidates(corpus, min_frequency=2)
        normalized = {item["normalized"] for item in result}
        self.assertIn("move", normalized)

    def test_count_term_fallback_case_insensitive(self) -> None:
        corpus = {"docs/a.md": "move MOVE moves"}
        with patch.object(tl, "SPACY_AVAILABLE", False), patch.object(tl, "INFLECT_AVAILABLE", False):
            total, files = tl.count_term(corpus, "move")
        self.assertEqual(total, 2)
        self.assertEqual(files["docs/a.md"], 2)


class TestInitCreateProgress(unittest.TestCase):
    def test_build_progress_orders_by_section_and_file_order(self) -> None:
        config = {
            "output_dir": "docs/src/content/docs",
            "chapters": {
                "b": {
                    "order": 2,
                    "files": {
                        "index": {"title": "B", "pages": [3, 4], "order": 0},
                    },
                },
                "a": {
                    "order": 1,
                    "files": {
                        "index": {"title": "A", "pages": [1, 2], "order": 0},
                    },
                },
            },
        }
        payload = icp.build_progress(config)
        self.assertEqual(payload["_meta"]["total_chapters"], 2)
        self.assertEqual(payload["chapters"][0]["title"], "A")
        self.assertEqual(payload["chapters"][0]["id"], "docs-src-content-docs-a-index")

    def test_main_refuses_overwrite_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "data").mkdir(parents=True)
            chapters = root / "chapters.json"
            output = root / "data" / "translation-progress.json"
            chapters.write_text(json.dumps({"chapters": {}, "output_dir": "docs/src/content/docs"}), encoding="utf-8")
            output.write_text("{}", encoding="utf-8")

            args = argparse.Namespace(chapters=Path("chapters.json"), output=Path("data/translation-progress.json"), force=False, json=False)
            with patch.object(icp, "PROJECT_ROOT", root), patch.object(icp, "parse_args", return_value=args):
                with self.assertRaises(SystemExit):
                    icp.main()


class TestInitHandoffGate(unittest.TestCase):
    def test_check_required_files_reports_missing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            missing = ihg.check_required_files(Path(td))
        self.assertGreaterEqual(len(missing), 1)

    def test_main_passes_with_skip_docs_build(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for rel in ihg.REQUIRED_FILES:
                p = root / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text("{}", encoding="utf-8")

            args = argparse.Namespace(project_root=root, skip_docs_build=True, json=False)
            ok_result = {"cmd": ["python"], "cwd": str(root), "returncode": 0, "stdout": "", "stderr": ""}
            with patch.object(ihg, "parse_args", return_value=args), patch.object(ihg, "run_cmd", return_value=ok_result) as run_cmd:
                ihg.main()
            self.assertEqual(run_cmd.call_count, 3)

    def test_main_fails_when_command_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for rel in ihg.REQUIRED_FILES:
                p = root / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text("{}", encoding="utf-8")

            args = argparse.Namespace(project_root=root, skip_docs_build=True, json=False)
            bad = {"cmd": ["python"], "cwd": str(root), "returncode": 1, "stdout": "", "stderr": "fail"}
            with patch.object(ihg, "parse_args", return_value=args), patch.object(ihg, "run_cmd", return_value=bad):
                with self.assertRaises(SystemExit):
                    ihg.main()


if __name__ == "__main__":
    unittest.main()
