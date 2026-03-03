#!/usr/bin/env python3
"""Generate homepage index.mdx and update astro.config.mjs sidebar from chapters.json."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CHAPTERS_FILE = PROJECT_ROOT / "chapters.json"
STYLE_FILE = PROJECT_ROOT / "style-decisions.json"
INDEX_FILE = PROJECT_ROOT / "docs" / "src" / "content" / "docs" / "index.mdx"
ASTRO_CONFIG = PROJECT_ROOT / "docs" / "astro.config.mjs"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sorted_sections(chapters: dict) -> list[tuple[str, dict]]:
    """Return chapter sections sorted by order."""
    return sorted(chapters.items(), key=lambda x: x[1].get("order", 9999))


def first_file_description(section: dict) -> str:
    """Get description from the first file in section (usually index)."""
    files = section.get("files", {})
    for _fname, cfg in sorted(files.items(), key=lambda x: x[1].get("order", 9999)):
        desc = cfg.get("description", "")
        if desc:
            return desc
    return ""


# --- Index page generation ---

def generate_index(chapters: dict, style: dict) -> str:
    sections = sorted_sections(chapters)
    first_slug = sections[0][0] if sections else "reference"
    second_slug = sections[1][0] if len(sections) > 1 else first_slug

    # Hero actions point to first two sections
    first_title = sections[0][1]["title"] if sections else "開始閱讀"
    second_title = sections[1][1]["title"] if len(sections) > 1 else ""

    lines = [
        "---",
        "title: 遊戲規則文件",
        "description: 遊戲規則文件首頁",
        "template: splash",
        "hero:",
        "  tagline: 快速查閱核心規則、角色、裝備與主持指南",
        "  image:",
        "    file: ../../assets/hero.jpg",
        "  actions:",
        f"    - text: {first_title}",
        f"      link: /{first_slug}/",
        "      icon: right-arrow",
    ]
    if second_title:
        lines += [
            f"    - text: {second_title}",
            f"      link: /{second_slug}/",
            "      icon: document",
            "      variant: minimal",
        ]
    lines += [
        "sidebar:",
        "  order: 0",
        "---",
        "",
        "import { CardGrid, LinkCard } from '@astrojs/starlight/components';",
        "",
        "## 內容簡介",
        "",
        "本站整理遊戲規則的主要章節，提供易讀、可搜尋的文件版本，方便跑團前準備與遊戲中快速查表。",
        "",
        "## 快速導航",
        "",
        "<CardGrid>",
    ]

    for slug, section in sections:
        title = section["title"]
        desc = first_file_description(section)
        lines.append(f'  <LinkCard title="{title}" href="/{slug}/" description="{desc}" />')

    lines += [
        "</CardGrid>",
        "",
        "---",
        "",
        "## 聲明",
        "",
        "本站內容為規則整理與翻譯文件，僅供個人遊戲參考使用。原文著作權與商標權歸原作者與出版方所有，請支持正版。",
    ]

    # Add repo link if configured
    repo = style.get("repository", {})
    if repo.get("show_on_homepage") and repo.get("url"):
        url = repo["url"]
        lines += [
            "",
            f"[GitHub 原始碼]({url})",
        ]

    return "\n".join(lines) + "\n"


# --- Sidebar generation ---

def generate_sidebar_entries(chapters: dict) -> str:
    """Generate JS sidebar array entries."""
    sections = sorted_sections(chapters)
    entries = []
    for slug, section in sections:
        title = section["title"]
        entries.append(
            f"\t\t\t\t{{\n"
            f"\t\t\t\t\tlabel: '{title}',\n"
            f"\t\t\t\t\tautogenerate: {{ directory: '{slug}' }},\n"
            f"\t\t\t\t}}"
        )
    return ",\n".join(entries)


def update_astro_sidebar(config_text: str, chapters: dict) -> str:
    """Replace sidebar array content in astro.config.mjs."""
    entries = generate_sidebar_entries(chapters)
    # Match the sidebar array: sidebar: [ ... ],
    pattern = r"(sidebar:\s*\[)\s*\n.*?\n(\s*\],)"
    replacement = f"\\1\n{entries}\n\\2"
    result, count = re.subn(pattern, replacement, config_text, flags=re.DOTALL)
    if count == 0:
        print("⚠ 無法定位 astro.config.mjs 中的 sidebar 陣列", file=sys.stderr)
        return config_text
    return result


def main() -> None:
    if not CHAPTERS_FILE.exists():
        print(f"❌ 找不到 {CHAPTERS_FILE}", file=sys.stderr)
        raise SystemExit(1)

    config = load_json(CHAPTERS_FILE)
    chapters = config.get("chapters", {})
    if not chapters:
        print("❌ chapters.json 中沒有章節資料", file=sys.stderr)
        raise SystemExit(1)

    style = load_json(STYLE_FILE) if STYLE_FILE.exists() else {}

    # Generate index.mdx
    index_content = generate_index(chapters, style)
    INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
    INDEX_FILE.write_text(index_content, encoding="utf-8")
    print(f"✓ 已產生首頁: {INDEX_FILE}")

    # Update astro.config.mjs sidebar
    if ASTRO_CONFIG.exists():
        original = ASTRO_CONFIG.read_text(encoding="utf-8")
        updated = update_astro_sidebar(original, chapters)
        if updated != original:
            ASTRO_CONFIG.write_text(updated, encoding="utf-8")
            print(f"✓ 已更新側邊欄: {ASTRO_CONFIG}")
        else:
            print("ℹ 側邊欄未變更")
    else:
        print(f"⚠ 找不到 {ASTRO_CONFIG}", file=sys.stderr)

    # Summary
    sections = sorted_sections(chapters)
    print(f"\n章節清單 ({len(sections)} 個):")
    for slug, section in sections:
        print(f"  /{slug}/ → {section['title']}")


if __name__ == "__main__":
    main()
