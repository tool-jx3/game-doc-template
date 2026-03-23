"""OCR utilities backed by the tesseract CLI."""

from __future__ import annotations

import re
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path

try:
    import pymupdf
except ImportError:
    pymupdf = None


IMAGE_SOURCE_SUFFIXES = {
    ".bmp",
    ".jpg",
    ".jpeg",
    ".png",
    ".tif",
    ".tiff",
    ".webp",
}
DEFAULT_OCR_LANG = "chi_tra+eng"
DEFAULT_OCR_PSM = 6
DEFAULT_OCR_DPI = 300
NATURAL_SORT_TOKEN_RE = re.compile(r"(\d+)")


def natural_sort_key(path: Path) -> tuple[tuple[int, object], ...]:
    """Return a natural sort key for filenames like page2 < page10."""
    key: list[tuple[int, object]] = []
    for token in NATURAL_SORT_TOKEN_RE.split(path.as_posix().lower()):
        if not token:
            continue
        if token.isdigit():
            key.append((0, int(token)))
        else:
            key.append((1, token))
    return tuple(key)


def find_ocr_image_files(source_path: Path) -> list[Path]:
    """Collect OCR-capable image files from a single file or a directory tree."""
    if source_path.is_file():
        return [source_path] if source_path.suffix.lower() in IMAGE_SOURCE_SUFFIXES else []

    files = [
        path
        for path in source_path.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_SOURCE_SUFFIXES
    ]
    return sorted(files, key=lambda path: natural_sort_key(path.relative_to(source_path)))


def parse_requested_ocr_languages(ocr_lang: str) -> list[str]:
    return [part.strip() for part in ocr_lang.split("+") if part.strip()]


def parse_tesseract_language_output(stdout: str) -> set[str]:
    languages: set[str] = set()
    for line in stdout.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("List of available languages"):
            continue
        languages.add(stripped)
    return languages


@lru_cache(maxsize=1)
def get_tesseract_available_languages() -> set[str]:
    binary = shutil.which("tesseract")
    if binary is None:
        raise RuntimeError("找不到 `tesseract`，請先安裝後再使用 OCR。")

    result = subprocess.run(
        [binary, "--list-langs"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or "無法讀取 tesseract 語言清單。"
        raise RuntimeError(detail)
    return parse_tesseract_language_output(result.stdout)


def ensure_tesseract_ready(ocr_lang: str) -> None:
    available = get_tesseract_available_languages()
    requested = parse_requested_ocr_languages(ocr_lang)
    missing = [lang for lang in requested if lang not in available]
    if missing:
        available_list = ", ".join(sorted(available)) or "<none>"
        missing_list = ", ".join(missing)
        raise RuntimeError(
            f"tesseract 缺少 OCR 語言資料：{missing_list}。"
            f"目前可用語言：{available_list}"
        )


def run_tesseract_ocr(image_path: Path, ocr_lang: str, ocr_psm: int) -> str:
    """Run tesseract on an image file and return normalized stdout text."""
    ensure_tesseract_ready(ocr_lang)
    binary = shutil.which("tesseract") or "tesseract"
    result = subprocess.run(
        [
            binary,
            str(image_path),
            "stdout",
            "-l",
            ocr_lang,
            "--psm",
            str(ocr_psm),
            "-c",
            "preserve_interword_spaces=1",
            "quiet",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or f"OCR 失敗：{image_path.name}"
        raise RuntimeError(detail)
    return result.stdout.strip()


def render_pdf_page_for_ocr(page, output_path: Path, dpi: int = DEFAULT_OCR_DPI) -> None:
    """Render a PDF page to an image for OCR."""
    if pymupdf is None:
        raise RuntimeError("缺少 `pymupdf`，無法將 PDF 頁面轉成 OCR 圖片。")

    try:
        pixmap = page.get_pixmap(dpi=dpi, alpha=False)
    except TypeError:
        matrix = pymupdf.Matrix(dpi / 72, dpi / 72)
        try:
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
        except TypeError:
            pixmap = page.get_pixmap(matrix=matrix)
    pixmap.save(str(output_path))
