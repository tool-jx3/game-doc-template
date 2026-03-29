"""Integration tests for multi-source chapter splitting."""

import json
import pytest
from pathlib import Path

from split_chapters import split_chapters


class TestMultiSourceSplit:
    def _make_pages_md(self, tmp_path, name, pages):
        """Create a _pages.md file with given page contents."""
        parts = []
        for num, text in pages.items():
            parts.append(f"<!-- PAGE {num} -->\n\n{text}")
        content = "\n\n".join(parts)
        path = tmp_path / f"{name}_pages.md"
        path.write_text(content, encoding="utf-8")
        return str(path)

    def test_single_source_backward_compat(self, tmp_path):
        source = self._make_pages_md(tmp_path, "rules", {
            1: "# Introduction\n\nWelcome to the game.",
            2: "## Combat\n\nFight stuff.",
        })
        output_dir = tmp_path / "docs"
        config = {
            "source": source,
            "output_dir": str(output_dir),
            "chapters": {
                "intro": {
                    "title": "Introduction",
                    "order": 1,
                    "files": {
                        "index": {"title": "Intro", "pages": [1, 1], "order": 0},
                    },
                },
            },
        }
        split_chapters(config, tmp_path)
        assert (output_dir / "intro" / "index.md").exists()

    def test_multi_source_chapter_level(self, tmp_path):
        source_a = self._make_pages_md(tmp_path, "core", {
            1: "# Core Rules\n\nCore content.",
        })
        source_b = self._make_pages_md(tmp_path, "exp", {
            1: "# Expansion\n\nNew stuff.",
        })
        output_dir = tmp_path / "docs"
        config = {
            "output_dir": str(output_dir),
            "chapters": {
                "core": {
                    "source": source_a,
                    "title": "Core",
                    "order": 1,
                    "files": {
                        "index": {"title": "Core", "pages": [1, 1], "order": 0},
                    },
                },
                "expansion": {
                    "source": source_b,
                    "title": "Expansion",
                    "order": 2,
                    "files": {
                        "index": {"title": "Expansion", "pages": [1, 1], "order": 0},
                    },
                },
            },
        }
        split_chapters(config, tmp_path)
        assert (output_dir / "core" / "index.md").exists()
        assert (output_dir / "expansion" / "index.md").exists()

    def test_recursive_files_creates_subdirs(self, tmp_path):
        source = self._make_pages_md(tmp_path, "rules", {
            1: "Actions content", 2: "Damage content",
        })
        output_dir = tmp_path / "docs"
        config = {
            "source": source,
            "output_dir": str(output_dir),
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
                                "damage": {"title": "Damage", "pages": [2, 2], "order": 1},
                            },
                        },
                    },
                },
            },
        }
        split_chapters(config, tmp_path)
        assert (output_dir / "rules" / "combat" / "actions.md").exists()
        assert (output_dir / "rules" / "combat" / "damage.md").exists()

    def test_meta_yml_generated_for_groups(self, tmp_path):
        source = self._make_pages_md(tmp_path, "rules", {1: "Content"})
        output_dir = tmp_path / "docs"
        config = {
            "source": source,
            "output_dir": str(output_dir),
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
        split_chapters(config, tmp_path)
        meta = output_dir / "rules" / "_meta.yml"
        assert meta.exists()
        content = meta.read_text(encoding="utf-8")
        assert "label: Rules" in content
        assert "order: 1" in content
        combat_meta = output_dir / "rules" / "combat" / "_meta.yml"
        assert combat_meta.exists()
        combat_content = combat_meta.read_text(encoding="utf-8")
        assert "label: Combat" in combat_content

    def test_flat_slash_paths_normalized(self, tmp_path):
        source = self._make_pages_md(tmp_path, "rules", {
            1: "Actions", 2: "Damage",
        })
        output_dir = tmp_path / "docs"
        config = {
            "source": source,
            "output_dir": str(output_dir),
            "chapters": {
                "rules": {
                    "title": "Rules",
                    "order": 1,
                    "files": {
                        "combat/actions": {"title": "Actions", "pages": [1, 1], "order": 0},
                        "combat/damage": {"title": "Damage", "pages": [2, 2], "order": 1},
                    },
                },
            },
        }
        split_chapters(config, tmp_path)
        assert (output_dir / "rules" / "combat" / "actions.md").exists()
        assert (output_dir / "rules" / "combat" / "damage.md").exists()
        # Synthetic group node gets _meta.yml with raw slug label
        combat_meta = output_dir / "rules" / "combat" / "_meta.yml"
        assert combat_meta.exists()
        content = combat_meta.read_text(encoding="utf-8")
        assert "label: combat" in content
        assert "order" not in content

    def test_bilingual_mode_meta_yml(self, tmp_path):
        source = self._make_pages_md(tmp_path, "rules", {1: "Content"})
        output_dir = tmp_path / "docs"
        config = {
            "source": source,
            "output_dir": str(output_dir),
            "mode": "bilingual",
            "chapters": {
                "rules": {
                    "title": "Rules",
                    "order": 1,
                    "files": {
                        "index": {"title": "Index", "pages": [1, 1], "order": 0},
                    },
                },
            },
        }
        split_chapters(config, tmp_path)
        assert (output_dir / "bilingual" / "rules" / "index.md").exists()
        rules_meta = output_dir / "bilingual" / "rules" / "_meta.yml"
        assert rules_meta.exists()
