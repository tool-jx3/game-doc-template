"""
opendataloader-pdf 引擎封裝

提供可用性偵測、PDF 轉 Markdown 呼叫、頁碼標記後處理。
"""

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

_availability_cache: dict[str, object] | None = None


def check_availability() -> dict[str, object]:
    """檢查 opendataloader-pdf 套件和 Java 執行環境是否可用。"""
    global _availability_cache
    if _availability_cache is not None:
        return _availability_cache

    result: dict[str, object] = {
        "available": False,
        "package_installed": False,
        "java_available": False,
        "java_version": None,
        "reason": None,
    }

    try:
        import opendataloader_pdf  # noqa: F401

        result["package_installed"] = True
    except ImportError:
        result["reason"] = "opendataloader-pdf 套件未安裝"
        _availability_cache = result
        return result

    java_bin = shutil.which("java")
    if java_bin is None:
        result["reason"] = "Java 未安裝"
        _availability_cache = result
        return result

    try:
        proc = subprocess.run(
            ["java", "-version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
        )
        version_output = proc.stderr or proc.stdout
        match = re.search(r'"(\d+)[\._]', version_output)
        if match:
            major = int(match.group(1))
            result["java_version"] = major
            if major >= 11:
                result["java_available"] = True
            else:
                result["reason"] = f"Java 版本 {major} 低於最低要求 11"
                _availability_cache = result
                return result
        else:
            result["reason"] = f"無法解析 Java 版本：{version_output[:100]}"
            _availability_cache = result
            return result
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        result["reason"] = f"Java 版本檢查失敗：{exc}"
        _availability_cache = result
        return result

    result["available"] = True
    result["reason"] = None
    _availability_cache = result
    return result


def is_available() -> bool:
    """快速檢查 opendataloader 是否可用。"""
    return bool(check_availability()["available"])


def convert_pdf_to_markdown(pdf_path: Path, output_dir: Path) -> str | None:
    """使用 opendataloader-pdf fast 模式將 PDF 轉為 Markdown。

    回傳完整 Markdown 文字內容，失敗時回傳 None。
    """
    import opendataloader_pdf

    with tempfile.TemporaryDirectory() as tmp_dir:
        opendataloader_pdf.convert(
            input_path=[str(pdf_path)],
            output_dir=tmp_dir,
            format="markdown",
            quiet=True,
        )

        md_files = list(Path(tmp_dir).glob("**/*.md"))
        if not md_files:
            print("⚠️  opendataloader 未產出 Markdown 檔案")
            return None

        return md_files[0].read_text(encoding="utf-8")


def convert_pdf_pages(
    pdf_path: Path,
    progress_every: int = 25,
) -> list[tuple[int, str]]:
    """逐頁提取 PDF 並回傳 (page_num, text) 列表。

    使用 opendataloader 的 pages 參數逐頁提取，
    以便產生與其他引擎一致的 <!-- PAGE N --> 標記。
    """
    import pymupdf

    doc = pymupdf.open(str(pdf_path))
    total_pages = len(doc)
    doc.close()

    import opendataloader_pdf

    pages: list[tuple[int, str]] = []

    with tempfile.TemporaryDirectory() as tmp_dir:
        opendataloader_pdf.convert(
            input_path=[str(pdf_path)],
            output_dir=tmp_dir,
            format="markdown",
            quiet=True,
        )

        md_files = list(Path(tmp_dir).glob("**/*.md"))
        if not md_files:
            print("⚠️  opendataloader 未產出 Markdown 檔案")
            return []

        content = md_files[0].read_text(encoding="utf-8")

    # opendataloader 輸出可能包含頁面分隔標記（如 --- 或換頁符）
    # 使用 pymupdf 取得頁數，然後嘗試按分隔符切分
    # 如果無法可靠切分，就將整份內容作為單頁處理，再用 pymupdf 頁碼對應
    page_separator_pattern = re.compile(r'\n---\n|\f')
    raw_pages = page_separator_pattern.split(content)

    # 過濾空頁
    raw_pages = [p for p in raw_pages if p.strip()]

    if len(raw_pages) == total_pages:
        for i, text in enumerate(raw_pages):
            pages.append((i + 1, text.strip()))
    elif len(raw_pages) > 1 and abs(len(raw_pages) - total_pages) <= 2:
        # 接近頁數，允許小誤差
        for i, text in enumerate(raw_pages):
            pages.append((i + 1, text.strip()))
    else:
        # 無法可靠切分 → 使用逐頁模式
        pages = _convert_pages_individually(pdf_path, total_pages, progress_every)

    return pages


def _convert_pages_individually(
    pdf_path: Path,
    total_pages: int,
    progress_every: int,
) -> list[tuple[int, str]]:
    """逐頁呼叫 opendataloader 提取（fallback 模式）。"""
    import pymupdf
    import opendataloader_pdf

    pages: list[tuple[int, str]] = []
    doc = pymupdf.open(str(pdf_path))

    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            for page_num in range(1, total_pages + 1):
                # 提取單頁 PDF
                single = pymupdf.open()
                single.insert_pdf(doc, from_page=page_num - 1, to_page=page_num - 1)
                tmp_pdf = Path(tmp_dir) / f"page_{page_num}.pdf"
                single.save(str(tmp_pdf))
                single.close()

                page_out_dir = Path(tmp_dir) / f"page_{page_num}_out"
                page_out_dir.mkdir()

                opendataloader_pdf.convert(
                    input_path=[str(tmp_pdf)],
                    output_dir=str(page_out_dir),
                    format="markdown",
                    quiet=True,
                )

                md_files = list(page_out_dir.glob("**/*.md"))
                text = md_files[0].read_text(encoding="utf-8").strip() if md_files else ""
                pages.append((page_num, text))

                if progress_every > 0 and page_num % progress_every == 0:
                    print(f"↻ 分頁提取進度（opendataloader）: {page_num}/{total_pages}")
    finally:
        doc.close()

    return pages


def write_pages_file(
    pages: list[tuple[int, str]],
    output_file: Path,
) -> Path:
    """將頁面列表寫入含 <!-- PAGE N --> 標記的檔案。"""
    with output_file.open("w", encoding="utf-8") as handle:
        for page_num, text in pages:
            handle.write(f"\n\n<!-- PAGE {page_num} -->\n\n{text}")

    return output_file
