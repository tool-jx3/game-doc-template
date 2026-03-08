---
name: super-translate
description: Use when high-quality translation is needed with multi-agent review loops and strict progress tracking.
user-invocable: true
disable-model-invocation: true
---

# Super Translate

## Overview

Run iterative translation with a single reviewer loop and one Git checkpoint commit per completed batch.
Pipeline: `translator -> reviewer -> refiner` (max 2 iterations).

**Core principle:** Source-fidelity and quality checked in one pass; no overwrite unless reviewer passes.

## The Process

### Step 1: Resolve Scope and Preconditions

1. Verify required files exist:
   - `data/translation-progress.json`
   - `glossary.json`
   - `style-decisions.json`
   If any are missing, stop and ask user to initialize first.

2. Resolve target files:
   - If `$ARGUMENTS` specifies concrete file paths or a scoped pattern → use those directly.
   - Otherwise (no args, `all`, or `next`) → **auto-select from `translation-progress.json`**:
     1. **Resume first**: collect all files with status `in_progress` (highest priority).
     2. **Then queue**: collect files with status `not_started`, in chapter order.
     3. Default batch size is 3 files. Display selected files in Traditional Chinese before proceeding:
        ```
        翻譯進度：已完成 X / Y 個章節
        本批次自動選取以下 N 個檔案：
        - [in_progress 繼續] <file>
        - [not_started 新增] <file>
        …
        是否繼續？或請指定其他範圍。
        ```
     4. Wait for user confirmation or override.

### Step 2: Create TodoWrite Before Dispatch

Create TodoWrite with:
- one parent item per target file
- sub-steps: draft, review, refine (if needed), writeback
- batch checkpoint and final verification items

### Step 3: Terminology Preflight (Fail-Closed)

```bash
uv run python scripts/validate_glossary.py
uv run python scripts/term_read.py --fail-on-missing --fail-on-forbidden
```

If preflight fails, stop and fix terminology first.

### Step 4: Resolve Translation Mode

Read `style-decisions.json.translation_mode.mode`.
If missing, ask user in Traditional Chinese:
- **完整翻譯**：完整翻譯所有內容，保留原始結構與細節
- **摘要翻譯**：以精簡方式翻譯重點規則，省略範例與冗長說明

Persist mode before dispatch.

### Step 5: Prepare Draft Paths

For each target file, obtain its draft path (this also creates the directory):

```bash
uv run python scripts/draft.py --skill super-translate path <TARGET_FILE>
```

Use the printed path as `<DRAFT_FILE>` for that file.

### Step 6: Execute Per Batch (Default First 3 Files)

**Pre-read shared context once per batch (before the file loop):**

Read and hold in memory:
- `GLOSSARY_CONTENT` = full content of `glossary.json`
- `STYLE_CONTENT` = full content of `style-decisions.json`

For each target file:
1. mark TodoWrite item `in_progress`
2. update `translation-progress.json` status to `in_progress`
3. Read `SOURCE_CONTENT` = full content of `<TARGET_FILE>`
4. Resolve `<DRAFT_FILE>`:
   ```bash
   DRAFT_FILE=$(uv run python scripts/draft.py --skill super-translate path <TARGET_FILE>)
   ```
5. dispatch translator using `./translator-prompt.md`, inline:
   - `<SOURCE_CONTENT>` = content of target file
   - `<GLOSSARY_CONTENT>` = glossary.json content
   - `<STYLE_CONTENT>` = style-decisions.json content
   - `<DRAFT_FILE>` = `$DRAFT_FILE` (from above)
   - The stub draft already contains `_draft_source` in its frontmatter; translator must preserve it in the output
   - `frontmatter.title` is the page title; translator must not restate it anywhere in the body as a heading of any level (`#`, `##`, etc.)
   - If the opening overview/introduction block has no heading in the source, translator must keep it as plain body content and must not invent a `概覽` heading
   - If source content contains image markdown in the middle of prose flow, preserve the exact image link and move it into the middle of the translated paragraph without splitting that paragraph into separate blocks
5. After translator returns, read `DRAFT_CONTENT` = full content of `<DRAFT_FILE>`
6. dispatch reviewer using `./reviewer-prompt.md`, inline:
   - `<SOURCE_CONTENT>`, `<DRAFT_CONTENT>`, `<GLOSSARY_CONTENT>`, `<STYLE_CONTENT>`
   - Reviewer must fail the draft if it adds any heading that restates `frontmatter.title`, or invents an overview heading that is not present in the source
   - Reviewer must fail the draft if image links are dropped, altered, or break one paragraph into multiple blocks when they should stay inside the paragraph flow
7. if fail → dispatch refiner using `./refiner-prompt.md`, inline:
   - `<SOURCE_CONTENT>`, `<DRAFT_CONTENT>`, `<REVIEW_JSON>`, `<GLOSSARY_CONTENT>`, `<STYLE_CONTENT>`
   - Refiner must remove any added heading that restates `frontmatter.title`, and remove any invented overview heading while preserving the paragraph content below it
   - Refiner must restore the exact image link and place it back into the paragraph body without truncating the surrounding text
   → re-read `DRAFT_CONTENT` from updated draft → re-run reviewer (inline same context)
8. cap at 2 iterations total

If 2 iterations still have critical issues, ask user in Traditional Chinese:
- **保留目前草稿，不覆蓋原始檔，稍後手動修正後再續跑**
- **停止此檔案，先處理術語或規則歧義再繼續**

Unknown term handling:

```bash
uv run python scripts/term_edit.py --term "<TERM>" --set-zh "<ZH>" --status approved --mark-term
uv run python scripts/validate_glossary.py
uv run python scripts/term_read.py --fail-on-missing --fail-on-forbidden
```

Then rerun the file loop.

### Step 7: Controlled Writeback

Only if reviewer passes:
- ```bash
  uv run python scripts/draft.py --skill super-translate writeback <TARGET_FILE>
  ```
- **Immediately** update `translation-progress.json`:
  - Set file status to `completed`
  - Recalculate `_meta.completed` (count of completed entries)
  - Update `_meta.updated` to current timestamp
- close TodoWrite file item

If blocked/failed:
- keep source unchanged
- keep `translation-progress.json` status as `in_progress`
- mark TodoWrite as blocked

### Step 8: Batch Checkpoint Report

After each batch:
- report completed/blocked/failed files
- report iteration counts
- report updated progress: `已完成 X / Y 個章節`
- run `git status --short` and verify the batch scope before staging
- stage **only** files touched by this batch:
  - completed translated source files from this batch
  - `data/translation-progress.json`
  - `glossary.json` if changed in this batch
  - `style-decisions.json` if changed in this batch
- create exactly one checkpoint commit for the batch:

```bash
git commit -m "progress: X/Y"
```

- keep the commit message short and progress-only; do not include filenames or explanations
- never stage or commit unrelated user changes
- if no file reached `completed` in this batch, skip the commit
- confirm TodoWrite + progress tracker sync
- if remaining `not_started` or `in_progress` files exist: ask user whether to continue with next batch
  - if yes: re-run Step 1 auto-select (resume `in_progress` first, then next `not_started` files in chapter order) → return to Step 6
  - if no: proceed to Step 9 Final Verification

### Step 9: Final Verification

```bash
uv run python scripts/validate_glossary.py
uv run python scripts/term_read.py --fail-on-missing --fail-on-forbidden
```

Invoke `check-consistency` skill to validate terminology consistency across all translated files.
If any violations are found, resolve them before marking the run complete.

## Prompt Templates

Prompt templates are colocated with this skill:
- `./translator-prompt.md`
- `./reviewer-prompt.md` (combined source + quality review)
- `./refiner-prompt.md`

## Dispatch Templates

All context is inlined by the orchestrator before dispatch. Subagents must not read any files themselves.

### translator

```text
Task tool (general-purpose):
  description: "Translate draft for <TARGET_FILE>"
  prompt template: ./translator-prompt.md
  placeholders:
    <TARGET_FILE>        path string
    <SOURCE_CONTENT>     inlined file content
    <DRAFT_FILE>         draft output path
    <GLOSSARY_CONTENT>   inlined glossary.json content
    <STYLE_CONTENT>      inlined style-decisions.json content
```

### reviewer

```text
Task tool (general-purpose):
  description: "Review translation for <TARGET_FILE>"
  prompt template: ./reviewer-prompt.md
  placeholders:
    <TARGET_FILE>        path string
    <SOURCE_CONTENT>     inlined source file content
    <DRAFT_FILE>         draft file path
    <DRAFT_CONTENT>      inlined draft file content (read after translator finishes)
    <GLOSSARY_CONTENT>   inlined glossary.json content
    <STYLE_CONTENT>      inlined style-decisions.json content
```

### refiner

```text
Task tool (general-purpose):
  description: "Refine draft for <TARGET_FILE>"
  prompt template: ./refiner-prompt.md
  placeholders:
    <TARGET_FILE>        path string
    <SOURCE_CONTENT>     inlined source file content
    <DRAFT_FILE>         draft file path
    <DRAFT_CONTENT>      inlined current draft content (re-read after each iteration)
    <REVIEW_JSON>        reviewer output JSON
    <GLOSSARY_CONTENT>   inlined glossary.json content
    <STYLE_CONTENT>      inlined style-decisions.json content
```

## Example Workflow

### Auto-select (no args)

```text
You: /super-translate

[Step 1] Verify files → auto-select from progress tracker:
  翻譯進度：已完成 0 / 10 個章節
  本批次自動選取以下 3 個檔案：
  - [not_started 新增] rules/intro.md
  - [not_started 新增] rules/combat.md
  - [not_started 新增] rules/equipment.md
  是否繼續？

[Steps 2-5] Setup: TodoWrite, terminology preflight, mode, draft dir

Batch 1: rules/intro.md
  - translator -> draft generated
  - reviewer -> pass
  - writeback + update translation-progress (completed=1) + TodoWrite

Batch 1: rules/combat.md
  - translator -> draft generated
  - reviewer -> 1 critical issue
  - refiner -> fixed
  - reviewer -> pass
  - writeback + update translation-progress (completed=2) + TodoWrite

Batch 1: rules/equipment.md
  - translator -> draft generated
  - reviewer -> pass
  - writeback + update translation-progress (completed=3) + TodoWrite

[Step 8 Batch checkpoint]
  - 已完成 3 / 10 個章節
  - completed: 3, blocked: 0
  - git commit -m "progress: 3/10"
  - 是否繼續下一批？

User: 繼續

[Step 1 re-run] auto-select next 3 not_started files → Batch 2...
```

### Explicit target

```text
You: /super-translate rules/combat.md rules/equipment.md

[Step 1] Use specified files directly (skip auto-select)
...
```

## Common Mistakes

**Wrong:** Overwrite source before reviewer passes
**Correct:** Keep draft isolated until reviewer passes

**Wrong:** Skip TodoWrite updates until end of run
**Correct:** Sync TodoWrite and `translation-progress.json` after each review loop

**Wrong:** Invent translation for unknown terms
**Correct:** Run `term_edit.py --set-zh` workflow (auto-runs `--cal`), then rerun affected file

## Progress Sync Contract (Required)

1. Sync TodoWrite and `translation-progress.json` at file start, every review loop, and file close.
2. Never defer sync until end-of-run.
3. Create the batch checkpoint commit immediately after each completed batch.

## When to Stop and Ask for Help

Stop when:
- repeated critical findings remain after iteration cap
- subagent output is malformed and not safely recoverable

## Red Flags

Never:
- skip TodoWrite creation
- overwrite source with unresolved critical findings
- use script-generated prose translation
- restate `frontmatter.title` as any body heading
- invent an overview heading that does not exist in the source
