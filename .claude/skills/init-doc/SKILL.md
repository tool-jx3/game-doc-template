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

### Step 2: Create TodoWrite

Create items for:
- extraction
- formatting decisions
- image and theme setup
- terminology bootstrap
- chapter mapping
- progress tracker creation
- final handoff gate

### Step 3: Extract and Validate Raw Outputs

Run:

```bash
uv run python scripts/extract_pdf.py <pdf_path>
```

Validate outputs:
- `data/markdown/<name>.md`
- `data/markdown/<name>_pages.md`
- `data/markdown/images/<name>/`

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

### Step 6: Select Images and Theme

1. Ask user to assign extracted images for hero/background/og.
2. Copy and resize where needed.
3. Ask theme decisions in Traditional Chinese (mode/overlay/palette).
4. Update `docs/src/styles/custom.css` and persist style decisions.

### Step 7: Build Terminology Baseline

1. Generate candidates:

```bash
uv run python scripts/term_generate.py --min-frequency 2
```

2. Ask user to confirm key terms and proper noun policy.
3. Update glossary safely:

```bash
uv run python scripts/term_edit.py --term "<TERM>" --cal
uv run python scripts/term_edit.py --term "<TERM>" --set-zh "<ZH>" --status approved --mark-term
uv run python scripts/validate_glossary.py
uv run python scripts/term_read.py --fail-on-missing --fail-on-forbidden
```

### Step 8: Split Chapters and Build Navigation

1. Initial split:

```bash
uv run python scripts/split_chapters.py
```

2. Generate/update homepage index from style decisions.
3. Ask split confirmation in Traditional Chinese:

```text
找到以下章節結構：
1. [章節名稱] - 約 XXX 字
2. [章節名稱] - 約 XXX 字
...
建議拆分為獨立檔案嗎？
```

4. Finalize split and `chapters.json` mapping.

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

## Progress Sync Contract (Required)

1. Keep TodoWrite updated at every step.
2. Mark blockers immediately and include failing command/context.
3. Close TodoWrite only after final gate passes.

## When to Stop and Ask for Help

Stop when:
- source extraction repeatedly fails
- chapter boundaries are ambiguous and decision-sensitive
- glossary validation cannot be resolved safely
- docs build fails with unclear root cause

## When to Revisit Earlier Steps

Return to earlier steps when:
- user changes formatting/theme policy
- user changes proper noun strategy
- split strategy changes after review

## Red Flags

Never:
- continue after failed validation gates
- skip user confirmation for formatting/proper noun policy
- leave progress tracker uninitialized at handoff

## Next Step

Continue with `/translate` or `/super-translate`.

## Example Usage

```text
/init-doc
/init-doc data/pdfs/rulebook.pdf
```
