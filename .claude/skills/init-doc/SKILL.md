---
name: init-doc
description: Use when initializing a translation project from extraction through glossary, chapter mapping, and progress tracking.
user-invocable: true
disable-model-invocation: true
---

# Initialize Document Translation

## Overview

Initialize translation baseline from PDF extraction to chaptered docs, style decisions, glossary, and progress tracker.

**Core principle:** Build a deterministic, verifiable baseline before any large-scale translation.

## Interaction Rules

- All user interaction must be Traditional Chinese (zh-TW).
- AskUserQuestion prompts must be Traditional Chinese.
- Do not use Simplified Chinese in user-facing text.

## The Process

### Step 1: Cleanup and Source Validation

Run cleanup:

```bash
uv run python scripts/clean_sample_data.py --yes
```

Then resolve source PDF from `$ARGUMENTS` or ask user in Traditional Chinese. Ensure source is under `data/pdfs/`.

Before extraction, ask user in Traditional Chinese whether to preserve PDF images in the generated docs:

```text
是否要保留 PDF 內的圖片，並在切分後的 Markdown 文件中保留對應圖片連結？
```

Record this decision as `preserve_images: true/false` for the rest of the run.

### Step 2: Create TodoWrite

Create items for:
- extraction
- formatting decisions
- image retention decision
- image and theme setup
- terminology bootstrap
- chapter mapping
- progress tracker creation
- final handoff gate

### Step 3: Extract and Validate Raw Outputs

Run:

```bash
uv run python scripts/extract_pdf.py <pdf_path> --include-images
```

If `preserve_images` is `false`, run instead:

```bash
uv run python scripts/extract_pdf.py <pdf_path> --no-include-images
```

Validate outputs:
- `data/markdown/<name>.md`
- `data/markdown/<name>_pages.md`
- `data/markdown/images/<name>/`（only when `preserve_images = true`）

### Step 4: Cropping Review and Optional Split

Review readability and completeness.
If needed, split large source into parts and re-extract until clean.

### Step 5: Confirm Document Formatting Decisions

Summarize content to user in Traditional Chinese:

```text
書本內容概覽：
- 主要內容類型：[規則說明、範例場景、角色選項...]
- 特殊結構：[大量表格、骰表、設計者備註...]
- 建議可使用的格式化元件：[...]
```

Collect formatting choices (Traditional Chinese):
- aside mapping (`note/tip/caution/danger`)
- card/tabs usage
- table/dice-table conventions

Persist to `style-decisions.json.document_format`.

### Step 6: Select Images, Theme, and Homepage Content

1. If `preserve_images = true`, ask user to assign extracted images for hero/background/og.
2. If `preserve_images = true`, copy and resize where needed.
3. If `preserve_images = false`, skip extracted image assignment and continue with theme-only setup.
4. Ask theme decisions in Traditional Chinese (mode/overlay/palette).
5. Update `docs/src/styles/custom.css` and persist style decisions.
6. Persist image retention decision to `style-decisions.json.images.preserve_images`.
7. Ask for site meta in Traditional Chinese (all four fields):
   - **網站標題**（`site.title`）：首頁 `<title>` 及 frontmatter title，例：「Rapscallion 遊戲規則」
   - **首頁描述**（`site.description`）：SEO description，一句話
   - **副標語**（`site.tagline`）：hero 區塊顯示的一行短語
   - **內容簡介**（`site.intro`）：首頁「內容簡介」段落，一到兩句

   Persist to `style-decisions.json`:

   ```json
   {
     "site": {
       "title": "<USER_INPUT>",
       "description": "<USER_INPUT>",
       "tagline": "<USER_INPUT>",
       "intro": "<USER_INPUT>"
     }
   }
   ```

9. Ask for copyright and credits in Traditional Chinese:
   - Copyright notice text（例：`© 2024 Author Name. All rights reserved.`）
   - Credits entries as role → name pairs（例：原作者、翻譯、美術設計等）
   - Whether to show each section on the homepage
10. Persist to `style-decisions.json`:

```json
{
  "images": {
    "preserve_images": true
  },
  "copyright": {
    "text": "<USER_INPUT>",
    "show_on_homepage": true
  },
  "credits": {
    "entries": [
      { "role": "原作者", "name": "..." },
      { "role": "翻譯", "name": "..." }
    ],
    "show_on_homepage": true
  }
}
```

`generate_nav.py` will render these as **## 版權宣告** and **## 製作名單** sections on the homepage. If neither is provided, a generic fallback disclaimer is used.

### Step 7: Build Terminology Baseline

Invoke `term-decision` skill for terminology bootstrap instead of duplicating the workflow here.

Required handoff to `term-decision`:
1. Source is the extracted markdown from this init run.
2. First inspect high-signal terminology sources in the original book:
   - source glossary / terminology pages
   - index pages
   - appendix term lists
   - playbook / move summary tables that clearly define recurring mechanics terms
3. Complete one first-pass terminology bootstrap from those sections:
   - prefill obvious term translations into `glossary.json`
   - keep wording consistent with `style-decisions.json`
   - ask the user only about uncertain, culturally nuanced, or mechanics-ambiguous terms
4. After that first pass, generate and verify the remaining candidates with:

```bash
uv run python scripts/term_generate.py --min-frequency 2
uv run python scripts/term_cal_batch.py
uv run python scripts/validate_glossary.py
uv run python scripts/term_read.py --fail-on-missing --fail-on-forbidden
```

`init-doc` must not continue to chapter split until the `term-decision` handoff completes cleanly.

### Step 8: Multi-Agent Chapter Split and Navigation

Run chapter split planning with two focused agents.
Pipeline: `toc-planner -> wordcount-planner`.

Split policy for both planners:
- Prefer semantic chapter/file boundaries from the source TOC or clear in-text subheadings.
- Do not break one long chapter into generic numbered parts like `1`, `2`, `3`, `part-1`, or `一`, `二`, `三` unless those are the actual source headings.
- When a long chapter needs internal subdivision, keep the top-level section slug stable and use nested file paths inside `files` (for example `equipment/weapons`) so the output can use subdirectories.
- If no trustworthy subordinate headings exist, keep the chapter as one file and surface the risk instead of inventing arbitrary numbered splits.

1. Create draft config path:
   - `.claude/skills/init-doc/.state/chapters.draft.json`
2. Dispatch toc planner using `./split-planner-prompt.md` to generate TOC-aligned draft `chapters_config`.
3. Dispatch wordcount planner using `./split-wordcount-planner-prompt.md` to rebalance file granularity based on word count while preserving TOC order.
4. If wordcount planner reports unresolved critical issues, stop and ask user in Traditional Chinese before writing `chapters.json`.
5. Before writing `chapters.json`, set image split policy:
   - if `preserve_images = true`, include:

```json
{
  "images": {
    "enabled": true,
    "assets_dir": "docs/src/assets/extracted",
    "repeat_file_size_threshold": 5
  }
}
```

   - if `preserve_images = false`, include:

```json
{
  "images": {
    "enabled": false
  }
}
```

6. Write final config to `chapters.json` (no user confirmation for split decision), then run split and generate navigation:

```bash
uv run python scripts/split_chapters.py
uv run python scripts/generate_nav.py
```

`generate_nav.py` reads `chapters.json` and:
- generates `docs/src/content/docs/index.mdx` (homepage with dynamic CardGrid)
- updates `docs/astro.config.mjs` sidebar to match chapter slugs

7. Finalize split outputs and `chapters.json` mapping.

### Step 9: Create Translation Progress Tracker

Create `data/translation-progress.json` from `chapters.json`:

```bash
uv run python scripts/init_create_progress.py --force
```

Tracker contract:
- chapter ids derived from output file paths
- source page ranges mapped from chapter config
- initial status `not_started`
- `_meta` fields (`updated`, `total_chapters`, `completed`)

### Step 10: Final Gate and Handoff (Fail-Closed)

Run one-shot handoff gate:

```bash
uv run python scripts/init_handoff_gate.py
```

If any gate fails, stop and fix before completion.

## Prompt Templates

Prompt templates are colocated with this skill:
- `./split-planner-prompt.md`
- `./split-wordcount-planner-prompt.md`

## Dispatch Templates

Use these fixed dispatch patterns:

### toc-planner

```text
Task tool (general-purpose):
  description: "Draft TOC-based split config for <SOURCE_PAGES_FILE>"
  prompt template: ./split-planner-prompt.md
  placeholders:
    <SOURCE_PAGES_FILE>, <DRAFT_CONFIG_PATH>
```

### wordcount-planner

```text
Task tool (general-purpose):
  description: "Rebalance split config by wordcount for <SOURCE_PAGES_FILE>"
  prompt template: ./split-wordcount-planner-prompt.md
  placeholders:
    <SOURCE_PAGES_FILE>, <DRAFT_CONFIG_PATH>
```

## Progress Sync Contract (Required)

1. Keep TodoWrite updated at every step.
2. Mark blockers immediately and include failing command/context.
3. Close TodoWrite only after final gate passes.

## When to Stop and Ask for Help

Stop when:
- source extraction repeatedly fails
- chapter split planners cannot produce a usable config
- glossary validation cannot be resolved safely
- docs build fails with unclear root cause

## When to Revisit Earlier Steps

Return to earlier steps when:
- user changes formatting/theme policy
- user changes proper noun strategy
- source markdown changes enough to invalidate page mapping

## Red Flags

Never:
- continue after failed validation gates
- ignore TOC order when applying wordcount balancing
- skip user confirmation for formatting/proper noun policy
- leave progress tracker uninitialized at handoff

## Next Step

Continue with `/translate` or `/super-translate`.

## Example Usage

```text
/init-doc
/init-doc data/pdfs/rulebook.pdf
```
