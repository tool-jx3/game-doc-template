#!/usr/bin/env python3
"""Clean template/sample data before starting a new translation run."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MARKDOWN_DIR = PROJECT_ROOT / "data" / "markdown"
DOCS_CONTENT_DIR = PROJECT_ROOT / "docs" / "src" / "content" / "docs"
GLOSSARY_PATH = PROJECT_ROOT / "glossary.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Clean sample/template content.")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Apply cleanup directly (otherwise dry-run).",
    )
    return parser.parse_args()


def remove_path(path: Path, apply: bool) -> None:
    rel = path.relative_to(PROJECT_ROOT)
    if path.is_dir():
        print(f"remove dir: {rel}")
        if apply:
            shutil.rmtree(path, ignore_errors=True)
        return
    print(f"remove file: {rel}")
    if apply:
        path.unlink(missing_ok=True)


def clean_markdown_data(apply: bool) -> None:
    if not MARKDOWN_DIR.exists():
        return
    for child in sorted(MARKDOWN_DIR.iterdir()):
        if child.name == ".gitkeep":
            continue
        remove_path(child, apply)


def clean_docs_content(apply: bool) -> None:
    if not DOCS_CONTENT_DIR.exists():
        return
    for path in sorted(DOCS_CONTENT_DIR.rglob("*")):
        if path.is_dir():
            continue
        if path.suffix.lower() not in {".md", ".mdx"}:
            continue
        remove_path(path, apply)

    # remove now-empty directories
    for path in sorted(DOCS_CONTENT_DIR.rglob("*"), reverse=True):
        if path.is_dir() and not any(path.iterdir()):
            rel = path.relative_to(PROJECT_ROOT)
            print(f"remove empty dir: {rel}")
            if apply:
                path.rmdir()


def clean_glossary(apply: bool) -> None:
    if not GLOSSARY_PATH.exists():
        return

    default_description = "術語表 - 英文遊戲術語對照繁體中文翻譯"
    description = default_description

    try:
        current = json.loads(GLOSSARY_PATH.read_text(encoding="utf-8"))
        meta = current.get("_meta", {})
        description = meta.get("description") or default_description
    except Exception:
        description = default_description

    cleaned = {
        "_meta": {
            "description": description,
            "updated": "",
        }
    }

    rel = GLOSSARY_PATH.relative_to(PROJECT_ROOT)
    print(f"reset glossary: {rel}")
    if apply:
        GLOSSARY_PATH.write_text(
            json.dumps(cleaned, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


def main() -> None:
    args = parse_args()
    apply = args.yes
    mode = "APPLY" if apply else "DRY-RUN"
    print(f"[clean-sample-data] mode={mode}")
    print("Target roots:")
    print(f"- {MARKDOWN_DIR.relative_to(PROJECT_ROOT)}")
    print(f"- {DOCS_CONTENT_DIR.relative_to(PROJECT_ROOT)}")
    print(f"- {GLOSSARY_PATH.relative_to(PROJECT_ROOT)}")

    clean_markdown_data(apply)
    clean_docs_content(apply)
    clean_glossary(apply)

    if apply:
        print("✓ Cleanup complete")
    else:
        print("ℹ️ Dry-run only. Re-run with --yes to apply.")


if __name__ == "__main__":
    main()
