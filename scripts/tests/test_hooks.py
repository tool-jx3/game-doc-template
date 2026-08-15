"""Tests for the advisory PostToolUse hooks in .claude/hooks/."""

from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

import _term_lib as tl

HOOKS_DIR = Path(__file__).resolve().parents[2] / ".claude" / "hooks"


def _load_hook(name: str):
    spec = importlib.util.spec_from_file_location(
        name.replace("-", "_"), HOOKS_DIR / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestCheckpointCheck:
    def test_counts_chinese_named_untracked_docs_files(self, monkeypatch, tmp_path):
        # git's default core.quotePath renders non-ASCII paths as quoted escape
        # sequences; the count must still see them — zh-TW projects name their
        # chapter files in Chinese.
        mod = _load_hook("checkpoint-check")
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
        docs = tmp_path / "docs" / "src" / "content" / "docs"
        docs.mkdir(parents=True)
        (docs / "戰鬥.md").write_text("內容", encoding="utf-8")
        (docs / "combat.md").write_text("content", encoding="utf-8")
        (docs / "notes.txt").write_text("skip me", encoding="utf-8")
        monkeypatch.setattr(mod, "PROJECT_ROOT", tmp_path)

        assert mod.count_uncommitted_docs_changes() == 2

    def test_warning_message_labels_threshold_not_batch_size(self):
        # WARN_THRESHOLD (10) is ~2x the skills' documented batch size (5);
        # the message must not present 10 as the batch size.
        mod = _load_hook("checkpoint-check")

        message = mod.build_warning_message(12)

        assert "12" in message
        assert "批次大小（10）" not in message
        assert "5" in message


class TestTerminologyCheck:
    def _seed_glossary(self, tmp_path, monkeypatch):
        glossary_path = tmp_path / "glossary.json"
        glossary_path.write_text(
            json.dumps(
                {
                    "_meta": {"description": "測試", "updated": ""},
                    "Warden": {
                        "zh": "守密人",
                        "status": "approved",
                        "forbidden": ["典獄長"],
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr(tl, "DEFAULT_GLOSSARY", glossary_path)

    def test_forbidden_warning_cites_approved_zh_translation(self, monkeypatch, tmp_path):
        # The advisory must point at the approved zh form (entry["zh"]), not the
        # English glossary key — substituting the key into Chinese prose would
        # violate the translation contract.
        mod = _load_hook("terminology-check")
        self._seed_glossary(tmp_path, monkeypatch)

        warnings = mod.check_file_for_forbidden_terms("監獄由典獄長管理。")

        assert len(warnings) == 1
        assert "守密人" in warnings[0]

    def test_extract_check_target_from_bash_writeback(self, monkeypatch, tmp_path):
        mod = _load_hook("terminology-check")
        monkeypatch.setattr(mod, "PROJECT_ROOT", tmp_path)
        data = {
            "tool_name": "Bash",
            "tool_input": {
                "command": (
                    "uv run python scripts/draft.py --skill translate "
                    "writeback docs/src/content/docs/rules/combat.md"
                )
            },
        }

        target = mod.extract_check_target(data)

        assert target == tmp_path / "docs" / "src" / "content" / "docs" / "rules" / "combat.md"

    def test_extract_check_target_from_write_tool(self, monkeypatch, tmp_path):
        # bilingual-translate publishes via a direct Write (no draft.py
        # writeback); the hook must cover that path too.
        mod = _load_hook("terminology-check")
        monkeypatch.setattr(mod, "PROJECT_ROOT", tmp_path)
        target_file = tmp_path / "docs" / "src" / "content" / "docs" / "bilingual" / "combat.md"
        data = {"tool_name": "Write", "tool_input": {"file_path": str(target_file)}}

        assert mod.extract_check_target(data) == target_file

    def test_extract_check_target_ignores_write_outside_docs_content(
        self, monkeypatch, tmp_path
    ):
        mod = _load_hook("terminology-check")
        monkeypatch.setattr(mod, "PROJECT_ROOT", tmp_path)
        data = {
            "tool_name": "Write",
            "tool_input": {"file_path": str(tmp_path / "scripts" / "helper.py")},
        }

        assert mod.extract_check_target(data) is None

    def test_extract_check_target_ignores_unrelated_bash(self, monkeypatch, tmp_path):
        mod = _load_hook("terminology-check")
        monkeypatch.setattr(mod, "PROJECT_ROOT", tmp_path)
        data = {"tool_name": "Bash", "tool_input": {"command": "git status"}}

        assert mod.extract_check_target(data) is None
