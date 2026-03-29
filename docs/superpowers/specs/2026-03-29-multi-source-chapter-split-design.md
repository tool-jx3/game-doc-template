# Multi-Source Chapter Split Design

## Summary

Extend the chapter-split pipeline to support multiple PDF sources within a single documentation site, while maintaining full backward compatibility with existing single-PDF projects.

## Problem

Currently, the entire pipeline (init-doc -> chapter-split -> translate) assumes one PDF = one project. Games with multiple rulebooks (core rules + expansion + GM guide) require separate projects and cannot share a unified documentation site, glossary, or navigation.

## Approach

Hybrid of minimal schema extension + merge orchestrator:

1. Each PDF gets its own `chapters_<name>.json` (planner works as-is per PDF)
2. New `merge_multi.py` combines them into a single `chapters.json`
3. `chapters.json` format is backward-compatible with new optional chapter-level fields
4. `split_chapters.py` and `generate_nav.py` work on the merged `chapters.json`
5. `starlight-auto-sidebar` plugin + `_meta.yml` files handle deep sidebar nesting

## Design Decisions

| Decision | Choice | Reason |
|----------|--------|--------|
| Page number scope | Local per source | Each PDF has its own page 1; chapter-level `source` field disambiguates |
| Sidebar grouping | By PDF | Each PDF becomes a top-level sidebar group |
| Config source of truth | Individual `chapters_<name>.json` | Edits always in per-PDF files; `chapters.json` is a derived artifact from merge |
| Planner strategy | Independent per PDF | Each PDF runs its own TOC + wordcount planner; results merged after |
| Global vs per-chapter config | Global defaults, chapter-level overrides | `source`, `clean_patterns`, `images` can be overridden per chapter |
| Sidebar technology | `starlight-auto-sidebar` + `_meta.yml` | Handles deep nesting without manual `astro.config.mjs` sidebar entries |
| Existing sidebar codepath | Preserved | `generate_sidebar_entries()` and `update_astro_sidebar()` kept for non-plugin fallback |

---

## 1. `chapters.json` Format Extension

### Single PDF (unchanged)

```json
{
  "source": "data/markdown/core-rules_pages.md",
  "output_dir": "docs/src/content/docs",
  "mode": "bilingual",
  "clean_patterns": ["\\[footer\\]"],
  "images": { "enabled": false },
  "chapters": {
    "combat": {
      "title": "Combat",
      "order": 1,
      "files": {
        "actions": { "title": "Actions", "pages": [5, 7], "order": 0 }
      }
    }
  }
}
```

### Multi PDF (after merge)

```json
{
  "output_dir": "docs/src/content/docs",
  "mode": "bilingual",
  "images": { "enabled": false },
  "chapters": {
    "core-rules": {
      "source": "data/markdown/core-rules_pages.md",
      "title": "Core Rules",
      "order": 1,
      "clean_patterns": ["\\[footer\\]"],
      "files": {
        "index": { "title": "Overview", "pages": [1, 4], "order": 0 },
        "combat": {
          "title": "Combat",
          "order": 1,
          "files": {
            "actions": { "title": "Actions", "pages": [5, 7], "order": 0 },
            "damage": { "title": "Damage", "pages": [8, 10], "order": 1 }
          }
        }
      }
    },
    "expansion": {
      "source": "data/markdown/expansion_pages.md",
      "title": "Expansion",
      "order": 2,
      "images": { "enabled": true, "assets_dir": "docs/src/assets/extracted" },
      "files": {
        "new-classes": { "title": "New Classes", "pages": [1, 8], "order": 0 }
      }
    }
  }
}
```

### Config Resolution Rules

| Field | Top-level | Chapter-level | Priority |
|-------|-----------|---------------|----------|
| `source` | Default (single PDF) | Override (multi PDF) | chapter > top |
| `clean_patterns` | Default | Override | chapter > top |
| `images` | Default | Override | chapter > top |
| `output_dir` | Global | -- | Top-level only |
| `mode` | Global | -- | Top-level only |

### Node Type Detection

- Has `pages` -> leaf node (produces .md file)
- Has `files` -> group node (produces subdirectory + `_meta.yml`)
- Neither -> validation error

### File Path Format: Recursive Only

The existing codebase supports flat slash-separated paths in `files` (e.g., `"combat/damage": { "pages": [11, 16] }`). This design introduces a recursive nested format where group nodes contain their own `files` dict.

**Decision: only the recursive nested format is supported for multi-source configs.** The rationale:

- Flat slash paths cannot carry group-level metadata (`title`, `order`) needed for `_meta.yml` generation
- `merge_multi.py` converts planner output (which may use flat paths) into recursive format during merge
- Single-PDF configs continue to support flat slash paths for backward compatibility — `split_chapters.py` normalizes flat paths into nested structure on the fly before processing

Normalization logic in `split_chapters.py`:

```python
def normalize_files(files: dict) -> dict:
    """Convert flat slash-path entries into nested recursive structure."""
    result = {}
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

**Limitation:** Synthetic group nodes created by normalization have `title` set to the raw slug and no `order` field. The resulting `_meta.yml` will have `label: combat` (raw slug) and no ordering. Users who need controlled ordering and human-readable labels should switch to the recursive format explicitly. This is acceptable because normalization is a backward-compat safety net, not the primary authoring path.

---

## 2. `merge_multi.py` Script

### Per-PDF Config Format

Each `chapters_<name>.json` uses the existing single-PDF format plus top-level `slug`, `title`, `order`:

```json
{
  "source": "data/markdown/core-rules_pages.md",
  "slug": "core-rules",
  "title": "Core Rules",
  "order": 1,
  "clean_patterns": ["\\[footer\\]"],
  "chapters": {
    "combat": {
      "title": "Combat",
      "order": 1,
      "files": { "actions": { "title": "Actions", "pages": [5, 7], "order": 0 } }
    }
  }
}
```

### Merge Logic

1. Read each input file
2. For each input:
   - Use `slug` as the merged chapter key
   - Convert original `chapters` to `files` (demote one level)
   - Inject `source` into chapter level
   - Move `clean_patterns`, `images` etc. to chapter level
3. Inherit `output_dir`, `mode` from first input (or CLI `--mode`, `--output-dir` overrides)
4. Validate: no duplicate slugs (hard error), duplicate orders (warning only — Starlight resolves ties alphabetically)
5. Warn if any top-level chapter lacks an `index` leaf node (needed for homepage links)
6. Write `chapters.json`

**Note:** On Windows, shell glob expansion may not work. The script uses `glob.glob()` internally to expand patterns, so both `chapters_*.json` and explicit file lists work.

### CLI

```bash
# Basic
uv run python scripts/merge_multi.py chapters_*.json

# Specify output
uv run python scripts/merge_multi.py chapters_*.json -o chapters.json

# Override globals
uv run python scripts/merge_multi.py chapters_*.json --mode bilingual
```

---

## 3. `split_chapters.py` Changes

### Modified Flow

```
Read chapters.json
  -> For each chapter:
    -> Resolve source (chapter.source ?? top-level source)
    -> Resolve clean_patterns, images (same fallback)
    -> Load source page dict (cached per source path)
    -> Recursively walk files:
      -> Group node -> mkdir + write _meta.yml
      -> Leaf node -> extract pages, clean, write .md
```

### Structural Refactor Note

The current `split_chapters()` function loads the source once at the top and iterates chapters. This must be refactored to a "iterate chapters, load per-chapter (with cache)" pattern. The main loop changes from:

```
load source -> load manifest -> for each chapter: process files
```

to:

```
for each chapter:
  resolve config (source, images, clean_patterns)
  load source pages (cached)
  load image manifest (cached)
  process files recursively
```

### Source Cache

```python
_page_cache: dict[str, dict[int, str]] = {}

def load_pages(source_path: str) -> dict[int, str]:
    if source_path not in _page_cache:
        _page_cache[source_path] = parse_pages(source_path)
    return _page_cache[source_path]
```

### Recursive Files Processing

```python
def process_files(files: dict, output_dir: Path, pages: dict, config: ChapterConfig):
    for key, entry in files.items():
        if "pages" in entry:
            write_leaf(key, entry, output_dir, pages, config)
        elif "files" in entry:
            sub_dir = output_dir / key
            sub_dir.mkdir(parents=True, exist_ok=True)
            write_meta_yml(sub_dir, entry)
            process_files(entry["files"], sub_dir, pages, config)
        else:
            raise ValueError(f"Invalid entry '{key}': must have 'pages' or 'files'")
```

### Config Fallback

```python
def resolve_config(chapter_key: str, chapter: dict, top_level: dict) -> ChapterConfig:
    source = chapter.get("source", top_level.get("source"))
    if not source:
        raise ValueError(f"Chapter '{chapter_key}' has no 'source' and no top-level 'source' defined")
    return ChapterConfig(
        source=source,
        clean_patterns=chapter.get("clean_patterns", top_level.get("clean_patterns", [])),
        images=chapter.get("images", top_level.get("images", {})),
    )
```

### Image Manifest Resolution (Multi-Source)

Currently `load_image_manifest()` is called once with the top-level `source`. In multi-source mode, each chapter may reference a different `_pages.md` with its own image manifest.

**Solution:** Cache image manifests per source, mirroring the page cache pattern:

```python
_manifest_cache: dict[str, dict] = {}

def load_manifest(source_path: str, images_config: dict) -> dict:
    if source_path not in _manifest_cache:
        _manifest_cache[source_path] = _load_image_manifest(source_path, images_config)
    return _manifest_cache[source_path]
```

The `source_slug` for `copy_image_to_assets` is derived from the chapter-level `source` (via `infer_source_stem()`), not the top-level source. This ensures images from different PDFs land in separate asset subdirectories (e.g., `docs/src/assets/extracted/core-rules/`, `docs/src/assets/extracted/expansion/`).

### `_meta.yml` Generation

Group nodes produce `_meta.yml` (compatible with `starlight-auto-sidebar` >=0.x) in their directory:

```yaml
label: Combat
order: 1
```

Mapping: `title` -> `label`, `order` -> `order`.

Supported `_meta.yml` fields from the plugin: `label`, `order`, `badge`, `collapsed`, `sort`, `hidden`, `depth`, `cascade`. This design only generates `label` and `order`; users can manually add other fields.

### Output Structure Example

Non-bilingual:
```
docs/src/content/docs/
  core-rules/
    _meta.yml          <- label: Core Rules, order: 1
    index.md
    combat/
      _meta.yml        <- label: Combat, order: 1
      actions.md
      damage.md
  expansion/
    _meta.yml          <- label: Expansion, order: 2
    new-classes.md
```

Bilingual mode (`mode: "bilingual"`):
```
docs/src/content/docs/
  bilingual/
    _meta.yml          <- label: (site title), order: 0
    core-rules/
      _meta.yml        <- label: Core Rules, order: 1
      index.md
      combat/
        _meta.yml      <- label: Combat, order: 1
        actions.md
        damage.md
    expansion/
      _meta.yml        <- label: Expansion, order: 2
      new-classes.md
```

The `bilingual/` wrapper directory also gets a `_meta.yml`. The `split_chapters.py` bilingual path logic (appending `/bilingual/` to output_dir) is unchanged; `_meta.yml` generation simply follows wherever the output directory is.

---

## 4. `generate_nav.py` Changes

### Scope

| Function | Action |
|----------|--------|
| `generate_sidebar_entries()` | **No change** — only works correctly for flat (single-PDF) configs. For multi-source nested configs, sidebar is handled by `starlight-auto-sidebar` + `_meta.yml`. |
| `update_astro_sidebar()` | **No change** — same limitation as above. |
| `generate_index()` | Small change: recursive description + safe link targets |

### Known Limitation

`generate_sidebar_entries()` and `update_astro_sidebar()` only work for single-PDF flat configs. Multi-source projects **must** use `starlight-auto-sidebar` for correct sidebar rendering. This is acceptable because multi-source is a new feature that inherently requires the plugin.

### `first_file_description()` Recursive Adaptation

Current: only checks one level of `files`.
Changed: recursively descends group nodes to find first leaf with a description.

### `generate_index()` Link Safety

For homepage `LinkCard` entries, the `href` must point to a resolvable page. In multi-source configs, a top-level chapter (e.g., `core-rules`) is a group node with no guaranteed `index.md`.

**Rule:** Multi-source top-level chapters should always include an `index` leaf node with `"order": 0`. The merge script validates this and emits a warning if missing. `generate_index()` resolves the link target to the first leaf node when no `index` exists at the group root:

```python
def first_leaf_path(files: dict, path_prefix: str) -> str:
    """Recursively find the path to the first leaf node (by order)."""
    for key, entry in sorted(files.items(), key=lambda x: x[1].get("order", 9999)):
        if "pages" in entry:
            return f"{path_prefix}/{key}"
        elif "files" in entry:
            result = first_leaf_path(entry["files"], f"{path_prefix}/{key}")
            if result:
                return result
    return path_prefix  # fallback to group path
```

---

## 5. `starlight-auto-sidebar` Integration

### Install

Requires `starlight-auto-sidebar` compatible with Starlight v1+ (Astro Content Layer API). Verify version compatibility before installing.

```bash
cd docs && bun add starlight-auto-sidebar
```

### `docs/astro.config.mjs`

Add plugin:

```js
import starlightAutoSidebar from 'starlight-auto-sidebar'

export default defineConfig({
  integrations: [
    starlight({
      plugins: [starlightAutoSidebar()],
    }),
  ],
})
```

### `docs/src/content.config.ts`

Add autoSidebar collection:

```typescript
import { defineCollection } from 'astro:content';
import { docsLoader, i18nLoader } from '@astrojs/starlight/loaders';
import { docsSchema, i18nSchema } from '@astrojs/starlight/schema';
import { autoSidebarLoader } from 'starlight-auto-sidebar/loader';
import { autoSidebarSchema } from 'starlight-auto-sidebar/schema';

export const collections = {
    docs: defineCollection({ loader: docsLoader(), schema: docsSchema() }),
    i18n: defineCollection({ loader: i18nLoader(), schema: i18nSchema() }),
    autoSidebar: defineCollection({
        loader: autoSidebarLoader(),
        schema: autoSidebarSchema(),
    }),
};
```

---

## 6. Progress Tracking Changes

### `init_create_progress.py`

Recursive traversal of nested files. Only leaf nodes (with `pages`) create progress records.

New `source` field per record. **ID format uses the existing path-based convention** (matching current `progress_edit.py --file` expectations) to avoid breaking changes:

```json
{
  "id": "docs-src-content-docs-core-rules-combat-actions",
  "title": "Actions",
  "file": "docs/src/content/docs/core-rules/combat/actions.md",
  "source": "data/markdown/core-rules_pages.md",
  "source_pages": "5-7",
  "status": "not_started",
  "notes": ""
}
```

### Recursive `iter_chapter_files()`

```python
def iter_chapter_files(chapter_map: dict, output_dir: str, mode: str):
    """Recursively yield leaf nodes with accumulated path segments."""
    base = f"{output_dir}/bilingual" if mode == "bilingual" else output_dir
    for section_slug, section in chapter_map.items():
        source = section.get("source", "")
        yield from _walk_files(
            section.get("files", {}),
            path_prefix=f"{base}/{section_slug}",
            source=source,
        )

def _walk_files(files: dict, path_prefix: str, source: str):
    for key, entry in files.items():
        current_path = f"{path_prefix}/{key}"
        if "pages" in entry:
            yield {
                "file": f"{current_path}.md",
                "title": entry.get("title", key),
                "source": source,
                "pages": entry["pages"],
            }
        elif "files" in entry:
            yield from _walk_files(entry["files"], current_path, source)
```

### `progress_read.py`

New `--source` filter flag with partial matching:

```bash
uv run python scripts/progress_read.py --source core-rules
```

---

## 7. Chapter-Split Skill Flow

### Detection

Scan `data/markdown/*_pages.md`:
- 1 file -> single PDF flow (existing logic, produces `chapters.json` directly)
- Multiple files -> multi PDF flow

### Multi PDF Flow

```
Detect multiple _pages.md files
  -> Ask user for slug, title, order per PDF
  -> For each PDF:
    -> Dispatch TOC planner (with slug, title, order params)
    -> Dispatch wordcount planner
    -> Output chapters_<name>.json
  -> merge_multi.py -> chapters.json
  -> split_chapters.py
  -> generate_nav.py
```

### Planner Prompt Additions

| Parameter | Purpose |
|-----------|---------|
| `slug` | Top-level chapter key for this PDF in merged config |
| `title` | Display name for this PDF's section |
| `order` | Sort position in site sidebar |

Planner internal logic unchanged -- still reads one `_pages.md`, still produces chapter structure. Planner output may use flat slash-path format; `merge_multi.py` converts to recursive format during merge. For single-PDF flow, `split_chapters.py` normalizes flat paths automatically via `normalize_files()`.

---

## 8. File Change Summary

### New Files

| File | Purpose |
|------|---------|
| `scripts/merge_multi.py` | Merge multiple `chapters_<name>.json` into `chapters.json` |

### Modified Files

| File | Change | Scope |
|------|--------|-------|
| `scripts/split_chapters.py` | Source/config fallback + recursive files + `_meta.yml` generation | Medium |
| `scripts/generate_nav.py` | `first_file_description()` recursive adaptation | Small |
| `scripts/init_create_progress.py` | Recursive traversal + source field | Small |
| `scripts/progress_read.py` | `--source` filter | Small |
| `.claude/skills/chapter-split/SKILL.md` | Multi `_pages.md` detection + per-PDF planner flow | Medium |
| `docs/astro.config.mjs` | Add `starlight-auto-sidebar` plugin | Small |
| `docs/src/content.config.ts` | Add autoSidebar collection | Small |
| `docs/package.json` | New dependency | Small |

### Unchanged Files

| File | Reason |
|------|--------|
| `scripts/extract_pdf.py` | Stays single-PDF extraction |
| `generate_sidebar_entries()` | Preserved for non-plugin fallback |
| `update_astro_sidebar()` | Preserved for non-plugin fallback |
| Planner internal logic | Unchanged; only receives extra slug/title/order params |

---

## 9. Backward Compatibility

| Scenario | Expected Behavior |
|----------|-------------------|
| Old `chapters.json` (single source, flat files) | Unchanged; all fallbacks use top-level values |
| New single-PDF project | Skill uses existing single PDF flow |
| No auto-sidebar plugin installed | `_meta.yml` files exist but ignored; sidebar still generated by `generate_nav.py` |
| Manual edit of `chapters.json` (no merge) | Works normally; doesn't depend on `chapters_*.json` existing |
