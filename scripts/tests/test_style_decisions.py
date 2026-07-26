from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

import _style_decisions_lib as sdl
import style_decisions as sd
import validate_style_decisions as vsd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = PROJECT_ROOT / "style-decisions.schema.json"


def _seed_style(style_path: Path) -> None:
    sdl.save_style_decisions(
        style_path,
        sdl.default_style_decisions_payload(),
        schema_path=SCHEMA_PATH,
    )


def test_cmd_init_creates_default_file(tmp_path):
    style_path = tmp_path / "style-decisions.json"
    args = argparse.Namespace(
        style=style_path,
        schema=SCHEMA_PATH,
        force=False,
        description="測試 style decisions",
    )

    sd.cmd_init(args)

    payload = json.loads(style_path.read_text(encoding="utf-8"))
    assert payload["_meta"]["description"] == "測試 style decisions"
    assert payload["translation_mode"]["mode"] == "full"


def test_cmd_set_document_format_for_document(tmp_path):
    style_path = tmp_path / "style-decisions.json"
    _seed_style(style_path)

    args = argparse.Namespace(
        style=style_path,
        schema=SCHEMA_PATH,
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
    assert entry["layout_profile"] == "double-column"
    assert entry["page_text_engine"] == "markitdown"


def test_cmd_add_translation_note_upserts_by_key(tmp_path):
    style_path = tmp_path / "style-decisions.json"
    _seed_style(style_path)

    def make(note: str) -> argparse.Namespace:
        return argparse.Namespace(
            style=style_path,
            schema=SCHEMA_PATH,
            document_key=None,
            key="tone",
            topic="語氣",
            note=note,
        )

    sd.cmd_add_translation_note(make("保持冷靜、正式。"))
    sd.cmd_add_translation_note(make("保持冷靜、正式，避免過度口語。"))

    payload = json.loads(style_path.read_text(encoding="utf-8"))
    notes = payload["translation_notes"]["global"]
    assert len(notes) == 1
    assert notes[0]["note"] == "保持冷靜、正式，避免過度口語。"


def test_cmd_set_translation_mode_bilingual(tmp_path):
    style_path = tmp_path / "style-decisions.json"
    _seed_style(style_path)

    args = argparse.Namespace(
        style=style_path,
        schema=SCHEMA_PATH,
        mode="bilingual",
        reason="test",
    )
    sd.cmd_set_translation_mode(args)

    payload = json.loads(style_path.read_text(encoding="utf-8"))
    assert payload["translation_mode"]["mode"] == "bilingual"
    assert payload["translation_mode"]["reason"] == "test"


def test_validate_style_decisions_reports_invalid_payload(monkeypatch, tmp_path):
    style_path = tmp_path / "style-decisions.json"
    style_path.write_text(
        json.dumps(
            {"_meta": {"description": "x", "updated": ""}, "repository": {"visibility": "internal"}},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    args = argparse.Namespace(style=style_path, schema=SCHEMA_PATH)
    monkeypatch.setattr(vsd, "parse_args", lambda: args)

    with pytest.raises(SystemExit):
        vsd.main()


def test_validate_style_decisions_accepts_default_payload(monkeypatch, tmp_path):
    style_path = tmp_path / "style-decisions.json"
    _seed_style(style_path)

    args = argparse.Namespace(style=style_path, schema=SCHEMA_PATH)
    monkeypatch.setattr(vsd, "parse_args", lambda: args)

    vsd.main()
