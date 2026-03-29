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


def sorted_files(section: dict) -> list[tuple[str, dict]]:
    """Return files in a section sorted by order."""
    return sorted(section.get("files", {}).items(), key=lambda x: x[1].get("order", 9999))


def mode_prefix(mode: str) -> str:
    return "bilingual/" if mode == "bilingual" else ""


def section_primary_slug(section_slug: str, section: dict, mode: str = "zh_only") -> str:
    """Return the primary doc slug for a section."""
    files = sorted_files(section)
    prefix = mode_prefix(mode)
    if not files:
        return f"{prefix}{section_slug}"

    filename, _config = files[0]
    if filename == "index":
        return f"{prefix}{section_slug}"
    return f"{prefix}{section_slug}/{filename}"


def section_primary_href(section_slug: str, section: dict, mode: str = "zh_only") -> str:
    """Return the primary doc href for a section."""
    return f"/{section_primary_slug(section_slug, section, mode)}/"


def first_file_description(section: dict) -> str:
    """Get description from the first file in section (usually index)."""
    for _fname, cfg in sorted_files(section):
        desc = cfg.get("description", "")
        if desc:
            return desc
    return ""


def yaml_safe(value: str) -> str:
    """Wrap YAML-sensitive scalars in double quotes."""
    if any(
        ch in value
        for ch in (
            ":",
            "：",
            "#",
            "{",
            "}",
            "[",
            "]",
            ",",
            "&",
            "*",
            "?",
            "|",
            "-",
            "<",
            ">",
            "=",
            "!",
            "%",
            "@",
            "`",
        )
    ):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value


# --- Index page generation ---

def generate_index(chapters: dict, style: dict, mode: str = "zh_only") -> str:
    sections = sorted_sections(chapters)
    first_slug = sections[0][0] if sections else "reference"
    second_slug = sections[1][0] if len(sections) > 1 else first_slug

    # Hero actions point to first two sections
    first_title = sections[0][1]["title"] if sections else "開始閱讀"
    second_title = sections[1][1]["title"] if len(sections) > 1 else ""
    first_href = section_primary_href(first_slug, sections[0][1], mode) if sections else "/reference/"
    second_href = (
        section_primary_href(second_slug, sections[1][1], mode)
        if len(sections) > 1
        else first_href
    )

    site = style.get("site", {})
    title = site.get("title", "遊戲規則文件")
    description = site.get("description", "遊戲規則文件首頁")
    tagline = site.get("tagline", "快速查閱核心規則、角色、裝備與主持指南")
    intro = site.get("intro", "本站整理遊戲規則的主要章節，提供易讀、可搜尋的文件版本，方便跑團前準備與遊戲中快速查表。")

    lines = [
        "---",
        f"title: {yaml_safe(title)}",
        f"description: {yaml_safe(description)}",
        "template: splash",
        "hero:",
        f"  tagline: {yaml_safe(tagline)}",
        "  image:",
        "    file: ../../assets/hero.jpg",
        "  actions:",
        f"    - text: {yaml_safe(first_title)}",
        f"      link: {first_href}",
        "      icon: right-arrow",
    ]
    if second_title:
        lines += [
            f"    - text: {yaml_safe(second_title)}",
            f"      link: {second_href}",
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
        intro,
        "",
        "## 快速導航",
        "",
        "<CardGrid>",
    ]

    for slug, section in sections:
        title = section["title"]
        desc = first_file_description(section)
        href = section_primary_href(slug, section, mode)
        lines.append(f'  <LinkCard title="{title}" href="{href}" description="{desc}" />')

    lines += [
        "</CardGrid>",
        "",
        "---",
        "",
    ]

    copyright_cfg = style.get("copyright", {})
    credits_cfg = style.get("credits", {})
    has_copyright = copyright_cfg.get("show_on_homepage") and copyright_cfg.get("text")
    has_credits = credits_cfg.get("show_on_homepage") and credits_cfg.get("entries")

    if has_copyright:
        lines += [
            "## 版權宣告",
            "",
            copyright_cfg["text"],
            "",
        ]
    if has_credits:
        lines += [
            "## 製作名單",
            "",
            "| 職責 | 人員 |",
            "| --- | --- |",
        ]
        for entry in credits_cfg["entries"]:
            role = entry.get("role", "")
            name = entry.get("name", "")
            lines.append(f"| {role} | {name} |")
        lines.append("")
    if not has_copyright and not has_credits:
        lines += [
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

def generate_sidebar_entries(chapters: dict, mode: str = "zh_only") -> str:
    """Generate JS sidebar array entries."""
    sections = sorted_sections(chapters)
    entries = []
    for slug, section in sections:
        title = section["title"]
        files = sorted_files(section)
        if len(files) == 1:
            primary_slug = section_primary_slug(slug, section, mode)
            entries.append(
                f"\t\t\t\t{{\n"
                f"\t\t\t\t\tlabel: '{title}',\n"
                f"\t\t\t\t\tslug: '{primary_slug}',\n"
                f"\t\t\t\t}}"
            )
            continue

        directory = f"{mode_prefix(mode)}{slug}"
        entries.append(
            f"\t\t\t\t{{\n"
            f"\t\t\t\t\tlabel: '{title}',\n"
            f"\t\t\t\t\tautogenerate: {{ directory: '{directory}' }},\n"
            f"\t\t\t\t}}"
        )
    return ",\n".join(entries)


def update_astro_sidebar(config_text: str, chapters: dict, mode: str = "zh_only") -> str:
    """Replace sidebar array content in astro.config.mjs."""
    entries = generate_sidebar_entries(chapters, mode=mode)
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

    chapters_data = load_json(CHAPTERS_FILE)
    if "chapters" in chapters_data:
        chapters = chapters_data["chapters"]
        mode = chapters_data.get("mode", "zh_only")
    else:
        chapters = chapters_data
        mode = "zh_only"
    if not chapters:
        print("❌ chapters.json 中沒有章節資料", file=sys.stderr)
        raise SystemExit(1)

    style = load_json(STYLE_FILE) if STYLE_FILE.exists() else {}

    # Generate index.mdx
    index_content = generate_index(chapters, style, mode=mode)
    INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
    INDEX_FILE.write_text(index_content, encoding="utf-8")
    print(f"✓ 已產生首頁: {INDEX_FILE}")

    # Update astro.config.mjs sidebar
    if ASTRO_CONFIG.exists():
        original = ASTRO_CONFIG.read_text(encoding="utf-8")
        updated = update_astro_sidebar(original, chapters, mode=mode)
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
