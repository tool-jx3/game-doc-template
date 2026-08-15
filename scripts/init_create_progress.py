#!/usr/bin/env python3
"""Create data/translation-progress.json from chapters.json."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from _markdown_utils import iter_leaves
from split_chapters import normalize_files

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CHAPTERS = PROJECT_ROOT / "chapters.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "translation-progress.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate translation progress tracker from chapters config.")
    parser.add_argument("--chapters", type=Path, default=DEFAULT_CHAPTERS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--force", action="store_true", help="Overwrite output file if it exists.")
    parser.add_argument("--json", action="store_true", help="Print generated payload as JSON.")
    return parser.parse_args()


def now_date() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def load_chapters(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"❌ chapters config not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def iter_chapter_files(
    config: dict[str, Any],
) -> list[tuple[str, str, dict[str, Any], str]]:
    """Walk chapter config recursively.

    Returns list of (section_slug, rel_path, file_cfg, source) for each
    leaf node.  The 4th element *source* comes from the chapter-level
    ``source`` field (or top-level fallback).
    """
    chapter_map = config.get("chapters", {})
    output_dir = config.get("output_dir", "docs/src/content/docs")
    mode = config.get("mode", "zh_only")
    base = f"{output_dir}/bilingual" if mode == "bilingual" else output_dir

    results: list[tuple[str, str, dict[str, Any], str]] = []

    for section_slug, section in sorted(
        chapter_map.items(), key=lambda x: x[1].get("order", 9999)
    ):
        if section_slug.startswith("_"):
            continue
        source = section.get("source", config.get("source", ""))
        files = normalize_files(section.get("files", {}))
        _walk_files(
            files,
            path_prefix=f"{base}/{section_slug}",
            section_slug=section_slug,
            source=source,
            results=results,
        )

    return results


def _walk_files(
    files: dict,
    path_prefix: str,
    section_slug: str,
    source: str,
    results: list[tuple[str, str, dict[str, Any], str]],
) -> None:
    """Walk a normalized files dict, collecting leaf nodes.

    Raises:
        ValueError: an entry has neither ``pages`` nor ``files`` (propagated
        from ``iter_leaves``), instead of silently dropping it.
    """
    for key_path, entry in iter_leaves(files):
        results.append((section_slug, f"{path_prefix}/{key_path}.md", entry, source))


def chapter_id_from_path(rel_path: str) -> str:
    # Use PurePosixPath to keep forward slashes on all platforms
    from pathlib import PurePosixPath

    path = PurePosixPath(rel_path)
    # Keep uniqueness across sections (e.g., many index.md files)
    return str(path.with_suffix("")).replace("/", "-")


def page_range_to_string(pages: Any) -> str:
    if isinstance(pages, list) and len(pages) == 2:
        return f"{pages[0]}-{pages[1]}"
    return ""


def build_progress(config: dict[str, Any]) -> dict[str, Any]:
    chapters = []
    for _, rel_path, file_cfg, source in iter_chapter_files(config):
        title = str(file_cfg.get("title", Path(rel_path).stem))
        entry: dict[str, Any] = {
            "id": chapter_id_from_path(rel_path),
            "title": title,
            "file": rel_path,
            "source_pages": page_range_to_string(file_cfg.get("pages")),
            "status": "not_started",
            "notes": "",
        }
        if source:
            entry["source"] = source
        chapters.append(entry)

    payload = {
        "_meta": {
            "description": "Translation progress tracker",
            "updated": now_date(),
            "total_chapters": len(chapters),
            "completed": 0,
        },
        "chapters": chapters,
    }
    return payload


def main() -> None:
    args = parse_args()
    chapters_path = args.chapters if args.chapters.is_absolute() else PROJECT_ROOT / args.chapters
    output_path = args.output if args.output.is_absolute() else PROJECT_ROOT / args.output

    if output_path.exists() and not args.force:
        raise SystemExit(f"❌ output exists: {output_path} (use --force to overwrite)")

    config = load_chapters(chapters_path)
    payload = build_progress(config)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"✓ created: {output_path}")
    print(f"  total chapters: {payload['_meta']['total_chapters']}")

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
