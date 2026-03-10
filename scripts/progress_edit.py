#!/usr/bin/env python3
"""Update translation progress entries."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROGRESS = PROJECT_ROOT / "data" / "translation-progress.json"
DEFAULT_CHAPTERS = PROJECT_ROOT / "chapters.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update translation progress.")
    parser.add_argument(
        "--progress-file",
        type=Path,
        default=DEFAULT_PROGRESS,
        help="Path to translation-progress JSON file.",
    )
    parser.add_argument(
        "--file",
        type=str,
        help="Target file path (as stored in progress JSON) to update.",
    )
    parser.add_argument(
        "--status",
        type=str,
        choices=["not_started", "in_progress", "completed"],
        help="Set chapter status.",
    )
    parser.add_argument("--notes", type=str, help="Set notes for the chapter.")
    parser.add_argument(
        "--show",
        action="store_true",
        help="Show current entry for --file.",
    )
    parser.add_argument(
        "--create-if-missing",
        action="store_true",
        help="Create progress file from chapters.json if it does not exist.",
    )
    parser.add_argument(
        "--chapters",
        type=Path,
        default=DEFAULT_CHAPTERS,
        help="Path to chapters.json (used with --create-if-missing).",
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON.")
    return parser.parse_args()


def now_date() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def load_progress(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_progress(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def recalculate_meta(data: dict) -> None:
    """Recalculate _meta.completed, _meta.total_chapters, and _meta.updated."""
    chapters = data.get("chapters", [])
    completed = sum(1 for ch in chapters if ch.get("status") == "completed")
    meta = data.setdefault("_meta", {})
    meta["total_chapters"] = len(chapters)
    meta["completed"] = completed
    meta["updated"] = now_date()


def create_from_chapters(chapters_path: Path) -> dict:
    """Create a fresh progress structure from chapters.json."""
    # Reuse init_create_progress logic
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from init_create_progress import build_progress, load_chapters

    config = load_chapters(chapters_path)
    return build_progress(config)


def find_entry(data: dict, file_path: str) -> dict | None:
    for ch in data.get("chapters", []):
        if ch.get("file") == file_path or ch.get("id") == file_path:
            return ch
    return None


def main() -> None:
    args = parse_args()
    progress_file = args.progress_file
    if not progress_file.is_absolute():
        progress_file = PROJECT_ROOT / progress_file

    data = load_progress(progress_file)

    # Create if missing
    if not data and args.create_if_missing:
        chapters_path = args.chapters
        if not chapters_path.is_absolute():
            chapters_path = PROJECT_ROOT / chapters_path
        data = create_from_chapters(chapters_path)
        save_progress(progress_file, data)
        print(f"✓ 已建立進度檔案：{progress_file}")

    if not data:
        print(f"❌ 進度檔案不存在：{progress_file}", file=sys.stderr)
        print("  使用 --create-if-missing 從 chapters.json 建立。", file=sys.stderr)
        sys.exit(1)

    if not args.file:
        # No file specified — just show summary after any create
        recalculate_meta(data)
        save_progress(progress_file, data)
        meta = data.get("_meta", {})
        if args.json:
            print(json.dumps(meta, ensure_ascii=False, indent=2))
        else:
            print(f"✓ 進度：{meta.get('completed', 0)} / {meta.get('total_chapters', 0)}")
        return

    entry = find_entry(data, args.file)
    if entry is None:
        print(f"❌ 找不到檔案：{args.file}", file=sys.stderr)
        sys.exit(1)

    if args.show:
        print(json.dumps(entry, ensure_ascii=False, indent=2))
        return

    has_mutation = args.status is not None or args.notes is not None
    if not has_mutation:
        print("❌ 未指定要更新的欄位。使用 --status 或 --notes。", file=sys.stderr)
        sys.exit(1)

    if args.status is not None:
        entry["status"] = args.status
    if args.notes is not None:
        entry["notes"] = args.notes

    recalculate_meta(data)
    save_progress(progress_file, data)

    meta = data.get("_meta", {})
    result = {
        "file": entry.get("file"),
        "status": entry.get("status"),
        "notes": entry.get("notes", ""),
        "progress": f"{meta.get('completed', 0)}/{meta.get('total_chapters', 0)}",
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"✓ 已更新：{result['file']}")
        print(f"  狀態：{result['status']}")
        print(f"  進度：{result['progress']}")


if __name__ == "__main__":
    main()
