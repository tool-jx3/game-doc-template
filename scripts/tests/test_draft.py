from __future__ import annotations

import json

import pytest

import draft as dr

SOURCE_REL = "docs/src/content/docs/rules/basic.md"
DRAFT_REL = ".state/translate/drafts/docs/src/content/docs/rules/basic.md"


def _write_manifest(root, draft_rel: str) -> None:
    manifest_path = root / ".state" / "translate" / "draft-manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(
            {
                "entries": {
                    SOURCE_REL: {
                        "source": SOURCE_REL,
                        "draft": draft_rel,
                        "updated": "2026-03-09T00:00:00+00:00",
                    }
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_cmd_path_creates_empty_draft_and_manifest_entry(monkeypatch, tmp_path):
    monkeypatch.setattr(dr, "ROOT", tmp_path)

    dr.cmd_path(SOURCE_REL, "translate")

    draft = tmp_path / DRAFT_REL
    assert draft.exists()
    assert draft.read_text(encoding="utf-8") == ""

    manifest = json.loads(
        (tmp_path / ".state" / "translate" / "draft-manifest.json").read_text(encoding="utf-8")
    )
    assert SOURCE_REL in manifest["entries"]
    assert manifest["entries"][SOURCE_REL]["draft"] == DRAFT_REL


def test_cmd_writeback_restores_source_and_clears_manifest(monkeypatch, tmp_path):
    monkeypatch.setattr(dr, "ROOT", tmp_path)

    draft = tmp_path / DRAFT_REL
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
    _write_manifest(tmp_path, DRAFT_REL)

    dr.cmd_writeback(SOURCE_REL, "translate")

    source = tmp_path / SOURCE_REL
    # Image markdown must survive writeback untouched.
    assert source.read_text(encoding="utf-8") == expected
    assert not draft.exists()

    manifest = json.loads(
        (tmp_path / ".state" / "translate" / "draft-manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["entries"] == {}


def test_cmd_writeback_uses_manifest_draft_path(monkeypatch, tmp_path):
    monkeypatch.setattr(dr, "ROOT", tmp_path)

    draft = tmp_path / "custom-drafts" / "basic.md"
    draft.parent.mkdir(parents=True, exist_ok=True)
    draft.write_text("內容\n", encoding="utf-8")
    _write_manifest(tmp_path, "custom-drafts/basic.md")

    dr.cmd_writeback(SOURCE_REL, "translate")

    source = tmp_path / SOURCE_REL
    assert source.read_text(encoding="utf-8") == "內容\n"
    assert not draft.exists()


def test_cmd_writeback_fails_without_manifest_entry(monkeypatch, tmp_path):
    monkeypatch.setattr(dr, "ROOT", tmp_path)

    draft = tmp_path / DRAFT_REL
    draft.parent.mkdir(parents=True, exist_ok=True)
    draft.write_text("內容\n", encoding="utf-8")

    with pytest.raises(SystemExit):
        dr.cmd_writeback(SOURCE_REL, "translate")
