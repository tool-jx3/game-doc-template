"""EPUB parsing and extraction utilities.

Handles EPUB spine parsing, virtual page splitting, image extraction,
and Markdown conversion for EPUB sources.
"""

import json
import posixpath
import re
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path, PurePosixPath
from urllib.parse import unquote

from _image_analysis import analyze_image_bytes
from _markdown_utils import (
    extract_markdown_image_targets,
    split_markdown_sections,
    strip_markdown_images,
)

try:
    from markitdown import MarkItDown
except ImportError:
    MarkItDown = None

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EPUB_DOCUMENT_MEDIA_TYPES = {
    "application/xhtml+xml",
    "text/html",
}
SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def normalize_epub_internal_path(base_dir: PurePosixPath, href: str) -> str:
    """將 EPUB 內部相對路徑展開成 zip 內的正規化路徑。"""
    cleaned = unquote(href.split("#", 1)[0].split("?", 1)[0].strip())
    if not cleaned:
        return ""
    base = base_dir.as_posix()
    if base in {"", "."}:
        return posixpath.normpath(cleaned)
    return posixpath.normpath(posixpath.join(base, cleaned))


def sanitize_filename_component(name: str) -> str:
    """將來源檔名轉成穩定的 ASCII 檔名片段。"""
    sanitized = SAFE_FILENAME_RE.sub("_", name).strip("._")
    return sanitized or "image"


def build_epub_image_filename(page_num: int, image_index: int, image_path: str) -> str:
    """建立 EPUB 圖片輸出檔名。"""
    source = PurePosixPath(image_path)
    stem = sanitize_filename_component(source.stem)
    ext = source.suffix.lower() or ".bin"
    return f"page{page_num:03d}_img{image_index:02d}_{stem}{ext}"


def should_print_progress(page_num: int, total_pages: int, progress_every: int) -> bool:
    """控制分頁提取進度輸出頻率。"""
    return page_num == 1 or page_num == total_pages or page_num % progress_every == 0


# ---------------------------------------------------------------------------
# EPUB parsing
# ---------------------------------------------------------------------------


def parse_epub_package(epub_path: Path) -> dict[str, object]:
    """解析 EPUB 的 OPF、manifest 與 spine。"""
    with zipfile.ZipFile(epub_path) as archive:
        container = ET.fromstring(archive.read("META-INF/container.xml"))
        container_ns = {"c": "urn:oasis:names:tc:opendocument:xmlns:container"}
        rootfile = container.find(".//c:rootfile", container_ns)
        if rootfile is None or "full-path" not in rootfile.attrib:
            raise SystemExit("❌ EPUB 缺少有效的 META-INF/container.xml rootfile")

        opf_path = PurePosixPath(rootfile.attrib["full-path"])
        opf_root = opf_path.parent
        opf = ET.fromstring(archive.read(rootfile.attrib["full-path"]))
        opf_ns = {"opf": "http://www.idpf.org/2007/opf"}

        manifest: dict[str, dict[str, str]] = {}
        for item in opf.findall(".//opf:manifest/opf:item", opf_ns):
            item_id = item.attrib.get("id")
            href = item.attrib.get("href")
            if not item_id or not href:
                continue
            manifest[item_id] = {
                "id": item_id,
                "href": href,
                "media_type": item.attrib.get("media-type", ""),
                "path": normalize_epub_internal_path(opf_root, href),
                "properties": item.attrib.get("properties", ""),
            }

        spine: list[dict[str, object]] = []
        for index, itemref in enumerate(opf.findall(".//opf:spine/opf:itemref", opf_ns), start=1):
            item_id = itemref.attrib.get("idref")
            if not item_id or item_id not in manifest:
                continue
            entry = dict(manifest[item_id])
            entry["index"] = index
            spine.append(entry)

        return {
            "opf_path": opf_path.as_posix(),
            "opf_root": opf_root.as_posix(),
            "manifest": manifest,
            "spine": spine,
        }


def iter_epub_spine_documents(epub_path: Path) -> list[dict[str, object]]:
    """取得 EPUB spine 中可轉成 Markdown 的文件。"""
    package = parse_epub_package(epub_path)
    return [
        item
        for item in package["spine"]  # type: ignore[index]
        if str(item.get("media_type", "")) in EPUB_DOCUMENT_MEDIA_TYPES
    ]


# ---------------------------------------------------------------------------
# Virtual page building
# ---------------------------------------------------------------------------


def build_epub_virtual_pages(extracted_root: Path, spine_documents: list[dict[str, object]]) -> list[dict[str, object]]:
    """將 EPUB spine 文件轉成虛擬頁碼區塊。"""
    if MarkItDown is None:
        raise RuntimeError("markitdown is required for EPUB extraction")

    md = MarkItDown()
    pages: list[dict[str, object]] = []

    for item in spine_documents:
        source_path = Path(extracted_root) / str(item["path"])
        result = md.convert(str(source_path))
        sections = split_markdown_sections(result.text_content)
        base_dir = PurePosixPath(str(item["path"])).parent

        for section_index, section in enumerate(sections, start=1):
            image_targets = [
                normalize_epub_internal_path(base_dir, target)
                for target in extract_markdown_image_targets(section)
            ]
            page_markdown = strip_markdown_images(section)
            if not page_markdown and not image_targets:
                continue
            pages.append(
                {
                    "spine_index": int(item["index"]),
                    "section_index": section_index,
                    "source_path": str(item["path"]),
                    "markdown": page_markdown,
                    "image_targets": [target for target in image_targets if target],
                }
            )

    return pages


# ---------------------------------------------------------------------------
# EPUB extraction entry points
# ---------------------------------------------------------------------------


def extract_epub_with_pages(
    epub_path: Path,
    output_dir: Path,
    progress_every: int = 5,
) -> Path | None:
    """依 EPUB spine 文件輸出含 PAGE 標記的 Markdown。"""
    if MarkItDown is None:
        print("⚠️  markitdown 未安裝，無法處理 EPUB")
        return None

    spine_documents = iter_epub_spine_documents(epub_path)
    output_file = output_dir / f"{epub_path.stem}_pages.md"
    progress_every = max(1, progress_every)

    with tempfile.TemporaryDirectory() as tmp_dir:
        with zipfile.ZipFile(epub_path) as archive:
            archive.extractall(tmp_dir)

        pages = build_epub_virtual_pages(Path(tmp_dir), spine_documents)
        total_docs = len(pages)
        with output_file.open("w", encoding="utf-8") as handle:
            for page_num, item in enumerate(pages, start=1):
                handle.write(f"\n\n<!-- PAGE {page_num} -->\n\n{str(item['markdown']).strip()}")
                if should_print_progress(page_num, total_docs, progress_every):
                    print(f"↻ 分頁提取進度（epub）: {page_num}/{total_docs}")

    print(f"✓ 已提取（含頁碼，epub-spine）: {output_file}")
    return output_file


def extract_epub_images(epub_path: Path, output_dir: Path) -> list[dict]:
    """提取 EPUB 中被內容章節引用的圖片，並建立 manifest。"""
    if MarkItDown is None:
        print("⚠️  markitdown 未安裝，無法處理 EPUB 圖片提取")
        return []

    images_dir = output_dir / "images" / epub_path.stem
    images_dir.mkdir(parents=True, exist_ok=True)
    saved_images: list[dict] = []

    spine_documents = iter_epub_spine_documents(epub_path)
    with tempfile.TemporaryDirectory() as tmp_dir:
        with zipfile.ZipFile(epub_path) as archive:
            archive.extractall(tmp_dir)
            pages = build_epub_virtual_pages(Path(tmp_dir), spine_documents)

            for page_num, page in enumerate(pages, start=1):
                for image_index, image_target in enumerate(page["image_targets"]):
                    try:
                        image_bytes = archive.read(image_target)
                    except KeyError:
                        continue

                    analysis = analyze_image_bytes(image_bytes)
                    filename = build_epub_image_filename(page_num, image_index, image_target)
                    image_path = images_dir / filename
                    image_path.write_bytes(image_bytes)

                    saved_images.append(
                        {
                            "page": page_num,
                            "image_index": image_index,
                            "placement_index": 0,
                            "xref": None,
                            "filename": filename,
                            "path": str(image_path.relative_to(output_dir).as_posix()),
                            "source_path": image_target,
                            "x": None,
                            "y": None,
                            "width": None,
                            "height": None,
                            "page_width": None,
                            "page_height": None,
                            "coverage_ratio": None,
                            "file_size": len(image_bytes),
                            "visual_hash": analysis.get("visual_hash"),
                            "dominant_color_ratio": analysis.get("dominant_color_ratio"),
                            "sampled_pixel_count": analysis.get("sampled_pixel_count"),
                        }
                    )

    manifest_path = images_dir / "manifest.json"
    manifest = {
        "source": epub_path.name,
        "source_type": "epub",
        "images_dir": str(images_dir.relative_to(output_dir).as_posix()),
        "images": saved_images,
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"✓ 已提取 {len(saved_images)} 張圖片到 {images_dir}")
    print(f"✓ 已建立圖片 manifest: {manifest_path}")
    return saved_images
