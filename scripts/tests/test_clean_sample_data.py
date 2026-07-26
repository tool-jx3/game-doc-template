from __future__ import annotations

import json

import clean_sample_data as csd


def _patch_paths(monkeypatch, tmp_path):
    monkeypatch.setattr(csd, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(csd, "CHAPTERS_PATH", tmp_path / "chapters.json")
    monkeypatch.setattr(csd, "STYLE_PATH", tmp_path / "style-decisions.json")
    monkeypatch.setattr(csd, "PROGRESS_GLOB_DIR", tmp_path / "data")
    monkeypatch.setattr(csd, "ASTRO_CONFIG", tmp_path / "docs" / "astro.config.mjs")
    monkeypatch.setattr(csd, "INDEX_MDX", tmp_path / "docs" / "src" / "content" / "docs" / "index.mdx")
    monkeypatch.setattr(csd, "PLANS_DIR", tmp_path / "plans")


def test_reset_chapters_writes_placeholder(monkeypatch, tmp_path):
    _patch_paths(monkeypatch, tmp_path)
    (tmp_path / "chapters.json").write_text('{"source": "old"}', encoding="utf-8")
    csd.reset_chapters(apply=True)
    data = json.loads((tmp_path / "chapters.json").read_text(encoding="utf-8"))
    assert data["source"] == "data/markdown/YOUR-RULEBOOK_pages.md"
    assert "example-section" in data["chapters"]


def test_reset_style_decisions_keeps_only_meta(monkeypatch, tmp_path):
    _patch_paths(monkeypatch, tmp_path)
    (tmp_path / "style-decisions.json").write_text(
        '{"_meta": {"description": "d", "updated": "x"}, "site": {"title": "YZE"}}',
        encoding="utf-8",
    )
    csd.reset_style_decisions(apply=True)
    data = json.loads((tmp_path / "style-decisions.json").read_text(encoding="utf-8"))
    assert list(data.keys()) == ["_meta"]


def test_remove_progress_files(monkeypatch, tmp_path):
    _patch_paths(monkeypatch, tmp_path)
    (tmp_path / "data").mkdir()
    for name in ("translation-progress.json", "translation-progress-bilingual.json"):
        (tmp_path / "data" / name).write_text("{}", encoding="utf-8")
    csd.remove_progress_files(apply=True)
    assert not list((tmp_path / "data").glob("translation-progress*.json"))


def test_reset_astro_config_title_and_sidebar(monkeypatch, tmp_path):
    _patch_paths(monkeypatch, tmp_path)
    cfg = tmp_path / "docs" / "astro.config.mjs"
    cfg.parent.mkdir(parents=True)
    cfg.write_text(
        "const SITE_CONFIG = {\n\ttitle: 'Old Sample Title',\n};\n"
        "export default defineConfig({\n\tsidebar: [\n\t\t{ label: 'X', slug: 'bilingual/x' },\n\t],\n});\n",
        encoding="utf-8",
    )
    csd.reset_astro_config(apply=True)
    text = cfg.read_text(encoding="utf-8")
    assert "title: '遊戲規則文件'" in text
    assert "bilingual/x" not in text
    assert "sidebar: []," in text


def test_reset_astro_config_idempotent_on_second_run(monkeypatch, tmp_path):
    _patch_paths(monkeypatch, tmp_path)
    cfg = tmp_path / "docs" / "astro.config.mjs"
    cfg.parent.mkdir(parents=True)
    cfg.write_text(
        "const SITE_CONFIG = {\n\ttitle: 'Old Sample Title',\n};\n"
        "export default defineConfig({\n"
        "\tintegrations: [\n"
        "\t\tstarlight({\n"
        "\t\t\tsidebar: [\n\t\t\t\t{ label: 'X', slug: 'bilingual/x' },\n\t\t\t],\n"
        "\t\t\tplugins: [starlightAutoSidebar()],\n"
        "\t\t\tcustomCss: ['./src/styles/custom.css'],\n"
        "\t\t}),\n"
        "\t],\n"
        "});\n",
        encoding="utf-8",
    )
    csd.reset_astro_config(apply=True)
    first_pass = cfg.read_text(encoding="utf-8")
    assert "sidebar: []," in first_pass
    assert "plugins: [starlightAutoSidebar()]," in first_pass
    assert "customCss: ['./src/styles/custom.css']," in first_pass

    # Re-running on an already-blank sidebar must not corrupt subsequent lines.
    csd.reset_astro_config(apply=True)
    second_pass = cfg.read_text(encoding="utf-8")
    assert second_pass == first_pass


def test_write_placeholder_index_and_remove_plans(monkeypatch, tmp_path):
    _patch_paths(monkeypatch, tmp_path)
    (tmp_path / "plans").mkdir()
    (tmp_path / "plans" / "x.md").write_text("x", encoding="utf-8")
    csd.write_placeholder_index(apply=True)
    csd.remove_plans_dir(apply=True)
    index = tmp_path / "docs" / "src" / "content" / "docs" / "index.mdx"
    assert index.exists()
    assert "title:" in index.read_text(encoding="utf-8")
    assert not (tmp_path / "plans").exists()


def test_idempotent_second_run(monkeypatch, tmp_path):
    _patch_paths(monkeypatch, tmp_path)
    csd.reset_chapters(apply=True)
    first = (tmp_path / "chapters.json").read_text(encoding="utf-8")
    csd.reset_chapters(apply=True)
    assert (tmp_path / "chapters.json").read_text(encoding="utf-8") == first
