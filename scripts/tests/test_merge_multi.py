"""Tests for merge_multi module."""

import json
import pytest
from pathlib import Path

from merge_multi import merge_configs, validate_merge


class TestMergeConfigs:
    def _make_config(self, slug, title, order, source, chapters=None):
        return {
            "slug": slug,
            "title": title,
            "order": order,
            "source": source,
            "output_dir": "docs/src/content/docs",
            "mode": "bilingual",
            "chapters": chapters or {},
        }

    def test_single_config_produces_one_chapter(self):
        configs = [
            self._make_config("core", "Core Rules", 1, "core_pages.md", {
                "combat": {
                    "title": "Combat",
                    "order": 1,
                    "files": {"actions": {"title": "Actions", "pages": [5, 7], "order": 0}},
                }
            })
        ]
        result = merge_configs(configs)
        assert "core" in result["chapters"]
        assert result["chapters"]["core"]["source"] == "core_pages.md"
        assert result["chapters"]["core"]["title"] == "Core Rules"
        # Original chapters become files (demoted one level)
        assert "combat" in result["chapters"]["core"]["files"]
        assert "actions" in result["chapters"]["core"]["files"]["combat"]["files"]

    def test_two_configs_both_present(self):
        configs = [
            self._make_config("core", "Core", 1, "core.md"),
            self._make_config("exp", "Expansion", 2, "exp.md"),
        ]
        result = merge_configs(configs)
        assert "core" in result["chapters"]
        assert "exp" in result["chapters"]

    def test_inherits_mode_from_first(self):
        c1 = self._make_config("a", "A", 1, "a.md")
        c1["mode"] = "bilingual"
        c2 = self._make_config("b", "B", 2, "b.md")
        c2["mode"] = "zh_only"
        result = merge_configs([c1, c2])
        assert result["mode"] == "bilingual"

    def test_inherits_output_dir_from_first(self):
        c1 = self._make_config("a", "A", 1, "a.md")
        c1["output_dir"] = "custom/path"
        result = merge_configs([c1])
        assert result["output_dir"] == "custom/path"

    def test_chapter_level_clean_patterns(self):
        c1 = self._make_config("core", "Core", 1, "core.md")
        c1["clean_patterns"] = ["\\[footer\\]"]
        result = merge_configs([c1])
        assert result["chapters"]["core"]["clean_patterns"] == ["\\[footer\\]"]

    def test_chapter_level_images(self):
        c1 = self._make_config("core", "Core", 1, "core.md")
        c1["images"] = {"enabled": True, "assets_dir": "docs/src/assets"}
        result = merge_configs([c1])
        assert result["chapters"]["core"]["images"]["enabled"] is True

    def test_source_injected_into_chapter(self):
        configs = [self._make_config("core", "Core", 1, "core_pages.md")]
        result = merge_configs(configs)
        assert result["chapters"]["core"]["source"] == "core_pages.md"

    def test_mode_override(self):
        configs = [self._make_config("a", "A", 1, "a.md")]
        result = merge_configs(configs, mode_override="zh_only")
        assert result["mode"] == "zh_only"

    def test_output_dir_override(self):
        configs = [self._make_config("a", "A", 1, "a.md")]
        result = merge_configs(configs, output_dir_override="custom")
        assert result["output_dir"] == "custom"


class TestValidateMerge:
    def test_duplicate_slugs_raises(self):
        configs = [
            {"slug": "core", "title": "A", "order": 1, "source": "a.md", "chapters": {}},
            {"slug": "core", "title": "B", "order": 2, "source": "b.md", "chapters": {}},
        ]
        with pytest.raises(ValueError, match="core"):
            validate_merge(configs)

    def test_duplicate_orders_warns(self, capsys):
        configs = [
            {"slug": "a", "title": "A", "order": 1, "source": "a.md", "chapters": {}},
            {"slug": "b", "title": "B", "order": 1, "source": "b.md", "chapters": {}},
        ]
        validate_merge(configs)  # Should not raise
        captured = capsys.readouterr()
        assert "order" in captured.err.lower() or "order" in captured.out.lower()

    def test_valid_configs_pass(self):
        configs = [
            {"slug": "a", "title": "A", "order": 1, "source": "a.md", "chapters": {}},
            {"slug": "b", "title": "B", "order": 2, "source": "b.md", "chapters": {}},
        ]
        validate_merge(configs)  # Should not raise
