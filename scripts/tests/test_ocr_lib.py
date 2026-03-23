from pathlib import Path
import subprocess

import pytest

import _ocr_lib as ol


class TestFindOcrImageFiles:
    def test_collects_and_sorts_images_naturally(self, tmp_path):
        (tmp_path / "page10.jpg").write_text("x", encoding="utf-8")
        (tmp_path / "page2.jpg").write_text("x", encoding="utf-8")
        nested = tmp_path / "nested"
        nested.mkdir()
        (nested / "page3.png").write_text("x", encoding="utf-8")
        (tmp_path / "notes.txt").write_text("x", encoding="utf-8")

        result = [
            path.relative_to(tmp_path).as_posix()
            for path in ol.find_ocr_image_files(tmp_path)
        ]

        assert result == ["nested/page3.png", "page2.jpg", "page10.jpg"]

    def test_single_image_file_returns_itself(self, tmp_path):
        image = tmp_path / "page001.jpeg"
        image.write_text("x", encoding="utf-8")
        assert ol.find_ocr_image_files(image) == [image]


class TestEnsureTesseractReady:
    def teardown_method(self):
        ol.get_tesseract_available_languages.cache_clear()

    def test_errors_when_tesseract_missing(self, monkeypatch):
        monkeypatch.setattr(ol.shutil, "which", lambda _name: None)

        with pytest.raises(RuntimeError, match="tesseract"):
            ol.ensure_tesseract_ready("eng")

    def test_errors_when_language_pack_missing(self, monkeypatch):
        monkeypatch.setattr(ol.shutil, "which", lambda _name: "/usr/bin/tesseract")
        monkeypatch.setattr(
            ol.subprocess,
            "run",
            lambda *args, **kwargs: subprocess.CompletedProcess(
                args=args[0],
                returncode=0,
                stdout='List of available languages in "/tmp" (2):\neng\nosd\n',
                stderr="",
            ),
        )

        with pytest.raises(RuntimeError, match="chi_tra"):
            ol.ensure_tesseract_ready("chi_tra+eng")


class TestRunTesseractOcr:
    def test_returns_stripped_stdout(self, monkeypatch, tmp_path):
        image = tmp_path / "page001.jpg"
        image.write_text("x", encoding="utf-8")
        monkeypatch.setattr(ol, "ensure_tesseract_ready", lambda _lang: None)
        monkeypatch.setattr(ol.shutil, "which", lambda _name: "/usr/bin/tesseract")
        monkeypatch.setattr(
            ol.subprocess,
            "run",
            lambda *args, **kwargs: subprocess.CompletedProcess(
                args=args[0],
                returncode=0,
                stdout="  OCR text  \n",
                stderr="",
            ),
        )

        assert ol.run_tesseract_ocr(image, ocr_lang="eng", ocr_psm=6) == "OCR text"
