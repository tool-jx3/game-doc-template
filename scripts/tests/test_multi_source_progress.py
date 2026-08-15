"""Tests for multi-source progress tracking."""

import json
import subprocess
import pytest
from pathlib import Path

from init_create_progress import iter_chapter_files, build_progress


class TestIterChapterFilesRecursive:
    def test_flat_files(self):
        config = {
            "output_dir": "docs/src/content/docs",
            "chapters": {
                "combat": {
                    "title": "Combat",
                    "order": 1,
                    "files": {
                        "actions": {"title": "Actions", "pages": [5, 7], "order": 0},
                    },
                },
            },
        }
        result = list(iter_chapter_files(config))
        assert len(result) == 1
        assert result[0][1].endswith("combat/actions.md")

    def test_nested_files(self):
        config = {
            "output_dir": "docs/src/content/docs",
            "chapters": {
                "rules": {
                    "title": "Rules",
                    "order": 1,
                    "files": {
                        "combat": {
                            "title": "Combat",
                            "order": 0,
                            "files": {
                                "actions": {"title": "Actions", "pages": [5, 7], "order": 0},
                                "damage": {"title": "Damage", "pages": [8, 10], "order": 1},
                            },
                        },
                    },
                },
            },
        }
        result = list(iter_chapter_files(config))
        assert len(result) == 2
        paths = [r[1] for r in result]
        assert any("rules/combat/actions.md" in p for p in paths)
        assert any("rules/combat/damage.md" in p for p in paths)

    def test_group_nodes_skipped(self):
        config = {
            "output_dir": "docs/src/content/docs",
            "chapters": {
                "rules": {
                    "title": "Rules",
                    "order": 1,
                    "files": {
                        "combat": {
                            "title": "Combat",
                            "order": 0,
                            "files": {
                                "actions": {"title": "Actions", "pages": [1, 1], "order": 0},
                            },
                        },
                    },
                },
            },
        }
        result = list(iter_chapter_files(config))
        assert len(result) == 1

    def test_source_field_from_chapter(self):
        config = {
            "output_dir": "docs/src/content/docs",
            "chapters": {
                "core": {
                    "source": "core_pages.md",
                    "title": "Core",
                    "order": 1,
                    "files": {
                        "index": {"title": "Index", "pages": [1, 1], "order": 0},
                    },
                },
            },
        }
        result = list(iter_chapter_files(config))
        assert len(result) == 1
        section_slug, rel_path, file_cfg, source = result[0]
        assert source == "core_pages.md"

    def test_malformed_entry_raises_instead_of_silently_dropping(self):
        config = {
            "output_dir": "docs/src/content/docs",
            "chapters": {
                "core": {
                    "title": "Core",
                    "order": 1,
                    "files": {
                        "index": {"title": "Index", "order": 0},
                    },
                },
            },
        }
        with pytest.raises(ValueError, match="index"):
            list(iter_chapter_files(config))

    def test_bilingual_mode(self):
        config = {
            "output_dir": "docs/src/content/docs",
            "mode": "bilingual",
            "chapters": {
                "core": {
                    "title": "Core",
                    "order": 1,
                    "files": {
                        "index": {"title": "Index", "pages": [1, 1], "order": 0},
                    },
                },
            },
        }
        result = list(iter_chapter_files(config))
        section_slug, rel_path, file_cfg, source = result[0]
        assert "bilingual" in rel_path


class TestBuildProgressMultiSource:
    def test_source_in_progress_entry(self):
        config = {
            "output_dir": "docs/src/content/docs",
            "chapters": {
                "core": {
                    "source": "core_pages.md",
                    "title": "Core",
                    "order": 1,
                    "files": {
                        "index": {"title": "Index", "pages": [1, 3], "order": 0},
                    },
                },
            },
        }
        payload = build_progress(config)
        assert len(payload["chapters"]) == 1
        entry = payload["chapters"][0]
        assert entry["source"] == "core_pages.md"
        assert entry["source_pages"] == "1-3"

    def test_no_source_omits_field(self):
        config = {
            "source": "",
            "output_dir": "docs/src/content/docs",
            "chapters": {
                "core": {
                    "title": "Core",
                    "order": 1,
                    "files": {
                        "index": {"title": "Index", "pages": [1, 1], "order": 0},
                    },
                },
            },
        }
        payload = build_progress(config)
        assert "source" not in payload["chapters"][0]


class TestProgressReadSourceFilter:
    def test_source_filter(self, tmp_path):
        progress = {
            "_meta": {"total_chapters": 2, "completed": 0},
            "chapters": [
                {"id": "a", "title": "A", "file": "a.md", "source": "core_pages.md", "status": "not_started"},
                {"id": "b", "title": "B", "file": "b.md", "source": "exp_pages.md", "status": "not_started"},
            ],
        }
        pf = tmp_path / "progress.json"
        pf.write_text(json.dumps(progress), encoding="utf-8")

        result = subprocess.run(
            ["uv", "run", "python", "scripts/progress_read.py",
             "--progress-file", str(pf), "--source", "core", "--json"],
            capture_output=True, text=True,
            cwd=str(Path(__file__).resolve().parents[2]),
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        data = json.loads(result.stdout)
        assert len(data["chapters"]) == 1
        assert data["chapters"][0]["source"] == "core_pages.md"
        assert data["total"] == 1
