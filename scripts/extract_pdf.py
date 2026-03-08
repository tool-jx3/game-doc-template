#!/usr/bin/env python3
"""
PDF 提取工具
將 PDF 轉換為 Markdown，支援文字與圖片提取

使用方式：
    python scripts/extract_pdf.py <pdf_file>
    python scripts/extract_pdf.py <pdf_file> --include-images
    python scripts/extract_pdf.py <pdf_file> --no-include-images

輸出：
    data/markdown/<檔名>.md                 - markitdown 提取版本
    data/markdown/<檔名>_pages.md           - 含頁碼標記版本（用於章節拆分）
    data/markdown/images/<檔名>/            - 提取的圖片
    data/markdown/images/<檔名>/manifest.json - 圖片位置與尺寸資訊
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

try:
    from markitdown import MarkItDown
except ImportError:
    MarkItDown = None

try:
    import pymupdf
except ImportError:
    pymupdf = None


def compute_visual_hash(samples: list[int]) -> str | None:
    """根據灰階採樣建立簡單視覺指紋。"""
    if not samples:
        return None
    average = sum(samples) / len(samples)
    bits = "".join("1" if sample >= average else "0" for sample in samples)
    return f"{int(bits, 2):016x}"


def analyze_image_bytes(image_bytes: bytes) -> dict[str, object]:
    """分析圖片內容，提供背景判定可用的視覺特徵。"""
    if pymupdf is None or not hasattr(pymupdf, "Pixmap"):
        return {}

    try:
        pixmap = pymupdf.Pixmap(image_bytes)
    except Exception:
        return {}

    width = int(getattr(pixmap, "width", 0) or 0)
    height = int(getattr(pixmap, "height", 0) or 0)
    stride = int(getattr(pixmap, "stride", 0) or 0)
    channel_count = int(getattr(pixmap, "n", 0) or 0)
    samples = getattr(pixmap, "samples", b"")

    if width <= 0 or height <= 0 or stride <= 0 or channel_count <= 0 or not samples:
        return {}

    color_counts: Counter[tuple[int, int, int]] = Counter()
    grayscale_samples: list[int] = []
    max_sample_axis = 48
    grid_axis = 8
    step_x = max(1, width // max_sample_axis)
    step_y = max(1, height // max_sample_axis)

    def sample_rgb(x: int, y: int) -> tuple[int, int, int]:
        offset = y * stride + x * channel_count
        pixel = samples[offset: offset + channel_count]
        if not pixel:
            return (0, 0, 0)
        if channel_count == 1:
            value = pixel[0]
            return (value, value, value)
        if channel_count >= 3:
            return (pixel[0], pixel[1], pixel[2])
        value = pixel[0]
        return (value, value, value)

    for y in range(0, height, step_y):
        for x in range(0, width, step_x):
            r, g, b = sample_rgb(x, y)
            color_counts[(r // 16, g // 16, b // 16)] += 1

    for grid_y in range(grid_axis):
        sample_y = min(height - 1, int((grid_y + 0.5) * height / grid_axis))
        for grid_x in range(grid_axis):
            sample_x = min(width - 1, int((grid_x + 0.5) * width / grid_axis))
            r, g, b = sample_rgb(sample_x, sample_y)
            grayscale = int(0.299 * r + 0.587 * g + 0.114 * b)
            grayscale_samples.append(grayscale)

    total_samples = sum(color_counts.values())
    dominant_color_ratio = None
    if total_samples:
        dominant_color_ratio = round(max(color_counts.values()) / total_samples, 4)

    return {
        "visual_hash": compute_visual_hash(grayscale_samples),
        "dominant_color_ratio": dominant_color_ratio,
        "sampled_pixel_count": total_samples,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="將 PDF 提取成可切分的 Markdown")
    parser.add_argument("pdf_file", help="來源 PDF 檔案")

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


def extract_with_markitdown(pdf_path: Path, output_dir: Path) -> Path | None:
    """使用 markitdown 提取 PDF 內容（較好的格式保留）"""
    if MarkItDown is None:
        print("⚠️  markitdown 未安裝，跳過")
        return None

    md = MarkItDown()
    result = md.convert(str(pdf_path))

    output_file = output_dir / f"{pdf_path.stem}.md"
    output_file.write_text(result.text_content, encoding="utf-8")

    print(f"✓ 已提取: {output_file}")
    return output_file


def extract_with_pages(pdf_path: Path, output_dir: Path) -> Path | None:
    """使用 markitdown 逐頁提取 PDF 內容（含頁碼標記，用於章節拆分）"""
    if MarkItDown is None:
        print("⚠️  markitdown 未安裝，跳過")
        return None
    if pymupdf is None:
        print("⚠️  pymupdf 未安裝（需要用於分頁），跳過")
        return None

    import tempfile

    md = MarkItDown()
    doc = pymupdf.open(str(pdf_path))

    content_parts = []
    with tempfile.TemporaryDirectory() as tmp_dir:
        for page_num in range(len(doc)):
            single = pymupdf.open()
            single.insert_pdf(doc, from_page=page_num, to_page=page_num)
            tmp_pdf = Path(tmp_dir) / f"page_{page_num + 1}.pdf"
            single.save(str(tmp_pdf))
            single.close()

            result = md.convert(str(tmp_pdf))
            content_parts.append(
                f"\n\n<!-- PAGE {page_num + 1} -->\n\n{result.text_content.strip()}"
            )

    doc.close()

    output_file = output_dir / f"{pdf_path.stem}_pages.md"
    output_file.write_text("".join(content_parts), encoding="utf-8")

    print(f"✓ 已提取（含頁碼）: {output_file}")
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

    # 設定輸出目錄
    project_root = Path(__file__).parent.parent
    output_dir = project_root / "data" / "markdown"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n📄 處理: {pdf_path.name}")
    print("-" * 50)

    # 使用 markitdown 提取
    extract_with_markitdown(pdf_path, output_dir)

    # 使用 pymupdf 提取（含頁碼）
    extract_with_pages(pdf_path, output_dir)

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
