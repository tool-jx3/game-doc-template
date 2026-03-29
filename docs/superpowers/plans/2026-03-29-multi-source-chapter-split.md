# Multi-Source Chapter Split Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Support multiple PDF sources in a single documentation site while maintaining full backward compatibility with single-PDF projects.

**Architecture:** Extend `chapters.json` with optional chapter-level `source`/`clean_patterns`/`images` overrides. New `merge_multi.py` script combines per-PDF configs. `split_chapters.py` gains recursive file traversal, per-chapter source loading with caching, and `_meta.yml` generation. `starlight-auto-sidebar` plugin handles deep sidebar nesting.

**Tech Stack:** Python 3.11+ (uv, pytest), Astro 5 + Starlight + starlight-auto-sidebar (bun), JSON config

**Spec:** `docs/superpowers/specs/2026-03-29-multi-source-chapter-split-design.md`

---

## File Structure

### New Files

| File | Responsibility |
|------|---------------|
| `scripts/merge_multi.py` | CLI script: merge multiple `chapters_<name>.json` into one `chapters.json` |
| `scripts/tests/test_merge_multi.py` | Tests for merge_multi.py |
| `scripts/tests/test_multi_source_split.py` | Tests for multi-source split_chapters.py changes |
| `scripts/tests/test_multi_source_progress.py` | Tests for recursive progress tracking |

### Modified Files

| File | Changes |
|------|---------|
| `scripts/split_chapters.py` | `normalize_files()`, `resolve_config()`, `write_meta_yml()`, recursive `process_files()`, source/manifest caching, refactor `split_chapters()` to per-chapter loop |
| `scripts/generate_nav.py` | `first_file_description()` recursive, `first_leaf_path()` for link safety |
| `scripts/init_create_progress.py` | Recursive `iter_chapter_files()` with source field |
| `scripts/progress_read.py` | `--source` filter flag |
| `docs/astro.config.mjs` | Add `starlight-auto-sidebar` plugin |
| `docs/src/content.config.ts` | Add `autoSidebar` collection |
| `docs/package.json` | New dependency (via `bun add`) |

---

## Chunk 1: Core utilities in `split_chapters.py`

### Task 1: `normalize_files()` — flatten slash paths to recursive structure

**Files:**
- Modify: `scripts/split_chapters.py`
- Test: `scripts/tests/test_split_chapters.py`

- [ ] **Step 1: Write failing tests for `normalize_files()`**

Add to `scripts/tests/test_split_chapters.py`:

```python
from split_chapters import normalize_files


class TestNormalizeFiles:
    def test_flat_entry_unchanged(self):
        files = {"actions": {"title": "Actions", "pages": [5, 7], "order": 0}}
        result = normalize_files(files)
        assert result == files

    def test_single_slash_path_becomes_nested(self):
        files = {"combat/actions": {"title": "Actions", "pages": [5, 7], "order": 0}}
        result = normalize_files(files)
        assert "combat" in result
        assert "files" in result["combat"]
        assert "actions" in result["combat"]["files"]
        assert result["combat"]["files"]["actions"]["pages"] == [5, 7]
        assert result["combat"]["title"] == "combat"

    def test_multi_level_slash_path(self):
        files = {"a/b/c": {"title": "C", "pages": [1, 2], "order": 0}}
        result = normalize_files(files)
        assert "a" in result
        assert "b" in result["a"]["files"]
        assert "c" in result["a"]["files"]["b"]["files"]

    def test_multiple_children_same_parent(self):
        files = {
            "combat/actions": {"title": "Actions", "pages": [5, 7], "order": 0},
            "combat/damage": {"title": "Damage", "pages": [8, 10], "order": 1},
        }
        result = normalize_files(files)
        assert "combat" in result
        assert "actions" in result["combat"]["files"]
        assert "damage" in result["combat"]["files"]

    def test_mixed_flat_and_slash(self):
        files = {
            "index": {"title": "Index", "pages": [1, 4], "order": 0},
            "combat/actions": {"title": "Actions", "pages": [5, 7], "order": 1},
        }
        result = normalize_files(files)
        assert "index" in result
        assert "pages" in result["index"]
        assert "combat" in result
        assert "files" in result["combat"]

    def test_group_node_has_no_pages(self):
        files = {"combat/actions": {"title": "Actions", "pages": [5, 7], "order": 0}}
        result = normalize_files(files)
        assert "pages" not in result["combat"]

    def test_empty_files(self):
        assert normalize_files({}) == {}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd D:/Code/trpg-doc/game-doc-template && uv run pytest scripts/tests/test_split_chapters.py::TestNormalizeFiles -v`
Expected: FAIL — `ImportError: cannot import name 'normalize_files'`

- [ ] **Step 3: Implement `normalize_files()` in `split_chapters.py`**

Add after the `infer_source_stem()` function (around line 198):

```python
def normalize_files(files: dict) -> dict:
    """Convert flat slash-path entries into nested recursive structure.

    Entries like ``"combat/actions": {"pages": [5, 7]}`` become nested:
    ``"combat": {"title": "combat", "files": {"actions": {"pages": [5, 7]}}}``.

    Entries without slashes are kept as-is.  Group nodes created by
    normalisation get ``title`` set to the raw slug and no ``order``.
    """
    result: dict = {}
    for key, entry in files.items():
        if "/" in key and "pages" in entry:
            parts = key.split("/")
            parent = parts[0]
            child = "/".join(parts[1:])
            if parent not in result:
                result[parent] = {"title": parent, "files": {}}
            result[parent]["files"][child] = entry
        else:
            result[key] = entry
    # Recurse for multi-level slash paths
    for key, entry in result.items():
        if "files" in entry:
            entry["files"] = normalize_files(entry["files"])
    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd D:/Code/trpg-doc/game-doc-template && uv run pytest scripts/tests/test_split_chapters.py::TestNormalizeFiles -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/split_chapters.py scripts/tests/test_split_chapters.py
git commit -m "feat: add normalize_files() for slash-path to nested conversion"
```

---

### Task 2: `resolve_config()` — per-chapter config fallback

**Files:**
- Modify: `scripts/split_chapters.py`
- Test: `scripts/tests/test_split_chapters.py`

- [ ] **Step 1: Write failing tests for `resolve_config()`**

Add to `scripts/tests/test_split_chapters.py`:

```python
import pytest
from split_chapters import resolve_config


class TestResolveConfig:
    def test_chapter_source_overrides_top_level(self):
        chapter = {"source": "chapter_source.md"}
        top = {"source": "top_source.md"}
        cfg = resolve_config("test", chapter, top)
        assert cfg["source"] == "chapter_source.md"

    def test_fallback_to_top_level_source(self):
        chapter = {}
        top = {"source": "top_source.md"}
        cfg = resolve_config("test", chapter, top)
        assert cfg["source"] == "top_source.md"

    def test_missing_source_raises(self):
        with pytest.raises(ValueError, match="test"):
            resolve_config("test", {}, {})

    def test_chapter_clean_patterns_override(self):
        chapter = {"clean_patterns": ["\\[footer\\]"]}
        top = {"clean_patterns": ["\\[header\\]"]}
        cfg = resolve_config("test", chapter, top)
        assert cfg["clean_patterns"] == ["\\[footer\\]"]

    def test_fallback_clean_patterns(self):
        chapter = {}
        top = {"clean_patterns": ["\\[header\\]"]}
        cfg = resolve_config("test", chapter, top)
        assert cfg["clean_patterns"] == ["\\[header\\]"]

    def test_default_clean_patterns_empty(self):
        chapter = {"source": "s.md"}
        cfg = resolve_config("test", chapter, {})
        assert cfg["clean_patterns"] == []

    def test_chapter_images_override(self):
        chapter = {"source": "s.md", "images": {"enabled": True}}
        top = {"images": {"enabled": False}}
        cfg = resolve_config("test", chapter, top)
        assert cfg["images"]["enabled"] is True

    def test_default_images_empty(self):
        chapter = {"source": "s.md"}
        cfg = resolve_config("test", chapter, {})
        assert cfg["images"] == {}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd D:/Code/trpg-doc/game-doc-template && uv run pytest scripts/tests/test_split_chapters.py::TestResolveConfig -v`
Expected: FAIL — `ImportError: cannot import name 'resolve_config'`

- [ ] **Step 3: Implement `resolve_config()`**

Add after `normalize_files()` in `scripts/split_chapters.py`:

```python
def resolve_config(chapter_key: str, chapter: dict, top_level: dict) -> dict:
    """Resolve per-chapter config with fallback to top-level defaults.

    Returns a dict with keys: source, clean_patterns, images.
    Raises ValueError if no source can be determined.
    """
    source = chapter.get("source", top_level.get("source"))
    if not source:
        raise ValueError(
            f"Chapter '{chapter_key}' has no 'source' and no top-level 'source' defined"
        )
    return {
        "source": source,
        "clean_patterns": chapter.get(
            "clean_patterns", top_level.get("clean_patterns", [])
        ),
        "images": chapter.get("images", top_level.get("images", {})),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd D:/Code/trpg-doc/game-doc-template && uv run pytest scripts/tests/test_split_chapters.py::TestResolveConfig -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/split_chapters.py scripts/tests/test_split_chapters.py
git commit -m "feat: add resolve_config() for per-chapter config fallback"
```

---

### Task 3: `write_meta_yml()` — generate `_meta.yml` for group nodes

**Files:**
- Modify: `scripts/split_chapters.py`
- Test: `scripts/tests/test_split_chapters.py`

- [ ] **Step 1: Write failing tests for `write_meta_yml()`**

Add to `scripts/tests/test_split_chapters.py`:

```python
import tempfile
from split_chapters import write_meta_yml


class TestWriteMetaYml:
    def test_writes_label_and_order(self, tmp_path):
        entry = {"title": "Combat", "order": 1, "files": {}}
        write_meta_yml(tmp_path, entry)
        content = (tmp_path / "_meta.yml").read_text(encoding="utf-8")
        assert "label: Combat" in content
        assert "order: 1" in content

    def test_no_order_omits_order(self, tmp_path):
        entry = {"title": "Combat", "files": {}}
        write_meta_yml(tmp_path, entry)
        content = (tmp_path / "_meta.yml").read_text(encoding="utf-8")
        assert "label: Combat" in content
        assert "order" not in content

    def test_yaml_special_chars_quoted(self, tmp_path):
        entry = {"title": "Damage: Conditions & Recovery", "order": 2, "files": {}}
        write_meta_yml(tmp_path, entry)
        content = (tmp_path / "_meta.yml").read_text(encoding="utf-8")
        assert 'label: "Damage: Conditions & Recovery"' in content

    def test_overwrites_existing(self, tmp_path):
        (tmp_path / "_meta.yml").write_text("old content", encoding="utf-8")
        entry = {"title": "New", "order": 0, "files": {}}
        write_meta_yml(tmp_path, entry)
        content = (tmp_path / "_meta.yml").read_text(encoding="utf-8")
        assert "label: New" in content
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd D:/Code/trpg-doc/game-doc-template && uv run pytest scripts/tests/test_split_chapters.py::TestWriteMetaYml -v`
Expected: FAIL — `ImportError: cannot import name 'write_meta_yml'`

- [ ] **Step 3: Implement `write_meta_yml()`**

Add after `resolve_config()` in `scripts/split_chapters.py`:

```python
def write_meta_yml(directory: Path, entry: dict) -> None:
    """Write a ``_meta.yml`` file for a group node directory.

    Generates ``label`` from *entry["title"]* and ``order`` from
    *entry.get("order")*.  The file is compatible with the
    ``starlight-auto-sidebar`` plugin.
    """
    title = entry.get("title", directory.name)
    lines: list[str] = [f"label: {_yaml_safe(title)}"]
    order = entry.get("order")
    if order is not None:
        lines.append(f"order: {order}")
    (directory / "_meta.yml").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd D:/Code/trpg-doc/game-doc-template && uv run pytest scripts/tests/test_split_chapters.py::TestWriteMetaYml -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/split_chapters.py scripts/tests/test_split_chapters.py
git commit -m "feat: add write_meta_yml() for starlight-auto-sidebar"
```

---

## Chunk 2: `merge_multi.py` script

### Task 4: Create `merge_multi.py` with core merge logic

**Files:**
- Create: `scripts/merge_multi.py`
- Create: `scripts/tests/test_merge_multi.py`

- [ ] **Step 1: Write failing tests for merge logic**

Create `scripts/tests/test_merge_multi.py`:

```python
"""Tests for merge_multi module."""

import json
import pytest
from pathlib import Path

from merge_multi import merge_configs, validate_merge


class TestMergeConfigs:
    def _make_config(self, slug, title, order, source, chapters=None):
        return {
            "slug": slug,
            "title": title,
            "order": order,
            "source": source,
            "output_dir": "docs/src/content/docs",
            "mode": "bilingual",
            "chapters": chapters or {},
        }

    def test_single_config_produces_one_chapter(self):
        configs = [
            self._make_config("core", "Core Rules", 1, "core_pages.md", {
                "combat": {
                    "title": "Combat",
                    "order": 1,
                    "files": {"actions": {"title": "Actions", "pages": [5, 7], "order": 0}},
                }
            })
        ]
        result = merge_configs(configs)
        assert "core" in result["chapters"]
        assert result["chapters"]["core"]["source"] == "core_pages.md"
        assert result["chapters"]["core"]["title"] == "Core Rules"
        # Original chapters become files (demoted one level)
        assert "combat" in result["chapters"]["core"]["files"]
        assert "actions" in result["chapters"]["core"]["files"]["combat"]["files"]

    def test_two_configs_both_present(self):
        configs = [
            self._make_config("core", "Core", 1, "core.md"),
            self._make_config("exp", "Expansion", 2, "exp.md"),
        ]
        result = merge_configs(configs)
        assert "core" in result["chapters"]
        assert "exp" in result["chapters"]

    def test_inherits_mode_from_first(self):
        c1 = self._make_config("a", "A", 1, "a.md")
        c1["mode"] = "bilingual"
        c2 = self._make_config("b", "B", 2, "b.md")
        c2["mode"] = "zh_only"
        result = merge_configs([c1, c2])
        assert result["mode"] == "bilingual"

    def test_inherits_output_dir_from_first(self):
        c1 = self._make_config("a", "A", 1, "a.md")
        c1["output_dir"] = "custom/path"
        result = merge_configs([c1])
        assert result["output_dir"] == "custom/path"

    def test_chapter_level_clean_patterns(self):
        c1 = self._make_config("core", "Core", 1, "core.md")
        c1["clean_patterns"] = ["\\[footer\\]"]
        result = merge_configs([c1])
        assert result["chapters"]["core"]["clean_patterns"] == ["\\[footer\\]"]

    def test_chapter_level_images(self):
        c1 = self._make_config("core", "Core", 1, "core.md")
        c1["images"] = {"enabled": True, "assets_dir": "docs/src/assets"}
        result = merge_configs([c1])
        assert result["chapters"]["core"]["images"]["enabled"] is True

    def test_source_injected_into_chapter(self):
        configs = [self._make_config("core", "Core", 1, "core_pages.md")]
        result = merge_configs(configs)
        assert result["chapters"]["core"]["source"] == "core_pages.md"

    def test_mode_override(self):
        configs = [self._make_config("a", "A", 1, "a.md")]
        result = merge_configs(configs, mode_override="zh_only")
        assert result["mode"] == "zh_only"

    def test_output_dir_override(self):
        configs = [self._make_config("a", "A", 1, "a.md")]
        result = merge_configs(configs, output_dir_override="custom")
        assert result["output_dir"] == "custom"


class TestValidateMerge:
    def test_duplicate_slugs_raises(self):
        configs = [
            {"slug": "core", "title": "A", "order": 1, "source": "a.md", "chapters": {}},
            {"slug": "core", "title": "B", "order": 2, "source": "b.md", "chapters": {}},
        ]
        with pytest.raises(ValueError, match="core"):
            validate_merge(configs)

    def test_duplicate_orders_warns(self, capsys):
        configs = [
            {"slug": "a", "title": "A", "order": 1, "source": "a.md", "chapters": {}},
            {"slug": "b", "title": "B", "order": 1, "source": "b.md", "chapters": {}},
        ]
        validate_merge(configs)  # Should not raise
        captured = capsys.readouterr()
        assert "order" in captured.err.lower() or "order" in captured.out.lower()

    def test_valid_configs_pass(self):
        configs = [
            {"slug": "a", "title": "A", "order": 1, "source": "a.md", "chapters": {}},
            {"slug": "b", "title": "B", "order": 2, "source": "b.md", "chapters": {}},
        ]
        validate_merge(configs)  # Should not raise
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd D:/Code/trpg-doc/game-doc-template && uv run pytest scripts/tests/test_merge_multi.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'merge_multi'`

- [ ] **Step 3: Implement `merge_multi.py`**

Create `scripts/merge_multi.py`:

```python
#!/usr/bin/env python3
"""Merge multiple chapters_<name>.json files into a single chapters.json."""

from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path

from split_chapters import normalize_files

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_merge(configs: list[dict]) -> None:
    """Validate configs before merging.

    Raises ValueError on duplicate slugs.  Prints warning on duplicate orders.
    """
    slugs: list[str] = []
    orders: list[int] = []
    for cfg in configs:
        slug = cfg["slug"]
        if slug in slugs:
            raise ValueError(f"Duplicate slug: '{slug}'")
        slugs.append(slug)
        order = cfg.get("order")
        if order is not None:
            if order in orders:
                print(
                    f"⚠ Warning: duplicate order {order} "
                    f"(slug '{slug}' conflicts with earlier entry)",
                    file=sys.stderr,
                )
            orders.append(order)


def merge_configs(
    configs: list[dict],
    *,
    mode_override: str | None = None,
    output_dir_override: str | None = None,
) -> dict:
    """Merge per-PDF configs into a single chapters.json structure.

    Each input config must have: slug, title, order, source, chapters.
    The original ``chapters`` dict is demoted to ``files`` under the
    top-level chapter keyed by ``slug``.
    """
    first = configs[0]
    result: dict = {
        "output_dir": output_dir_override or first.get("output_dir", "docs/src/content/docs"),
        "mode": mode_override or first.get("mode", "zh_only"),
        "chapters": {},
    }
    # Inherit top-level images if present in first config
    if "images" not in result and "images" in first:
        result["images"] = first["images"]

    for cfg in configs:
        slug = cfg["slug"]
        chapter: dict = {
            "source": cfg["source"],
            "title": cfg["title"],
            "order": cfg["order"],
        }
        # Demote original chapters to files (each original chapter becomes
        # a group node with its own files).
        # Normalize flat slash-paths to recursive format per spec.
        original_chapters = cfg.get("chapters", {})
        chapter["files"] = {}
        for ch_key, ch_val in original_chapters.items():
            chapter["files"][ch_key] = ch_val
        chapter["files"] = normalize_files(chapter["files"])
        # Move per-source overridable fields to chapter level
        if "clean_patterns" in cfg:
            chapter["clean_patterns"] = cfg["clean_patterns"]
        if "images" in cfg:
            chapter["images"] = cfg["images"]
        result["chapters"][slug] = chapter

    return result


def expand_paths(patterns: list[str]) -> list[Path]:
    """Expand glob patterns and return sorted unique paths."""
    paths: list[Path] = []
    for pattern in patterns:
        expanded = glob.glob(pattern)
        if expanded:
            for p in expanded:
                path = Path(p)
                if path not in paths:
                    paths.append(path)
        else:
            # Treat as literal path
            path = Path(pattern)
            if path not in paths:
                paths.append(path)
    return sorted(paths)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Merge multiple chapters_<name>.json into chapters.json"
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        help="Input JSON files or glob patterns (e.g., chapters_*.json)",
    )
    parser.add_argument(
        "-o", "--output",
        default="chapters.json",
        help="Output path (default: chapters.json)",
    )
    parser.add_argument("--mode", help="Override mode (bilingual or zh_only)")
    parser.add_argument("--output-dir", help="Override output_dir")
    args = parser.parse_args()

    input_paths = expand_paths(args.inputs)
    if not input_paths:
        print("❌ No input files found", file=sys.stderr)
        raise SystemExit(1)

    configs = []
    for path in input_paths:
        if not path.exists():
            print(f"❌ File not found: {path}", file=sys.stderr)
            raise SystemExit(1)
        configs.append(load_json(path))

    validate_merge(configs)
    result = merge_configs(
        configs,
        mode_override=args.mode,
        output_dir_override=args.output_dir,
    )

    # Warn about missing index leaf nodes
    for slug, chapter in result["chapters"].items():
        files = chapter.get("files", {})
        has_index = any(
            k == "index" and "pages" in v for k, v in files.items()
        )
        if not has_index:
            print(
                f"⚠ Warning: chapter '{slug}' has no 'index' leaf node "
                f"(homepage link may 404)",
                file=sys.stderr,
            )

    output_path = Path(args.output)
    output_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"✓ Merged {len(configs)} configs → {output_path}")
    for slug, chapter in result["chapters"].items():
        print(f"  /{slug}/ → {chapter['title']} (source: {chapter['source']})")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd D:/Code/trpg-doc/game-doc-template && uv run pytest scripts/tests/test_merge_multi.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/merge_multi.py scripts/tests/test_merge_multi.py
git commit -m "feat: add merge_multi.py for combining per-PDF chapter configs"
```

---

### Task 5: CLI integration test for `merge_multi.py`

**Files:**
- Modify: `scripts/tests/test_merge_multi.py`

- [ ] **Step 1: Write CLI integration test**

Add to `scripts/tests/test_merge_multi.py`:

```python
import subprocess
import tempfile


class TestMergeMultiCLI:
    def test_merge_two_files_produces_output(self, tmp_path):
        c1 = {
            "slug": "core", "title": "Core", "order": 1,
            "source": "core_pages.md", "output_dir": "docs/src/content/docs",
            "mode": "bilingual", "chapters": {},
        }
        c2 = {
            "slug": "exp", "title": "Expansion", "order": 2,
            "source": "exp_pages.md", "output_dir": "docs/src/content/docs",
            "mode": "bilingual", "chapters": {},
        }
        f1 = tmp_path / "chapters_core.json"
        f2 = tmp_path / "chapters_exp.json"
        out = tmp_path / "chapters.json"
        f1.write_text(json.dumps(c1), encoding="utf-8")
        f2.write_text(json.dumps(c2), encoding="utf-8")

        result = subprocess.run(
            ["uv", "run", "python", "scripts/merge_multi.py",
             str(f1), str(f2), "-o", str(out)],
            capture_output=True, text=True,
            cwd=str(Path(__file__).resolve().parents[2]),
        )
        assert result.returncode == 0
        merged = json.loads(out.read_text(encoding="utf-8"))
        assert "core" in merged["chapters"]
        assert "exp" in merged["chapters"]
```

- [ ] **Step 2: Run test to verify it passes**

Run: `cd D:/Code/trpg-doc/game-doc-template && uv run pytest scripts/tests/test_merge_multi.py::TestMergeMultiCLI -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add scripts/tests/test_merge_multi.py
git commit -m "test: add CLI integration test for merge_multi.py"
```

---

## Chunk 3: Refactor `split_chapters.py` for multi-source

### Task 6: Refactor `split_chapters()` to per-chapter source loading

**Files:**
- Modify: `scripts/split_chapters.py`
- Test: `scripts/tests/test_multi_source_split.py`

This is the core refactoring. The current `split_chapters()` loads one source at the top. We change it to iterate chapters, resolve config per-chapter, and load sources with caching.

- [ ] **Step 1: Write integration test for multi-source split**

Create `scripts/tests/test_multi_source_split.py`:

```python
"""Integration tests for multi-source chapter splitting."""

import json
import pytest
from pathlib import Path

from split_chapters import split_chapters


class TestMultiSourceSplit:
    def _make_pages_md(self, tmp_path, name, pages):
        """Create a _pages.md file with given page contents."""
        parts = []
        for num, text in pages.items():
            parts.append(f"<!-- PAGE {num} -->\n\n{text}")
        content = "\n\n".join(parts)
        path = tmp_path / f"{name}_pages.md"
        path.write_text(content, encoding="utf-8")
        return str(path)

    def test_single_source_backward_compat(self, tmp_path):
        source = self._make_pages_md(tmp_path, "rules", {
            1: "# Introduction\n\nWelcome to the game.",
            2: "## Combat\n\nFight stuff.",
        })
        output_dir = tmp_path / "docs"
        config = {
            "source": source,
            "output_dir": str(output_dir),
            "chapters": {
                "intro": {
                    "title": "Introduction",
                    "order": 1,
                    "files": {
                        "index": {"title": "Intro", "pages": [1, 1], "order": 0},
                    },
                },
            },
        }
        split_chapters(config, tmp_path)
        assert (output_dir / "intro" / "index.md").exists()

    def test_multi_source_chapter_level(self, tmp_path):
        source_a = self._make_pages_md(tmp_path, "core", {
            1: "# Core Rules\n\nCore content.",
        })
        source_b = self._make_pages_md(tmp_path, "exp", {
            1: "# Expansion\n\nNew stuff.",
        })
        output_dir = tmp_path / "docs"
        config = {
            "output_dir": str(output_dir),
            "chapters": {
                "core": {
                    "source": source_a,
                    "title": "Core",
                    "order": 1,
                    "files": {
                        "index": {"title": "Core", "pages": [1, 1], "order": 0},
                    },
                },
                "expansion": {
                    "source": source_b,
                    "title": "Expansion",
                    "order": 2,
                    "files": {
                        "index": {"title": "Expansion", "pages": [1, 1], "order": 0},
                    },
                },
            },
        }
        split_chapters(config, tmp_path)
        assert (output_dir / "core" / "index.md").exists()
        assert (output_dir / "expansion" / "index.md").exists()

    def test_recursive_files_creates_subdirs(self, tmp_path):
        source = self._make_pages_md(tmp_path, "rules", {
            1: "Actions content", 2: "Damage content",
        })
        output_dir = tmp_path / "docs"
        config = {
            "source": source,
            "output_dir": str(output_dir),
            "chapters": {
                "rules": {
                    "title": "Rules",
                    "order": 1,
                    "files": {
                        "combat": {
                            "title": "Combat",
                            "order": 0,
                            "files": {
                                "actions": {"title": "Actions", "pages": [1, 1], "order": 0},
                                "damage": {"title": "Damage", "pages": [2, 2], "order": 1},
                            },
                        },
                    },
                },
            },
        }
        split_chapters(config, tmp_path)
        assert (output_dir / "rules" / "combat" / "actions.md").exists()
        assert (output_dir / "rules" / "combat" / "damage.md").exists()

    def test_meta_yml_generated_for_groups(self, tmp_path):
        source = self._make_pages_md(tmp_path, "rules", {1: "Content"})
        output_dir = tmp_path / "docs"
        config = {
            "source": source,
            "output_dir": str(output_dir),
            "chapters": {
                "rules": {
                    "title": "Rules",
                    "order": 1,
                    "files": {
                        "combat": {
                            "title": "Combat",
                            "order": 0,
                            "files": {
                                "actions": {"title": "Actions", "pages": [1, 1], "order": 0},
                            },
                        },
                    },
                },
            },
        }
        split_chapters(config, tmp_path)
        meta = output_dir / "rules" / "_meta.yml"
        assert meta.exists()
        content = meta.read_text(encoding="utf-8")
        assert "label: Rules" in content
        assert "order: 1" in content

        combat_meta = output_dir / "rules" / "combat" / "_meta.yml"
        assert combat_meta.exists()
        combat_content = combat_meta.read_text(encoding="utf-8")
        assert "label: Combat" in combat_content

    def test_flat_slash_paths_normalized(self, tmp_path):
        source = self._make_pages_md(tmp_path, "rules", {
            1: "Actions", 2: "Damage",
        })
        output_dir = tmp_path / "docs"
        config = {
            "source": source,
            "output_dir": str(output_dir),
            "chapters": {
                "rules": {
                    "title": "Rules",
                    "order": 1,
                    "files": {
                        "combat/actions": {"title": "Actions", "pages": [1, 1], "order": 0},
                        "combat/damage": {"title": "Damage", "pages": [2, 2], "order": 1},
                    },
                },
            },
        }
        split_chapters(config, tmp_path)
        assert (output_dir / "rules" / "combat" / "actions.md").exists()
        assert (output_dir / "rules" / "combat" / "damage.md").exists()
        # Synthetic group node gets _meta.yml with raw slug label
        combat_meta = output_dir / "rules" / "combat" / "_meta.yml"
        assert combat_meta.exists()
        content = combat_meta.read_text(encoding="utf-8")
        assert "label: combat" in content
        assert "order" not in content  # Synthetic nodes have no order

    def test_bilingual_mode_meta_yml(self, tmp_path):
        source = self._make_pages_md(tmp_path, "rules", {1: "Content"})
        output_dir = tmp_path / "docs"
        config = {
            "source": source,
            "output_dir": str(output_dir),
            "mode": "bilingual",
            "chapters": {
                "rules": {
                    "title": "Rules",
                    "order": 1,
                    "files": {
                        "index": {"title": "Index", "pages": [1, 1], "order": 0},
                    },
                },
            },
        }
        split_chapters(config, tmp_path)
        assert (output_dir / "bilingual" / "rules" / "index.md").exists()
        # bilingual/ wrapper dir should not get a _meta.yml (it's not a chapter)
        # but rules/ should
        rules_meta = output_dir / "bilingual" / "rules" / "_meta.yml"
        assert rules_meta.exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd D:/Code/trpg-doc/game-doc-template && uv run pytest scripts/tests/test_multi_source_split.py -v`
Expected: FAIL — tests fail because `split_chapters()` doesn't support chapter-level source or recursive files yet

- [ ] **Step 3: Refactor `split_chapters()` function**

Add module-level caches before `split_chapters()` (around line 389):

```python
_page_cache: dict[str, dict[int, str]] = {}
_manifest_cache: dict[str, tuple[list[dict], Path | None, dict]] = {}


def _load_pages_cached(source_path: Path) -> dict[int, str]:
    """Load and cache pages from a _pages.md file."""
    key = str(source_path)
    if key not in _page_cache:
        content = source_path.read_text(encoding="utf-8")
        _page_cache[key] = extract_pages(content)
    return _page_cache[key]


def _load_manifest_cached(
    source: str, images_config: dict, project_root: Path
) -> tuple[list[dict], Path | None, dict]:
    """Load and cache image manifest for a source."""
    if source not in _manifest_cache:
        dummy_config = {"source": source, "images": images_config}
        _manifest_cache[source] = load_image_manifest(dummy_config, project_root)
    return _manifest_cache[source]


def process_files(
    files: dict,
    output_dir: Path,
    pages: dict[int, str],
    clean_patterns: list[str],
    page_images: dict[int, list[dict]],
    project_root: Path,
    assets_dir: Path,
    source_slug: str,
) -> tuple[int, int]:
    """Recursively process files dict. Returns (total_files, total_images)."""
    total_files = 0
    total_images = 0
    for key, entry in files.items():
        if "pages" in entry:
            # Leaf node — write .md file
            title = entry["title"]
            description = entry.get("description", "")
            order = entry.get("order")
            start_page, end_page = entry["pages"]
            output_path = output_dir / f"{key}.md"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            section_content, image_count = build_section_content(
                pages, start_page, end_page, clean_patterns,
                page_images, output_path, project_root, assets_dir, source_slug,
            )
            frontmatter = generate_frontmatter(title, description, order)
            section_content = _strip_duplicate_heading(section_content, title)
            full_content = frontmatter + "\n" + section_content
            output_path.write_text(full_content, encoding="utf-8")
            char_count = len(section_content)
            image_note = f", {image_count} 張圖" if image_count else ""
            print(
                f"   ✓ {key}.md - {title} "
                f"(p.{start_page}-{end_page}, {char_count:,} 字{image_note})"
            )
            total_files += 1
            total_images += image_count
        elif "files" in entry:
            # Group node — create subdirectory + _meta.yml, recurse
            sub_dir = output_dir / key
            sub_dir.mkdir(parents=True, exist_ok=True)
            write_meta_yml(sub_dir, entry)
            sub_files, sub_images = process_files(
                entry["files"], sub_dir, pages, clean_patterns,
                page_images, project_root, assets_dir, source_slug,
            )
            total_files += sub_files
            total_images += sub_images
        else:
            raise ValueError(f"Invalid entry '{key}': must have 'pages' or 'files'")
    return total_files, total_images
```

Replace the `split_chapters()` function (lines 391-463) with:

```python
def split_chapters(config: dict, project_root: Path):
    """根據設定拆分章節（支援多 source 與遞迴 files）"""
    output_dir = project_root / config.get("output_dir", "docs/src/content/docs")
    if config.get("mode") == "bilingual":
        output_dir = output_dir / "bilingual"

    # Clear caches for fresh run
    _page_cache.clear()
    _manifest_cache.clear()

    total_files = 0
    total_images = 0

    for section_name, section_config in config["chapters"].items():
        # Resolve per-chapter config with fallback
        ch_config = resolve_config(section_name, section_config, config)
        source_path = project_root / ch_config["source"]
        clean_patterns = ch_config["clean_patterns"]
        images_config = ch_config["images"]

        if not source_path.exists():
            print(f"❌ 找不到來源檔案: {source_path}")
            sys.exit(1)

        # Load pages (cached)
        pages = _load_pages_cached(source_path)

        # Load images (cached)
        page_text_stats = build_page_text_stats(pages, clean_patterns)
        manifest_images, manifest_path, image_policy = _load_manifest_cached(
            ch_config["source"], images_config, project_root
        )
        page_images, skipped = group_images_by_page(
            manifest_images, page_text_stats, image_policy
        )
        assets_dir = resolve_assets_dir(
            {"images": images_config}, project_root
        )
        source_slug = infer_source_stem(Path(ch_config["source"]))

        section_title = section_config.get("title", section_name)
        print(f"\n📁 {section_title} ({section_name}/) [source: {ch_config['source']}]")

        # Create section directory + _meta.yml
        section_dir = output_dir / section_name
        section_dir.mkdir(parents=True, exist_ok=True)
        write_meta_yml(section_dir, section_config)

        # Normalize flat slash-paths to recursive structure
        files = normalize_files(section_config.get("files", {}))

        # Process recursively
        sec_files, sec_images = process_files(
            files, section_dir, pages, clean_patterns,
            page_images, project_root, assets_dir, source_slug,
        )
        total_files += sec_files
        total_images += sec_images

    print("-" * 50)
    print(f"✅ 完成！共產生 {total_files} 個檔案，插入 {total_images} 張圖片")
```

- [ ] **Step 4: Run all split tests to verify they pass**

Run: `cd D:/Code/trpg-doc/game-doc-template && uv run pytest scripts/tests/test_split_chapters.py scripts/tests/test_multi_source_split.py -v`
Expected: All PASS (both old and new tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/split_chapters.py scripts/tests/test_multi_source_split.py
git commit -m "feat: refactor split_chapters() for multi-source with recursive files"
```

---

## Chunk 4: `generate_nav.py` changes

### Task 7: Recursive `first_file_description()` and `first_leaf_path()`

**Files:**
- Modify: `scripts/generate_nav.py`
- Modify: `scripts/tests/test_generate_nav.py`

- [ ] **Step 1: Write failing tests**

Add to `scripts/tests/test_generate_nav.py`:

```python
from generate_nav import first_file_description, first_leaf_path


class TestFirstFileDescriptionRecursive:
    def test_flat_files(self):
        section = {
            "files": {
                "index": {"order": 0, "description": "Overview"},
                "combat": {"order": 1, "description": "Combat rules"},
            }
        }
        assert first_file_description(section) == "Overview"

    def test_nested_finds_leaf(self):
        section = {
            "files": {
                "combat": {
                    "order": 0,
                    "files": {
                        "actions": {"order": 0, "description": "Action rules", "pages": [1, 2]},
                    },
                },
            }
        }
        assert first_file_description(section) == "Action rules"

    def test_empty_files(self):
        assert first_file_description({"files": {}}) == ""

    def test_no_description_returns_empty(self):
        section = {"files": {"index": {"order": 0, "pages": [1, 1]}}}
        assert first_file_description(section) == ""


class TestFirstLeafPath:
    def test_flat_leaf(self):
        files = {"index": {"order": 0, "pages": [1, 1]}}
        assert first_leaf_path(files, "/rules") == "/rules/index"

    def test_nested_leaf(self):
        files = {
            "combat": {
                "order": 0,
                "files": {
                    "actions": {"order": 0, "pages": [5, 7]},
                },
            },
        }
        assert first_leaf_path(files, "/rules") == "/rules/combat/actions"

    def test_respects_order(self):
        files = {
            "magic": {"order": 2, "pages": [10, 12]},
            "combat": {"order": 1, "pages": [5, 7]},
        }
        assert first_leaf_path(files, "/rules") == "/rules/combat"

    def test_empty_files_returns_prefix(self):
        assert first_leaf_path({}, "/rules") == "/rules"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd D:/Code/trpg-doc/game-doc-template && uv run pytest scripts/tests/test_generate_nav.py -v`
Expected: FAIL — `ImportError: cannot import name 'first_leaf_path'`

- [ ] **Step 3: Implement recursive functions**

In `scripts/generate_nav.py`, replace `first_file_description()` (lines 27-34) and add `first_leaf_path()`:

```python
def first_file_description(section: dict) -> str:
    """Get description from the first leaf file in section (recursive)."""
    files = section.get("files", {})
    for _fname, cfg in sorted(files.items(), key=lambda x: x[1].get("order", 9999)):
        if "pages" in cfg:
            desc = cfg.get("description", "")
            if desc:
                return desc
        elif "files" in cfg:
            desc = first_file_description(cfg)
            if desc:
                return desc
    return ""


def first_leaf_path(files: dict, path_prefix: str) -> str:
    """Recursively find the path to the first leaf node (by order)."""
    for key, entry in sorted(files.items(), key=lambda x: x[1].get("order", 9999)):
        if "pages" in entry:
            return f"{path_prefix}/{key}"
        elif "files" in entry:
            result = first_leaf_path(entry["files"], f"{path_prefix}/{key}")
            if result != f"{path_prefix}/{key}":
                return result
    return path_prefix
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd D:/Code/trpg-doc/game-doc-template && uv run pytest scripts/tests/test_generate_nav.py -v`
Expected: All PASS

- [ ] **Step 5: Write test for `generate_index()` with nested configs**

Add to `scripts/tests/test_generate_nav.py`:

```python
class TestGenerateIndexNestedLinks:
    def test_hero_links_resolve_to_first_leaf(self):
        chapters = {
            "core-rules": {
                "title": "Core Rules",
                "order": 1,
                "files": {
                    "combat": {
                        "title": "Combat",
                        "order": 0,
                        "files": {
                            "actions": {"order": 0, "pages": [5, 7], "description": "Action rules"},
                        },
                    },
                },
            },
            "expansion": {
                "title": "Expansion",
                "order": 2,
                "files": {
                    "new-classes": {"order": 0, "pages": [1, 8], "description": "New classes"},
                },
            },
        }
        style = {"site": {"title": "Test", "description": "Test site"}}
        result = gn.generate_index(chapters, style)
        # Hero link should point to first leaf, not group node
        assert "/core-rules/combat/actions/" in result
        # LinkCard should also resolve
        assert 'href="/core-rules/combat/actions/"' in result

    def test_hero_links_flat_files_unchanged(self):
        chapters = {
            "combat": {
                "title": "Combat",
                "order": 1,
                "files": {
                    "index": {"order": 0, "pages": [1, 2], "description": "Combat rules"},
                },
            },
        }
        style = {"site": {"title": "Test"}}
        result = gn.generate_index(chapters, style)
        # Flat files should link to section slug directly
        assert "/combat/" in result
```

- [ ] **Step 6: Update `generate_index()` to use `first_leaf_path()`**

In `scripts/generate_nav.py`, modify `generate_index()`:

1. For hero action links (around line 97), replace `/{first_slug}/` with resolved path:

```python
# Before the hero actions block, resolve link targets
first_link = first_leaf_path(sections[0][1].get("files", {}), f"/{first_slug}")
second_link = first_leaf_path(sections[1][1].get("files", {}), f"/{second_slug}") if len(sections) > 1 else first_link
```

Then use `first_link` and `second_link` in the hero lines:
```python
f"      link: {first_link}/",
...
f"      link: {second_link}/",
```

2. For LinkCard entries (around line 126), resolve each href:

```python
for slug, section in sections:
    title = section["title"]
    desc = first_file_description(section)
    link = first_leaf_path(section.get("files", {}), f"/{slug}")
    lines.append(f'  <LinkCard title="{title}" href="{link}/" description="{desc}" />')
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd D:/Code/trpg-doc/game-doc-template && uv run pytest scripts/tests/test_generate_nav.py -v`
Expected: All PASS

- [ ] **Step 8: Commit**

```bash
git add scripts/generate_nav.py scripts/tests/test_generate_nav.py
git commit -m "feat: recursive first_file_description() and first_leaf_path() with generate_index() integration"
```

---

## Chunk 5: Progress tracking changes

### Task 8: Recursive `iter_chapter_files()` with source field

**Files:**
- Modify: `scripts/init_create_progress.py`
- Create: `scripts/tests/test_multi_source_progress.py`

- [ ] **Step 1: Write failing tests**

Create `scripts/tests/test_multi_source_progress.py`:

```python
"""Tests for multi-source progress tracking."""

import pytest

from init_create_progress import iter_chapter_files


class TestIterChapterFilesRecursive:
    def test_flat_files(self):
        config = {
            "output_dir": "docs/src/content/docs",
            "chapters": {
                "combat": {
                    "title": "Combat",
                    "order": 1,
                    "files": {
                        "actions": {"title": "Actions", "pages": [5, 7], "order": 0},
                    },
                },
            },
        }
        result = list(iter_chapter_files(config))
        assert len(result) == 1
        assert result[0][1].endswith("combat/actions.md")

    def test_nested_files(self):
        config = {
            "output_dir": "docs/src/content/docs",
            "chapters": {
                "rules": {
                    "title": "Rules",
                    "order": 1,
                    "files": {
                        "combat": {
                            "title": "Combat",
                            "order": 0,
                            "files": {
                                "actions": {"title": "Actions", "pages": [5, 7], "order": 0},
                                "damage": {"title": "Damage", "pages": [8, 10], "order": 1},
                            },
                        },
                    },
                },
            },
        }
        result = list(iter_chapter_files(config))
        assert len(result) == 2
        paths = [r[1] for r in result]
        assert any("rules/combat/actions.md" in p for p in paths)
        assert any("rules/combat/damage.md" in p for p in paths)

    def test_group_nodes_skipped(self):
        config = {
            "output_dir": "docs/src/content/docs",
            "chapters": {
                "rules": {
                    "title": "Rules",
                    "order": 1,
                    "files": {
                        "combat": {
                            "title": "Combat",
                            "order": 0,
                            "files": {
                                "actions": {"title": "Actions", "pages": [1, 1], "order": 0},
                            },
                        },
                    },
                },
            },
        }
        result = list(iter_chapter_files(config))
        # Only leaf nodes, not group nodes
        assert len(result) == 1

    def test_source_field_from_chapter(self):
        config = {
            "output_dir": "docs/src/content/docs",
            "chapters": {
                "core": {
                    "source": "core_pages.md",
                    "title": "Core",
                    "order": 1,
                    "files": {
                        "index": {"title": "Index", "pages": [1, 1], "order": 0},
                    },
                },
            },
        }
        result = list(iter_chapter_files(config))
        assert len(result) == 1
        # Result tuple has 4 elements: (section_slug, rel_path, file_cfg, source)
        section_slug, rel_path, file_cfg, source = result[0]
        assert source == "core_pages.md"

    def test_bilingual_mode(self):
        config = {
            "output_dir": "docs/src/content/docs",
            "mode": "bilingual",
            "chapters": {
                "core": {
                    "title": "Core",
                    "order": 1,
                    "files": {
                        "index": {"title": "Index", "pages": [1, 1], "order": 0},
                    },
                },
            },
        }
        result = list(iter_chapter_files(config))
        section_slug, rel_path, file_cfg, source = result[0]
        assert "bilingual" in rel_path
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd D:/Code/trpg-doc/game-doc-template && uv run pytest scripts/tests/test_multi_source_progress.py -v`
Expected: FAIL — current `iter_chapter_files()` doesn't handle nested files or source field

- [ ] **Step 3: Rewrite `iter_chapter_files()` and `build_progress()` in `init_create_progress.py`**

Replace `iter_chapter_files()` (lines 36-50) and `_walk_files()` helper, then update `build_progress()` (lines 65-89):

```python
def iter_chapter_files(
    config: dict[str, Any],
) -> list[tuple[str, str, dict[str, Any], str]]:
    """Walk chapter config recursively.

    Returns list of (section_slug, rel_path, file_cfg, source) for each
    leaf node.  The 4th element *source* comes from the chapter-level
    ``source`` field (or top-level fallback).
    """
    chapter_map = config.get("chapters", {})
    output_dir = config.get("output_dir", "docs/src/content/docs")
    mode = config.get("mode", "zh_only")
    base = f"{output_dir}/bilingual" if mode == "bilingual" else output_dir

    results: list[tuple[str, str, dict[str, Any], str]] = []

    for section_slug, section in sorted(
        chapter_map.items(), key=lambda x: x[1].get("order", 9999)
    ):
        if section_slug.startswith("_"):
            continue
        source = section.get("source", config.get("source", ""))
        _walk_files(
            section.get("files", {}),
            path_prefix=f"{base}/{section_slug}",
            section_slug=section_slug,
            source=source,
            results=results,
        )

    return results


def _walk_files(
    files: dict,
    path_prefix: str,
    section_slug: str,
    source: str,
    results: list[tuple[str, str, dict[str, Any], str]],
) -> None:
    """Recursively walk files dict, collecting leaf nodes."""
    for key, entry in sorted(
        files.items(), key=lambda x: x[1].get("order", 9999)
    ):
        current_path = f"{path_prefix}/{key}"
        if "pages" in entry:
            results.append((section_slug, f"{current_path}.md", entry, source))
        elif "files" in entry:
            _walk_files(
                entry["files"], current_path, section_slug, source, results
            )
```

Replace `build_progress()` (lines 65-89) with:

```python
def build_progress(config: dict[str, Any]) -> dict[str, Any]:
    chapters = []
    for _, rel_path, file_cfg, source in iter_chapter_files(config):
        title = str(file_cfg.get("title", Path(rel_path).stem))
        entry: dict[str, Any] = {
            "id": chapter_id_from_path(rel_path),
            "title": title,
            "file": rel_path,
            "source_pages": page_range_to_string(file_cfg.get("pages")),
            "status": "not_started",
            "notes": "",
        }
        if source:
            entry["source"] = source
        chapters.append(entry)

    payload = {
        "_meta": {
            "description": "Translation progress tracker",
            "updated": now_date(),
            "total_chapters": len(chapters),
            "completed": 0,
        },
        "chapters": chapters,
    }
    return payload
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd D:/Code/trpg-doc/game-doc-template && uv run pytest scripts/tests/test_multi_source_progress.py -v`
Expected: All PASS

- [ ] **Step 6: Run existing tests to verify backward compat**

Run: `cd D:/Code/trpg-doc/game-doc-template && uv run pytest tests/test_scripts.py -v -k "progress or Progress"`
Expected: All existing progress-related tests PASS

- [ ] **Step 7: Commit**

```bash
git add scripts/init_create_progress.py scripts/tests/test_multi_source_progress.py
git commit -m "feat: recursive iter_chapter_files() with source field for progress tracking"
```

---

### Task 9: `--source` filter in `progress_read.py`

**Files:**
- Modify: `scripts/progress_read.py`
- Modify: `scripts/tests/test_multi_source_progress.py`

- [ ] **Step 1: Write failing test**

Add to `scripts/tests/test_multi_source_progress.py`:

```python
import json
import subprocess
from pathlib import Path


class TestProgressReadSourceFilter:
    def test_source_filter(self, tmp_path):
        progress = {
            "_meta": {"total_chapters": 2, "completed": 0},
            "chapters": [
                {"id": "a", "title": "A", "file": "a.md", "source": "core_pages.md", "status": "not_started"},
                {"id": "b", "title": "B", "file": "b.md", "source": "exp_pages.md", "status": "not_started"},
            ],
        }
        pf = tmp_path / "progress.json"
        pf.write_text(json.dumps(progress), encoding="utf-8")

        result = subprocess.run(
            ["uv", "run", "python", "scripts/progress_read.py",
             "--progress-file", str(pf), "--source", "core", "--json"],
            capture_output=True, text=True,
            cwd=str(Path(__file__).resolve().parents[2]),
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert len(data["chapters"]) == 1
        assert data["chapters"][0]["source"] == "core_pages.md"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd D:/Code/trpg-doc/game-doc-template && uv run pytest scripts/tests/test_multi_source_progress.py::TestProgressReadSourceFilter -v`
Expected: FAIL — `--source` argument not recognized

- [ ] **Step 3: Add `--source` filter to `progress_read.py`**

In `scripts/progress_read.py`, add to `parse_args()` (around line 30):

```python
parser.add_argument(
    "--source",
    default=None,
    help="Filter by source (partial match on source field)",
)
```

In `main()`, add source filter **before** the existing status/next filtering (before line 62, right after `chapters = data.get("chapters", [])`):

```python
# Apply --source filter first (before status/next filtering)
if args.source:
    chapters = [
        c for c in chapters
        if args.source in c.get("source", "")
    ]
```

This ensures `--source core --next 3` first narrows to core-source chapters, then selects the next 3 from that subset.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd D:/Code/trpg-doc/game-doc-template && uv run pytest scripts/tests/test_multi_source_progress.py::TestProgressReadSourceFilter -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/progress_read.py scripts/tests/test_multi_source_progress.py
git commit -m "feat: add --source filter to progress_read.py"
```

---

## Chunk 6: Starlight auto-sidebar integration

### Task 10: Install `starlight-auto-sidebar` and configure

**Files:**
- Modify: `docs/package.json` (via bun add)
- Modify: `docs/astro.config.mjs`
- Modify: `docs/src/content.config.ts`

- [ ] **Step 1: Install the plugin**

Run: `cd D:/Code/trpg-doc/game-doc-template/docs && bun add starlight-auto-sidebar`

- [ ] **Step 2: Verify package.json updated**

Run: `cd D:/Code/trpg-doc/game-doc-template && cat docs/package.json | grep auto-sidebar`
Expected: `"starlight-auto-sidebar": "^X.Y.Z"` in dependencies

- [ ] **Step 3: Update `docs/astro.config.mjs`**

Add import at top of file:

```js
import starlightAutoSidebar from 'starlight-auto-sidebar'
```

Add to starlight plugins array (inside the `starlight({...})` call):

```js
plugins: [starlightAutoSidebar()],
```

- [ ] **Step 4: Update `docs/src/content.config.ts`**

Add imports:

```typescript
import { autoSidebarLoader } from 'starlight-auto-sidebar/loader';
import { autoSidebarSchema } from 'starlight-auto-sidebar/schema';
```

Add collection:

```typescript
autoSidebar: defineCollection({
    loader: autoSidebarLoader(),
    schema: autoSidebarSchema(),
}),
```

- [ ] **Step 5: Verify site builds**

Run: `cd D:/Code/trpg-doc/game-doc-template/docs && bun run build`
Expected: Build succeeds with no errors

- [ ] **Step 6: Commit**

```bash
git add docs/package.json docs/bun.lockb docs/astro.config.mjs docs/src/content.config.ts
git commit -m "feat: integrate starlight-auto-sidebar plugin"
```

---

## Chunk 7: Skill and final validation

### Task 11: Update chapter-split skill

**Files:**
- Modify: `.claude/skills/chapter-split/SKILL.md`

- [ ] **Step 1: Add multi-source detection to skill**

In `.claude/skills/chapter-split/SKILL.md`, update Step 1 (Resolve Scope & Preconditions) to add:

```markdown
#### Multi-Source Detection

Scan `data/markdown/*_pages.md`:
- **1 file** → single PDF flow (existing logic, produce `chapters.json` directly)
- **Multiple files** → multi PDF flow:
  1. Ask user for slug, title, order per PDF
  2. For each PDF, dispatch TOC planner + wordcount planner independently
  3. Each planner outputs `chapters_<name>.json`
  4. Run `uv run python scripts/merge_multi.py chapters_*.json` to produce `chapters.json`
  5. Continue with split execution as normal
```

- [ ] **Step 2: Update Step 5 to mention `_meta.yml`**

Add note that `split_chapters.py` now generates `_meta.yml` files for group nodes, and that `starlight-auto-sidebar` plugin handles sidebar rendering for nested structures.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/chapter-split/SKILL.md
git commit -m "feat: update chapter-split skill for multi-source flow"
```

---

### Task 12: Run full test suite and validate

**Files:** (none — validation only)

- [ ] **Step 1: Run all tests**

Run: `cd D:/Code/trpg-doc/game-doc-template && uv run pytest scripts/tests/ -v`
Expected: All PASS

- [ ] **Step 2: Run legacy tests**

Run: `cd D:/Code/trpg-doc/game-doc-template && uv run pytest tests/ -v`
Expected: All PASS

- [ ] **Step 3: Verify site builds**

Run: `cd D:/Code/trpg-doc/game-doc-template/docs && bun run build`
Expected: Build succeeds

- [ ] **Step 4: Final commit**

```bash
git commit --allow-empty -m "chore: validate multi-source chapter split implementation"
```
