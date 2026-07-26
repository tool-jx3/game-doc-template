from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

import init_create_progress as icp


def test_build_progress_orders_by_section_and_file_order():
    config = {
        "output_dir": "docs/src/content/docs",
        "chapters": {
            "b": {"order": 2, "files": {"index": {"title": "B", "pages": [3, 4], "order": 0}}},
            "a": {"order": 1, "files": {"index": {"title": "A", "pages": [1, 2], "order": 0}}},
        },
    }

    payload = icp.build_progress(config)

    assert payload["_meta"]["total_chapters"] == 2
    assert payload["chapters"][0]["title"] == "A"
    assert payload["chapters"][0]["id"] == "docs-src-content-docs-a-index"
    assert payload["chapters"][0]["source_pages"] == "1-2"
    assert payload["chapters"][1]["title"] == "B"


def test_build_progress_bilingual_mode_targets_bilingual_dir():
    config = {
        "output_dir": "docs/src/content/docs",
        "mode": "bilingual",
        "chapters": {"a": {"order": 1, "files": {"index": {"title": "A", "pages": [1, 2]}}}},
    }

    payload = icp.build_progress(config)

    assert payload["chapters"][0]["file"] == "docs/src/content/docs/bilingual/a/index.md"


def test_main_refuses_overwrite_without_force(monkeypatch, tmp_path):
    (tmp_path / "data").mkdir(parents=True)
    (tmp_path / "chapters.json").write_text(
        json.dumps({"chapters": {}, "output_dir": "docs/src/content/docs"}), encoding="utf-8"
    )
    (tmp_path / "data" / "translation-progress.json").write_text("{}", encoding="utf-8")

    args = argparse.Namespace(
        chapters=Path("chapters.json"),
        output=Path("data/translation-progress.json"),
        force=False,
        json=False,
    )
    monkeypatch.setattr(icp, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(icp, "parse_args", lambda: args)

    with pytest.raises(SystemExit):
        icp.main()


def test_main_writes_progress_with_force(monkeypatch, tmp_path):
    (tmp_path / "data").mkdir(parents=True)
    (tmp_path / "chapters.json").write_text(
        json.dumps(
            {
                "output_dir": "docs/src/content/docs",
                "chapters": {"a": {"order": 1, "files": {"index": {"title": "A", "pages": [1, 2]}}}},
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "data" / "translation-progress.json"
    output.write_text("{}", encoding="utf-8")

    args = argparse.Namespace(
        chapters=Path("chapters.json"),
        output=Path("data/translation-progress.json"),
        force=True,
        json=False,
    )
    monkeypatch.setattr(icp, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(icp, "parse_args", lambda: args)

    icp.main()

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["_meta"]["total_chapters"] == 1
    assert payload["chapters"][0]["status"] == "not_started"
