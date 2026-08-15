from __future__ import annotations

import argparse
import json

import pytest

import validate_glossary as vg


def test_main_success(monkeypatch, tmp_path):
    glossary = tmp_path / "glossary.json"
    schema = tmp_path / "schema.json"
    glossary.write_text(
        json.dumps({"_meta": {"description": "x", "updated": ""}}), encoding="utf-8"
    )
    schema.write_text(json.dumps({"type": "object"}), encoding="utf-8")

    args = argparse.Namespace(glossary=glossary, schema=schema)
    monkeypatch.setattr(vg, "parse_args", lambda: args)

    vg.main()


def test_main_missing_glossary_raises(monkeypatch, tmp_path):
    schema = tmp_path / "schema.json"
    schema.write_text(json.dumps({"type": "object"}), encoding="utf-8")

    args = argparse.Namespace(glossary=tmp_path / "missing.json", schema=schema)
    monkeypatch.setattr(vg, "parse_args", lambda: args)

    with pytest.raises(SystemExit):
        vg.main()


def test_main_missing_schema_raises(monkeypatch, tmp_path):
    glossary = tmp_path / "glossary.json"
    glossary.write_text(json.dumps({"_meta": {}}), encoding="utf-8")

    args = argparse.Namespace(glossary=glossary, schema=tmp_path / "missing.json")
    monkeypatch.setattr(vg, "parse_args", lambda: args)

    with pytest.raises(SystemExit):
        vg.main()


def test_main_schema_violation_exits_nonzero(monkeypatch, tmp_path):
    glossary = tmp_path / "glossary.json"
    schema = tmp_path / "schema.json"
    glossary.write_text(json.dumps({"_meta": {"description": "x"}}), encoding="utf-8")
    schema.write_text(
        json.dumps({"type": "object", "required": ["missing_key"]}), encoding="utf-8"
    )

    args = argparse.Namespace(glossary=glossary, schema=schema)
    monkeypatch.setattr(vg, "parse_args", lambda: args)

    with pytest.raises(SystemExit) as excinfo:
        vg.main()
    assert excinfo.value.code == 1
