"""Markdown 文字處理共用工具函式。"""

import re
from urllib.parse import unquote

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LINKED_MARKDOWN_IMAGE_RE = re.compile(r"\[!\[[^\]]*]\([^)]+\)]\([^)]+\)")
MARKDOWN_IMAGE_RE = re.compile(r"!\[[^\]]*]\([^)]+\)")
MARKDOWN_HEADING_RE = re.compile(r"^#{1,3}\s+\S")


# ---------------------------------------------------------------------------
# Functions from extract_pdf.py
# ---------------------------------------------------------------------------


def strip_markdown_images(text: str) -> str:
    """移除 Markdown 圖片語法，避免後續依 manifest 再插圖時重複。"""
    stripped = LINKED_MARKDOWN_IMAGE_RE.sub("", text)
    stripped = MARKDOWN_IMAGE_RE.sub("", stripped)
    stripped = re.sub(r"\n{3,}", "\n\n", stripped)
    return stripped.strip()


def extract_markdown_image_targets(text: str) -> list[str]:
    """擷取 Markdown 中的圖片路徑。"""
    targets: list[str] = []
    for match in MARKDOWN_IMAGE_RE.finditer(text):
        target = match.group(0).split("](", 1)[1].rsplit(")", 1)[0].strip()
        target = target.split(maxsplit=1)[0].strip("<>")
        if target:
            targets.append(unquote(target))
    return targets


def split_markdown_sections(text: str) -> list[str]:
    """依 heading 將 Markdown 切成較細的虛擬頁碼區塊。"""
    lines = text.splitlines()
    sections: list[str] = []
    current: list[str] = []

    for line in lines:
        if MARKDOWN_HEADING_RE.match(line) and any(part.strip() for part in current):
            section = "\n".join(current).strip()
            if section:
                sections.append(section)
            current = [line]
            continue
        current.append(line)

    if any(part.strip() for part in current):
        section = "\n".join(current).strip()
        if section:
            sections.append(section)

    return sections or [text.strip()]


# ---------------------------------------------------------------------------
# Functions from split_chapters.py
# ---------------------------------------------------------------------------


def clean_content(text: str, patterns: list[str]) -> str:
    """清理內容"""
    for pattern in patterns:
        text = re.sub(pattern, "", text)
    # 移除多餘空行
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def count_page_text_tokens(text: str) -> int:
    """估算頁面文字量。"""
    return len(re.findall(r"\S+", text))


# ---------------------------------------------------------------------------
# Functions from generate_nav.py
# ---------------------------------------------------------------------------


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
