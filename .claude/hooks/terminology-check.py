#!/usr/bin/env python3
"""
Terminology Conflict Hook

Warns (never blocks) when a just-written-back translation file contains a
forbidden term variant from glossary.json. Backstops Codex-authored drafts
(routed via `codex exec`, which bypasses Claude's Write/Edit tools) as well
as Claude-authored ones, since both flow through `draft.py ... writeback`
before landing in published docs content.

Advisory only: this can false-positive (e.g. a forbidden variant appearing
inside a code block or proper noun), so it always exits 0 and only adds
`additionalContext` for Claude to weigh, never a blocking/error signal.
"""

import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"

WRITEBACK_RE = re.compile(r"draft\.py\s+(?:--skill\s+\S+\s+)?writeback\s+(\S+)")


def extract_writeback_target(command: str) -> str | None:
    """Pull the target file path out of a `draft.py ... writeback <path>` command."""
    match = WRITEBACK_RE.search(command)
    if not match:
        return None
    return match.group(1).strip("'\"")


MAX_WARNINGS = 8


def check_file_for_forbidden_terms(file_path: Path) -> list[str]:
    """Return warning lines (capped at MAX_WARNINGS, plus a summary line if truncated)
    for forbidden term variants found in file_path. additionalContext has a 10,000-char
    cap; an unbounded list would silently truncate on a glossary with many entries."""
    sys.path.insert(0, str(SCRIPTS_DIR))
    from _term_lib import DEFAULT_GLOSSARY, find_term_spans, is_managed_term, load_glossary

    glossary = load_glossary(DEFAULT_GLOSSARY)
    content = file_path.read_text(encoding="utf-8")

    warnings = []
    for term, entry in glossary.items():
        if term == "_meta" or not is_managed_term(term, entry):
            continue
        for forbidden in entry.get("forbidden", []):
            hits = find_term_spans(content, forbidden)
            if hits:
                warnings.append(f"「{forbidden}」出現 {len(hits)} 次（術語表核准用法為「{term}」）")

    if len(warnings) > MAX_WARNINGS:
        remaining = len(warnings) - MAX_WARNINGS
        warnings = warnings[:MAX_WARNINGS]
        warnings.append(f"…另有 {remaining} 項，執行 term_read.py 查看完整清單")
    return warnings


def main() -> None:
    try:
        input_data = sys.stdin.read()
        if not input_data.strip():
            sys.exit(0)
        data = json.loads(input_data)

        if data.get("tool_name") != "Bash":
            sys.exit(0)

        command = data.get("tool_input", {}).get("command", "")
        if "draft.py" not in command or "writeback" not in command:
            sys.exit(0)

        target = extract_writeback_target(command)
        if not target:
            sys.exit(0)

        file_path = (PROJECT_ROOT / target) if not Path(target).is_absolute() else Path(target)
        if not file_path.is_file() or file_path.suffix.lower() not in (".md", ".mdx"):
            sys.exit(0)

        warnings = check_file_for_forbidden_terms(file_path)
        if not warnings:
            sys.exit(0)

        rel = file_path.relative_to(PROJECT_ROOT) if file_path.is_relative_to(PROJECT_ROOT) else file_path
        message = (
            f"⚠️ 術語警告（僅供參考，可能誤報）：{rel} 疑似含有禁用詞變體：\n"
            + "\n".join(f"- {w}" for w in warnings)
        )
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
