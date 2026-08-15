#!/usr/bin/env python3
"""
Batch Checkpoint Hook

Warns (never blocks) when translated docs content has piled up uncommitted
past a full batch's worth of files. translate/super-translate/bilingual-translate
all document "commit immediately after each completed batch" (default batch
size 5), but evidence across real projects showed this is easy to drift from
during a long unattended run — mega-commits bundling 30+ chapters with zero
intermediate checkpoints were common.

Fires after `progress_edit.py ... --status completed` calls (the per-file
"just finished translating" signal) and checks how many docs-content files
are sitting as uncommitted git changes. Advisory only: this can false-positive
(e.g. a legitimately large single commit, or unrelated uncommitted work in the
same tree), so it always exits 0 and only adds `additionalContext`.
"""

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DOCS_CONTENT_DIR = "docs/src/content/docs"

# The skills' documented default batch size, quoted in the warning copy.
BATCH_SIZE = 5
# ~2x the batch size — avoids firing at the expected "just finished this
# batch, about to commit" moment, only flags when a checkpoint has clearly
# been skipped for 1.5-2+ batches.
WARN_THRESHOLD = 10


def count_uncommitted_docs_changes() -> int:
    result = subprocess.run(
        # -uall: without it, a wholly-new untracked chapter subdirectory collapses
        # into one "?? path/" line and every file inside it is invisible to the
        # .md/.mdx filter below — exactly the mega-batch case this hook exists to catch.
        # core.quotePath=false: with the default, non-ASCII paths (the norm for
        # Chinese-named chapter files) render as quoted escape sequences ending in
        # '"', which the suffix filter would silently drop.
        ["git", "-c", "core.quotePath=false", "status", "--short", "-uall", "--", DOCS_CONTENT_DIR],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
        timeout=10,
    )
    if result.returncode != 0:
        return 0
    lines = [
        line for line in result.stdout.splitlines()
        # Paths with spaces/special characters stay quoted even with
        # quotePath=false, so tolerate a trailing quote before the suffix check.
        if line.strip().rstrip('"').lower().endswith((".md", ".mdx"))
    ]
    return len(lines)


def build_warning_message(count: int) -> str:
    return (
        f"⚠️ Checkpoint 提醒（僅供參考，可能誤報）：{DOCS_CONTENT_DIR} 下有 {count} 個已修改但尚未 commit 的檔案，"
        f"超過警戒值 {WARN_THRESHOLD}（約兩個批次）。SKILL.md 要求每個 batch（預設 {BATCH_SIZE} 檔）完成後立刻 commit"
        "（`progress: X/Y`），建議現在補上 checkpoint commit 再繼續下一批。"
    )


def main() -> None:
    try:
        input_data = sys.stdin.read()
        if not input_data.strip():
            sys.exit(0)
        data = json.loads(input_data)

        if data.get("tool_name") != "Bash":
            sys.exit(0)

        command = data.get("tool_input", {}).get("command", "")
        if "progress_edit.py" not in command or "completed" not in command:
            sys.exit(0)

        count = count_uncommitted_docs_changes()
        if count <= WARN_THRESHOLD:
            sys.exit(0)

        message = build_warning_message(count)
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": message,
            }
        }))
        sys.exit(0)
    except Exception:
        # Advisory-only hook: any internal failure must never interfere with the workflow.
        sys.exit(0)


if __name__ == "__main__":
    main()
