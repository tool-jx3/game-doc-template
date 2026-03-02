from __future__ import annotations

import argparse
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import _term_lib as tl
import clean_sample_data as csd
import extract_pdf as ep
import init_create_progress as icp
import init_handoff_gate as ihg
import split_chapters as sc
import term_edit as te
import term_generate as tg
import term_read as tr
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
                self._text = text

            def get_text(self, _: str) -> str:
                return self._text

        class FakeDoc(list):
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

    def test_extract_images_writes_files(self) -> None:
        class FakePage:
            def get_images(self) -> list[tuple[int]]:
                return [(1,), (2,)]

        class FakeDoc(list):
            def extract_image(self, xref: int) -> dict[str, object]:
                return {"image": f"img{xref}".encode("utf-8"), "ext": "png"}

        class FakePyMuPDF:
            @staticmethod
            def open(_: str) -> FakeDoc:
                return FakeDoc([FakePage()])

        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            with patch.object(ep, "pymupdf", FakePyMuPDF):
                images = ep.extract_images(Path("sample.pdf"), out)
            self.assertEqual(len(images), 2)
            self.assertTrue(all(p.exists() for p in images))


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
            patch.object(tr, "count_term", return_value=(0, {})),
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
            self.assertEqual(run_cmd.call_count, 2)

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
