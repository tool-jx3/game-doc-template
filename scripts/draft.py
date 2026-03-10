#!/usr/bin/env python3
"""
Draft management for translation workflow.

Commands:
    path <source>         Create empty draft file and register it in manifest; print draft path
    chunk-path <source>   Split source at H2 boundaries into chunk drafts; print each chunk path
    writeback <source>    Write draft (or merge chunks) back to source using manifest metadata
    clean                 Remove all drafts for the specified skill

Options:
    --skill  translate | super-translate  (default: translate)

Examples:
    DRAFT=$(uv run python scripts/draft.py path docs/src/content/docs/rules/basic.md)
    uv run python scripts/draft.py writeback docs/src/content/docs/rules/basic.md

    # For large files: split into H2 chunks, translate each, then merge back
    uv run python scripts/draft.py chunk-path docs/src/content/docs/rules/combat.md
    uv run python scripts/draft.py writeback docs/src/content/docs/rules/combat.md

    uv run python scripts/draft.py --skill super-translate path docs/src/content/docs/rules/basic.md
    uv run python scripts/draft.py clean
"""

import argparse
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
VALID_SKILLS = ("translate", "super-translate")
_FM_RE = re.compile(r"^---\n(.*?)\n---\n?(.*)", re.DOTALL)
_H2_SPLIT_RE = re.compile(r"(?=^## )", re.MULTILINE)


def _draft_path(source: Path, skill: str) -> Path:
    draft_root = ROOT / ".claude" / "skills" / skill / ".state" / "drafts"
    return draft_root / source


def _manifest_path(skill: str) -> Path:
    state_root = ROOT / ".claude" / "skills" / skill / ".state"
    return state_root / "draft-manifest.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _load_manifest(skill: str) -> dict:
    manifest_path = _manifest_path(skill)
    if not manifest_path.exists():
        return {"entries": {}}
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _save_manifest(skill: str, manifest: dict) -> None:
    manifest_path = _manifest_path(skill)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _strip_draft_fields(content: str) -> str:
    """Remove legacy lines starting with _draft_ from YAML frontmatter."""
    match = _FM_RE.match(content)
    if not match:
        return content
    fm_lines = [l for l in match.group(1).splitlines() if not l.startswith("_draft_")]
    body = match.group(2)
    return "---\n" + "\n".join(fm_lines) + "\n---\n" + body


def _extract_fm_and_body(content: str) -> tuple[str, str]:
    """Return (frontmatter_block, body). frontmatter_block includes the --- delimiters."""
    match = _FM_RE.match(content)
    if match:
        fm = f"---\n{match.group(1)}\n---\n"
        body = match.group(2)
    else:
        fm = ""
        body = content
    return fm, body


def _split_body_at_h2(body: str) -> list[str]:
    """Split body at H2 boundaries. Each chunk starts with its ## heading (if any)."""
    sections = _H2_SPLIT_RE.split(body)
    return [s for s in sections if s.strip()]


def cmd_path(source_str: str, skill: str) -> None:
    source = Path(source_str)
    draft = _draft_path(source, skill)
    draft.parent.mkdir(parents=True, exist_ok=True)
    if not draft.exists():
        draft.write_text("", encoding="utf-8")

    manifest = _load_manifest(skill)
    entries = manifest.setdefault("entries", {})
    entries[source_str] = {
        "source": source_str,
        "draft": str(draft.relative_to(ROOT).as_posix()),
        "updated": _now_iso(),
    }
    _save_manifest(skill, manifest)
    print(draft)


def cmd_chunk_path(source_str: str, skill: str) -> None:
    """Split source file at H2 boundaries into chunk drafts. Prints each chunk path."""
    source = Path(source_str)
    abs_source = ROOT / source
    if not abs_source.exists():
        print(f"Error: source not found: {abs_source}", file=sys.stderr)
        sys.exit(1)

    content = abs_source.read_text(encoding="utf-8")
    fm, body = _extract_fm_and_body(content)
    sections = _split_body_at_h2(body)

    if len(sections) <= 1:
        # No meaningful H2 split; fall back to single draft
        print(f"Warning: no H2 sections found in {source_str}; using single draft", file=sys.stderr)
        cmd_path(source_str, skill)
        return

    # Build chunk contents: frontmatter goes only into the first chunk
    chunks: list[str] = []
    for i, section in enumerate(sections):
        if i == 0:
            chunks.append(fm + section if fm else section)
        else:
            chunks.append(section)

    # Determine base path for chunk files (stem strips .md extension)
    draft_base = _draft_path(source, skill)
    draft_base.parent.mkdir(parents=True, exist_ok=True)
    stem = draft_base.stem  # e.g. "combat"

    chunk_paths: list[Path] = []
    for i, chunk_content in enumerate(chunks):
        chunk_file = draft_base.parent / f"{stem}.chunk-{i}.md"
        chunk_file.write_text(chunk_content, encoding="utf-8")
        chunk_paths.append(chunk_file)

    # Register in manifest
    manifest = _load_manifest(skill)
    entries = manifest.setdefault("entries", {})
    entries[source_str] = {
        "source": source_str,
        "chunks": [str(p.relative_to(ROOT).as_posix()) for p in chunk_paths],
        "updated": _now_iso(),
    }
    _save_manifest(skill, manifest)

    for p in chunk_paths:
        print(p)


def cmd_writeback(source_str: str, skill: str) -> None:
    manifest = _load_manifest(skill)
    entry = manifest.get("entries", {}).get(source_str)
    if entry is None:
        print(f"Error: draft manifest entry not found for: {source_str}", file=sys.stderr)
        sys.exit(1)

    # Chunked entry: merge all chunks back into source
    if entry.get("chunks"):
        _merge_chunks_writeback(source_str, entry, skill, manifest)
        return

    # Single-draft entry (original behaviour)
    source = Path(source_str)
    draft_str = entry.get("draft")
    if not draft_str:
        print(f"Error: draft path missing in manifest for: {source_str}", file=sys.stderr)
        sys.exit(1)
    draft = ROOT / Path(draft_str)
    if not draft.exists():
        print(f"Error: draft not found: {draft}", file=sys.stderr)
        sys.exit(1)
    content = draft.read_text(encoding="utf-8")
    cleaned = _strip_draft_fields(content)
    abs_source = ROOT / source
    abs_source.parent.mkdir(parents=True, exist_ok=True)
    abs_source.write_text(cleaned, encoding="utf-8")
    draft.unlink()
    manifest["entries"].pop(source_str, None)
    _save_manifest(skill, manifest)
    print(f"Writeback: {draft.relative_to(ROOT)} → {source}", file=sys.stderr)


def _merge_chunks_writeback(source_str: str, entry: dict, skill: str, manifest: dict) -> None:
    """Read all chunk drafts in order, merge, write back to source."""
    chunk_strs: list[str] = entry["chunks"]
    merged_parts: list[str] = []

    for i, chunk_str in enumerate(chunk_strs):
        chunk_path = ROOT / Path(chunk_str)
        if not chunk_path.exists():
            print(f"Error: chunk draft not found: {chunk_path}", file=sys.stderr)
            sys.exit(1)
        raw = chunk_path.read_text(encoding="utf-8")
        cleaned = _strip_draft_fields(raw)

        # Strip frontmatter from all chunks except the first
        if i > 0:
            fm_match = _FM_RE.match(cleaned)
            if fm_match:
                cleaned = fm_match.group(2)
            cleaned = cleaned.lstrip("\n")

        merged_parts.append(cleaned)

    merged = "\n".join(merged_parts)
    # Collapse excessive blank lines (3+ → 2)
    merged = re.sub(r"\n{3,}", "\n\n", merged)

    source = Path(source_str)
    abs_source = ROOT / source
    abs_source.parent.mkdir(parents=True, exist_ok=True)
    abs_source.write_text(merged, encoding="utf-8")

    # Clean up chunk files
    for chunk_str in chunk_strs:
        (ROOT / Path(chunk_str)).unlink(missing_ok=True)
    manifest["entries"].pop(source_str, None)
    _save_manifest(skill, manifest)
    print(f"Merge writeback: {len(chunk_strs)} chunks → {source_str}", file=sys.stderr)


def cmd_clean(skill: str) -> None:
    draft_dir = ROOT / ".claude" / "skills" / skill / ".state" / "drafts"
    manifest_path = _manifest_path(skill)
    if draft_dir.exists():
        shutil.rmtree(draft_dir)
        print(f"Cleaned: {draft_dir.relative_to(ROOT)}", file=sys.stderr)
    else:
        print(f"No drafts found for skill '{skill}'", file=sys.stderr)
    if manifest_path.exists():
        manifest_path.unlink()


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

    p_path = sub.add_parser("path", help="Create draft file, register manifest entry, and print draft path")
    p_path.add_argument("source", help="Source file path relative to project root")

    p_chunk = sub.add_parser(
        "chunk-path",
        help="Split source at H2 boundaries into chunk drafts; print each chunk path",
    )
    p_chunk.add_argument("source", help="Source file path relative to project root")

    p_wb = sub.add_parser("writeback", help="Write draft (or merge chunk drafts) back to source")
    p_wb.add_argument("source", help="Source file path relative to project root")

    sub.add_parser("clean", help="Remove all drafts for the specified skill")

    args = parser.parse_args()

    if args.command == "path":
        cmd_path(args.source, args.skill)
    elif args.command == "chunk-path":
        cmd_chunk_path(args.source, args.skill)
    elif args.command == "writeback":
        cmd_writeback(args.source, args.skill)
    elif args.command == "clean":
        cmd_clean(args.skill)


if __name__ == "__main__":
    main()
