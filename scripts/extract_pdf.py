#!/usr/bin/env python3
"""
PDF 提取工具
將 PDF 轉換為 Markdown，支援文字與圖片提取

使用方式：
    python scripts/extract_pdf.py <pdf_file>
    python scripts/extract_pdf.py <pdf_file> --include-images
    python scripts/extract_pdf.py <pdf_file> --no-include-images
    python scripts/extract_pdf.py <pdf_file> --skip-full-markitdown
    python scripts/extract_pdf.py <pdf_file> --layout-profile double-column
    python scripts/extract_pdf.py <pdf_file> --page-text-engine markitdown

輸出：
    data/markdown/<檔名>.md                 - markitdown 提取版本
    data/markdown/<檔名>_pages.md           - 含頁碼標記版本（用於章節拆分）
    data/markdown/images/<檔名>/            - 提取的圖片
    data/markdown/images/<檔名>/manifest.json - 圖片位置與尺寸資訊
"""

import argparse
import json
import sys
import tempfile
from pathlib import Path

from _epub_lib import (
    extract_epub_images,
    extract_epub_with_pages,
    should_print_progress,
)
from _image_analysis import analyze_image_bytes, compute_visual_hash
from _layout_lib import (
    MIN_QUALITY_PROBE_CHARS,
    analyze_pymupdf_text_noise,
    classify_page_layout,
    detect_layout_profile,
    extract_page_text_pymupdf,
    probe_pymupdf_text_quality,
    sample_page_indices,
)
from _markdown_utils import (
    LINKED_MARKDOWN_IMAGE_RE,
    MARKDOWN_HEADING_RE,
    MARKDOWN_IMAGE_RE,
    extract_markdown_image_targets,
    split_markdown_sections,
    strip_markdown_images,
)

try:
    from markitdown import MarkItDown
except ImportError:
    MarkItDown = None

try:
    import pymupdf
except ImportError:
    pymupdf = None


VALID_PAGE_TEXT_ENGINES = {"auto", "pymupdf", "markitdown"}
VALID_LAYOUT_PROFILES = {"auto", "single-column", "double-column"}
SUPPORTED_SOURCE_TYPES = {
    ".pdf": "pdf",
    ".epub": "epub",
}
PAGE_TEXT_ENGINE_ALIASES = {
    "fitz": "pymupdf",
    "markdown": "markitdown",
}
LAYOUT_PROFILE_ALIASES = {
    "single": "single-column",
    "single_column": "single-column",
    "double": "double-column",
    "double_column": "double-column",
    "two-column": "double-column",
    "two_column": "double-column",
}


def normalize_page_text_engine(value: object) -> str | None:
    """正規化頁面文字引擎設定。"""
    if value is None:
        return None
    normalized = str(value).strip().lower()
    normalized = PAGE_TEXT_ENGINE_ALIASES.get(normalized, normalized)
    if normalized in VALID_PAGE_TEXT_ENGINES:
        return normalized
    return None


def normalize_layout_profile(value: object) -> str | None:
    """正規化版面設定。"""
    if value is None:
        return None
    normalized = str(value).strip().lower()
    normalized = LAYOUT_PROFILE_ALIASES.get(normalized, normalized)
    if normalized in VALID_LAYOUT_PROFILES:
        return normalized
    return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="將 PDF / EPUB 提取成可切分的 Markdown")
    parser.add_argument("pdf_file", help="來源 PDF / EPUB 檔案")
    parser.add_argument(
        "--skip-full-markitdown",
        action="store_true",
        help="略過整本 markitdown 提取，只保留 _pages.md 與圖片輸出",
    )
    parser.add_argument(
        "--page-text-engine",
        choices=("auto", "pymupdf", "markitdown"),
        default="auto",
        help="生成 _pages.md 時使用的頁面文字引擎（預設: auto；EPUB 目前固定使用 markitdown）",
    )
    parser.add_argument(
        "--layout-profile",
        choices=("auto", "single-column", "double-column"),
        default="auto",
        help="文件版面設定（預設: auto；EPUB 目前不使用此設定）",
    )

    include_group = parser.add_mutually_exclusive_group()
    include_group.add_argument(
        "--include-images",
        dest="include_images",
        action="store_true",
        help="包含圖片提取與 manifest",
    )
    include_group.add_argument(
        "--no-include-images",
        dest="include_images",
        action="store_false",
        help="略過圖片提取",
    )
    parser.set_defaults(include_images=None)
    return parser.parse_args()


def prompt_include_images() -> bool:
    """互動詢問是否要提取圖片。非互動執行時預設為否。"""
    if not sys.stdin.isatty():
        return False

    while True:
        answer = input("是否要包含圖片提取與位置記錄？[y/N]: ").strip().lower()
        if answer in {"", "n", "no"}:
            return False
        if answer in {"y", "yes"}:
            return True
        print("請輸入 y 或 n。")


def detect_source_type(source_path: Path) -> str:
    """判斷來源格式，目前支援 PDF 與 EPUB。"""
    source_type = SUPPORTED_SOURCE_TYPES.get(source_path.suffix.lower())
    if source_type is None:
        supported = ", ".join(sorted(SUPPORTED_SOURCE_TYPES))
        raise SystemExit(f"❌ 不支援的檔案格式：{source_path.suffix or '<none>'}（僅支援 {supported}）")
    return source_type


def extract_with_markitdown(source_path: Path, output_dir: Path) -> Path | None:
    """使用 markitdown 提取整本來源內容。"""
    if MarkItDown is None:
        print("⚠️  markitdown 未安裝，跳過")
        return None

    md = MarkItDown()
    result = md.convert(str(source_path))

    output_file = output_dir / f"{source_path.stem}.md"
    output_file.write_text(result.text_content, encoding="utf-8")

    print(f"✓ 已提取: {output_file}")
    return output_file



def load_style_decisions(project_root: Path) -> dict:
    """讀取 style-decisions.json。"""
    path = project_root / "style-decisions.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"⚠️  style-decisions.json 解析失敗，忽略文件抽取設定：{exc}")
        return {}


def load_document_extraction_settings(project_root: Path, pdf_stem: str) -> dict[str, str]:
    """讀取全域與每文件抽取設定。"""
    style_decisions = load_style_decisions(project_root)
    document_format = style_decisions.get("document_format", {})
    if not isinstance(document_format, dict):
        return {}

    settings: dict[str, str] = {}
    for key, normalizer in (
        ("page_text_engine", normalize_page_text_engine),
        ("layout_profile", normalize_layout_profile),
    ):
        normalized = normalizer(document_format.get(key))
        if normalized is not None:
            settings[key] = normalized

    documents = document_format.get("documents", {})
    if isinstance(documents, dict):
        doc_settings = documents.get(pdf_stem, {})
        if isinstance(doc_settings, dict):
            for key, normalizer in (
                ("page_text_engine", normalize_page_text_engine),
                ("layout_profile", normalize_layout_profile),
            ):
                normalized = normalizer(doc_settings.get(key))
                if normalized is not None:
                    settings[key] = normalized

    return settings


def resolve_page_text_strategy(
    pdf_path: Path,
    project_root: Path,
    requested_engine: str,
    requested_layout: str,
) -> dict[str, object]:
    """綜合 CLI、style-decisions 與自動偵測，決定分頁提取策略。"""
    source_type = detect_source_type(pdf_path)
    if source_type == "epub":
        return {
            "page_text_engine": "markitdown",
            "page_text_engine_source": "epub-default",
            "layout_profile": "single-column",
            "layout_profile_source": "epub-default",
            "document_settings": {},
            "detection": None,
            "quality_probe": None,
            "source_type": source_type,
        }

    pdf_stem = pdf_path.stem
    settings = load_document_extraction_settings(project_root, pdf_stem)

    page_text_engine = normalize_page_text_engine(requested_engine) or "auto"
    layout_profile = normalize_layout_profile(requested_layout) or "auto"
    engine_source = "cli" if page_text_engine != "auto" else None
    layout_source = "cli" if layout_profile != "auto" else None

    if page_text_engine == "auto":
        style_engine = settings.get("page_text_engine")
        if style_engine and style_engine != "auto":
            page_text_engine = style_engine
            engine_source = "style-decisions"

    if layout_profile == "auto":
        style_layout = settings.get("layout_profile")
        if style_layout and style_layout != "auto":
            layout_profile = style_layout
            layout_source = "style-decisions"

    detection: dict[str, object] | None = None
    quality_probe: dict[str, object] | None = None
    if layout_profile == "auto":
        detection = detect_layout_profile(pdf_path)
        layout_profile = str(detection.get("layout_profile", "single-column"))
        layout_source = str(detection.get("source", "auto-detect"))

    if (
        page_text_engine == "auto"
        and layout_profile == "single-column"
        and MarkItDown is not None
    ):
        quality_probe = probe_pymupdf_text_quality(pdf_path)
        if quality_probe.get("prefer_markitdown"):
            page_text_engine = "markitdown"
            engine_source = str(quality_probe.get("source", "quality-probe"))

    if page_text_engine == "auto":
        page_text_engine = "markitdown" if layout_profile == "double-column" else "pymupdf"
        engine_source = "layout-profile"

    if page_text_engine == "markitdown" and MarkItDown is None:
        print("⚠️  需要 markitdown 才能使用雙欄保守路徑，已回退到 pymupdf")
        page_text_engine = "pymupdf"
        engine_source = "fallback"

    return {
        "page_text_engine": page_text_engine,
        "page_text_engine_source": engine_source or "default",
        "layout_profile": layout_profile,
        "layout_profile_source": layout_source or "default",
        "document_settings": settings,
        "detection": detection,
        "quality_probe": quality_probe,
        "source_type": source_type,
    }


def extract_with_pages(
    pdf_path: Path,
    output_dir: Path,
    page_text_engine: str = "pymupdf",
    progress_every: int = 25,
) -> Path | None:
    """提取含頁碼標記的內容，用於章節拆分。"""
    source_type = detect_source_type(pdf_path)
    if source_type == "epub":
        return extract_epub_with_pages(pdf_path, output_dir, progress_every=max(1, progress_every // 5))

    if pymupdf is None:
        print("⚠️  pymupdf 未安裝（需要用於分頁），跳過")
        return None
    if page_text_engine == "markitdown" and MarkItDown is None:
        print("⚠️  markitdown 未安裝，無法使用 markitdown 分頁模式")
        return None

    doc = pymupdf.open(str(pdf_path))
    total_pages = len(doc)
    progress_every = max(1, progress_every)
    output_file = output_dir / f"{pdf_path.stem}_pages.md"
    try:
        with output_file.open("w", encoding="utf-8") as handle:
            if page_text_engine == "pymupdf":
                for page_num, page in enumerate(doc, 1):
                    page_text = extract_page_text_pymupdf(page)
                    handle.write(f"\n\n<!-- PAGE {page_num} -->\n\n{page_text}")
                    if should_print_progress(page_num, total_pages, progress_every):
                        print(f"↻ 分頁提取進度（pymupdf）: {page_num}/{total_pages}")
            else:
                md = MarkItDown()
                with tempfile.TemporaryDirectory() as tmp_dir:
                    for page_num in range(total_pages):
                        single = pymupdf.open()
                        single.insert_pdf(doc, from_page=page_num, to_page=page_num)
                        tmp_pdf = Path(tmp_dir) / f"page_{page_num + 1}.pdf"
                        single.save(str(tmp_pdf))
                        single.close()

                        result = md.convert(str(tmp_pdf))
                        handle.write(
                            f"\n\n<!-- PAGE {page_num + 1} -->\n\n{result.text_content.strip()}"
                        )
                        if should_print_progress(page_num + 1, total_pages, progress_every):
                            print(f"↻ 分頁提取進度（markitdown）: {page_num + 1}/{total_pages}")
    finally:
        doc.close()

    print(f"✓ 已提取（含頁碼，{page_text_engine}）: {output_file}")
    return output_file


def build_image_filename(page_num: int, image_index: int, placement_index: int, rect, ext: str) -> str:
    """建立包含位置與尺寸資訊的圖片檔名。"""
    if rect is None:
        return f"page{page_num:03d}_img{image_index:02d}_occ{placement_index:02d}.{ext}"

    x = round(rect.x0)
    y = round(rect.y0)
    width = round(rect.width)
    height = round(rect.height)
    return (
        f"page{page_num:03d}_img{image_index:02d}_occ{placement_index:02d}"
        f"_x{x}_y{y}_w{width}_h{height}.{ext}"
    )


def extract_images(pdf_path: Path, output_dir: Path) -> list[dict]:
    """提取 PDF 中的圖片，並記錄位置與尺寸資訊。"""
    source_type = detect_source_type(pdf_path)
    if source_type == "epub":
        return extract_epub_images(pdf_path, output_dir)

    if pymupdf is None:
        print("⚠️  pymupdf 未安裝，無法提取圖片")
        return []

    doc = pymupdf.open(str(pdf_path))
    images_dir = output_dir / "images" / pdf_path.stem
    images_dir.mkdir(parents=True, exist_ok=True)

    saved_images: list[dict] = []
    for page_num, page in enumerate(doc, 1):
        page_rect = getattr(page, "rect", None)
        page_width = round(float(page_rect.width), 2) if page_rect is not None else None
        page_height = round(float(page_rect.height), 2) if page_rect is not None else None

        try:
            page_images = page.get_images(full=True)
        except TypeError:
            page_images = page.get_images()

        for img_index, img in enumerate(page_images):
            xref = img[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            image_ext = base_image["ext"]
            analysis = analyze_image_bytes(image_bytes)
            try:
                rects = page.get_image_rects(xref, transform=False)
            except TypeError:
                rects = page.get_image_rects(xref)
            except AttributeError:
                rects = []

            if not rects:
                rects = [None]

            for placement_index, rect in enumerate(rects):
                image_name = build_image_filename(
                    page_num,
                    img_index,
                    placement_index,
                    rect,
                    image_ext,
                )
                image_path = images_dir / image_name
                image_path.write_bytes(image_bytes)

                if rect is None:
                    x = None
                    y = None
                    width = base_image.get("width")
                    height = base_image.get("height")
                else:
                    x = round(rect.x0, 2)
                    y = round(rect.y0, 2)
                    width = round(rect.width, 2)
                    height = round(rect.height, 2)

                coverage_ratio = None
                if (
                    width
                    and height
                    and page_width
                    and page_height
                    and page_width > 0
                    and page_height > 0
                ):
                    coverage_ratio = round((width * height) / (page_width * page_height), 4)

                saved_images.append(
                    {
                        "page": page_num,
                        "image_index": img_index,
                        "placement_index": placement_index,
                        "xref": xref,
                        "filename": image_name,
                        "path": str(image_path.relative_to(output_dir).as_posix()),
                        "x": x,
                        "y": y,
                        "width": width,
                        "height": height,
                        "page_width": page_width,
                        "page_height": page_height,
                        "coverage_ratio": coverage_ratio,
                        "file_size": len(image_bytes),
                        "visual_hash": analysis.get("visual_hash"),
                        "dominant_color_ratio": analysis.get("dominant_color_ratio"),
                        "sampled_pixel_count": analysis.get("sampled_pixel_count"),
                    }
                )

    doc.close()

    manifest_path = images_dir / "manifest.json"
    manifest = {
        "pdf": pdf_path.name,
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


def main():
    args = parse_args()
    pdf_path = Path(args.pdf_file)

    if not pdf_path.exists():
        print(f"❌ 找不到檔案: {pdf_path}")
        sys.exit(1)

    source_type = detect_source_type(pdf_path)

    # 設定輸出目錄
    project_root = Path(__file__).parent.parent
    output_dir = project_root / "data" / "markdown"
    output_dir.mkdir(parents=True, exist_ok=True)
    strategy = resolve_page_text_strategy(
        pdf_path,
        project_root,
        requested_engine=args.page_text_engine,
        requested_layout=args.layout_profile,
    )

    print(f"\n📄 處理: {pdf_path.name} ({source_type.upper()})")
    print(
        f"🧭 分頁引擎: {strategy['page_text_engine']} "
        f"（來源: {strategy['page_text_engine_source']}）"
    )
    print(
        f"🧭 版面設定: {strategy['layout_profile']} "
        f"（來源: {strategy['layout_profile_source']}）"
    )
    if strategy["detection"] is not None:
        sampled_pages = [
            f"p.{result['page']}={result['layout_profile']}"
            for result in strategy["detection"].get("sampled_pages", [])
            if result.get("layout_profile") != "unknown"
        ]
        if sampled_pages:
            print(f"   自動偵測抽樣: {', '.join(sampled_pages[:8])}")
    quality_probe = strategy.get("quality_probe")
    if quality_probe and quality_probe.get("prefer_markitdown"):
        noisy_pages = [
            f"p.{result['page']}={result['whitespace_ratio']}"
            for result in quality_probe.get("sampled_pages", [])
            if result.get("is_noisy")
        ]
        if noisy_pages:
            print(f"   文字品質探測：PyMuPDF 版面噪訊偏高，改用 markitdown（{', '.join(noisy_pages[:8])}）")
    print("-" * 50)

    if args.skip_full_markitdown:
        print("↷ 已略過整本 markitdown 提取")
    else:
        extract_with_markitdown(pdf_path, output_dir)

    extract_with_pages(
        pdf_path,
        output_dir,
        page_text_engine=strategy["page_text_engine"],
    )

    include_images = args.include_images
    if include_images is None:
        include_images = prompt_include_images()

    if include_images:
        extract_images(pdf_path, output_dir)
    else:
        print("↷ 已略過圖片提取")

    print("-" * 50)
    print("✅ 完成！")
    print(f"\n下一步：使用 split_chapters.py 拆分章節")


if __name__ == "__main__":
    main()
