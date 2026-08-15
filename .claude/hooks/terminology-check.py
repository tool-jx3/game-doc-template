#!/usr/bin/env python3
"""
Terminology & Structure Conflict Hook

Warns (never blocks) when a just-written-back translation file contains:
- a forbidden term variant from glossary.json, or
- a machine-detectable structural defect (unbalanced **bold** markers,
  skipped heading levels) that an LLM reviewer pass can miss — confirmed in
  practice: a broken bold marker once survived a full reviewer+refiner pass.

Coverage: fires on `draft.py ... writeback` Bash commands (the choke point for
translate/super-translate content, Codex- and Claude-authored alike) AND on
Write/Edit tool calls targeting files under docs/src/content/docs — the path
bilingual-translate uses to publish final files directly without a writeback.

Advisory only: every check here can false-positive (a forbidden variant
inside a code block or proper noun; a legitimate `***bold italic***`; a
heading structure that's unconventional but intentional), so this always
exits 0 and only adds `additionalContext` for Claude to weigh, never a
blocking/error signal.
"""

import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
DOCS_CONTENT_DIR = Path("docs") / "src" / "content" / "docs"

WRITEBACK_RE = re.compile(r"draft\.py\s+(?:--skill\s+\S+\s+)?writeback\s+(\S+)")
FENCED_CODE_RE = re.compile(r"```.*?```", re.DOTALL)
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
BOLD_MARKER_RE = re.compile(r"(?<!\*)\*\*(?!\*)")
HEADING_RE = re.compile(r"^(#{1,6})\s+\S", re.MULTILINE)

MAX_WARNINGS = 8


def extract_writeback_target(command: str) -> str | None:
    """Pull the target file path out of a `draft.py ... writeback <path>` command."""
    match = WRITEBACK_RE.search(command)
    if not match:
        return None
    return match.group(1).strip("'\"")


def extract_check_target(data: dict) -> Path | None:
    """Resolve the docs-content file this tool call published, if any.

    - Bash: a `draft.py ... writeback <path>` command (translate/super-translate,
      Codex- and Claude-authored drafts alike).
    - Write/Edit: a file under docs/src/content/docs (bilingual-translate writes
      final files directly, with no writeback command to hook).
    """
    tool_name = data.get("tool_name")
    tool_input = data.get("tool_input", {})

    if tool_name == "Bash":
        target = extract_writeback_target(tool_input.get("command", ""))
        if not target:
            return None
        path = Path(target)
        return path if path.is_absolute() else PROJECT_ROOT / path

    if tool_name in ("Write", "Edit"):
        raw = tool_input.get("file_path", "")
        if not raw:
            return None
        path = Path(raw)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        try:
            path.relative_to(PROJECT_ROOT / DOCS_CONTENT_DIR)
        except ValueError:
            return None
        return path

    return None


def check_file_for_forbidden_terms(content: str) -> list[str]:
    """Return warning lines for forbidden term variants found in content."""
    sys.path.insert(0, str(SCRIPTS_DIR))
    from _term_lib import DEFAULT_GLOSSARY, find_term_spans, is_managed_term, load_glossary

    glossary = load_glossary(DEFAULT_GLOSSARY)

    warnings = []
    for term, entry in glossary.items():
        if term == "_meta" or not is_managed_term(term, entry):
            continue
        # The approved usage in Chinese prose is the entry's zh translation, not
        # the (usually English) glossary key — citing the key would tell the
        # agent to substitute an English word into Chinese text.
        approved = entry.get("zh") or term
        for forbidden in entry.get("forbidden", []):
            hits = find_term_spans(content, forbidden)
            if hits:
                warnings.append(
                    f"「{forbidden}」出現 {len(hits)} 次（術語表核准譯名為「{approved}」，原文 {term}）"
                )
    return warnings


def check_structure(content: str) -> list[str]:
    """Return warning lines for machine-detectable Markdown structure defects."""
    warnings = []

    fence_free = FENCED_CODE_RE.sub("", content)
    code_free = INLINE_CODE_RE.sub("", fence_free)
    bold_count = len(BOLD_MARKER_RE.findall(code_free))
    if bold_count % 2 != 0:
        warnings.append(f"不平衡的 **粗體** 標記（程式碼區塊外共 {bold_count} 個 ** 符號，應為偶數）")

    # Only fence-stripped, not inline-code-stripped: a "# comment" inside a fenced
    # code block must not be treated as a heading, but a heading line is detected
    # by its leading `#` regardless of inline code elsewhere on that same line.
    prev_level = None
    for match in HEADING_RE.finditer(fence_free):
        level = len(match.group(1))
        if prev_level is not None and level > prev_level + 1:
            warnings.append(f"標題階層跳級：從 H{prev_level} 跳到 H{level}（略過中間層級）")
        prev_level = level

    return warnings


def collect_warnings(file_path: Path) -> list[str]:
    """Return warning lines (capped at MAX_WARNINGS, plus a summary line if truncated).
    additionalContext has a 10,000-char cap; an unbounded list would silently
    truncate on a glossary with many entries or a heavily-affected file."""
    content = file_path.read_text(encoding="utf-8")
    warnings = check_file_for_forbidden_terms(content) + check_structure(content)

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

        file_path = extract_check_target(data)
        if file_path is None:
            sys.exit(0)
        if not file_path.is_file() or file_path.suffix.lower() not in (".md", ".mdx"):
            sys.exit(0)

        warnings = collect_warnings(file_path)
        if not warnings:
            sys.exit(0)

        rel = file_path.relative_to(PROJECT_ROOT) if file_path.is_relative_to(PROJECT_ROOT) else file_path
        message = (
            f"⚠️ 術語／結構警告（僅供參考，可能誤報）：{rel} 疑似有以下問題：\n"
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
