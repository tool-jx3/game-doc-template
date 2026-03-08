#!/usr/bin/env python3
"""
Draft management for translation workflow.

Commands:
    path <source>      Create stub draft with _draft_source frontmatter; print draft path
    writeback <source> Strip _draft_* frontmatter fields and write draft back to source
    clean              Remove all drafts for the specified skill

Options:
    --skill  translate | super-translate  (default: translate)

Examples:
    DRAFT=$(uv run python scripts/draft.py path docs/src/content/docs/rules/basic.md)
    uv run python scripts/draft.py writeback docs/src/content/docs/rules/basic.md
    uv run python scripts/draft.py --skill super-translate path docs/src/content/docs/rules/basic.md
    uv run python scripts/draft.py clean
"""

import argparse
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
VALID_SKILLS = ("translate", "super-translate")
_FM_RE = re.compile(r"^---\n(.*?)\n---\n?(.*)", re.DOTALL)


def _draft_path(source: Path, skill: str) -> Path:
    draft_root = ROOT / ".claude" / "skills" / skill / ".state" / "drafts"
    return draft_root / source


def _strip_draft_fields(content: str) -> str:
    """Remove lines starting with _draft_ from YAML frontmatter."""
    match = _FM_RE.match(content)
    if not match:
        return content
    fm_lines = [l for l in match.group(1).splitlines() if not l.startswith("_draft_")]
    body = match.group(2)
    return "---\n" + "\n".join(fm_lines) + "\n---\n" + body


def cmd_path(source_str: str, skill: str) -> None:
    source = Path(source_str)
    draft = _draft_path(source, skill)
    draft.parent.mkdir(parents=True, exist_ok=True)
    # Write stub so the draft file exists and carries source path in frontmatter
    if not draft.exists():
        draft.write_text(f"---\n_draft_source: {source_str}\n---\n")
    print(draft)


def cmd_writeback(source_str: str, skill: str) -> None:
    source = Path(source_str)
    draft = _draft_path(source, skill)
    if not draft.exists():
        print(f"Error: draft not found: {draft}", file=sys.stderr)
        sys.exit(1)
    content = draft.read_text(encoding="utf-8")
    cleaned = _strip_draft_fields(content)
    abs_source = ROOT / source
    abs_source.parent.mkdir(parents=True, exist_ok=True)
    abs_source.write_text(cleaned, encoding="utf-8")
    draft.unlink()
    print(f"Writeback: {draft.relative_to(ROOT)} → {source}", file=sys.stderr)


def cmd_clean(skill: str) -> None:
    draft_dir = ROOT / ".claude" / "skills" / skill / ".state" / "drafts"
    if draft_dir.exists():
        shutil.rmtree(draft_dir)
        print(f"Cleaned: {draft_dir.relative_to(ROOT)}", file=sys.stderr)
    else:
        print(f"No drafts found for skill '{skill}'", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Draft management for translation workflow",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--skill",
        choices=VALID_SKILLS,
        default="translate",
        help="Skill context (default: translate)",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    p_path = sub.add_parser("path", help="Create stub draft and print draft path")
    p_path.add_argument("source", help="Source file path relative to project root")

    p_wb = sub.add_parser("writeback", help="Strip _draft_* fields and write draft to source")
    p_wb.add_argument("source", help="Source file path relative to project root")

    sub.add_parser("clean", help="Remove all drafts for the specified skill")

    args = parser.parse_args()

    if args.command == "path":
        cmd_path(args.source, args.skill)
    elif args.command == "writeback":
        cmd_writeback(args.source, args.skill)
    elif args.command == "clean":
        cmd_clean(args.skill)


if __name__ == "__main__":
    main()
