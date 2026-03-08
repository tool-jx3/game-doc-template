---
name: translate
description: Use when translating one file, one section, or all docs with glossary and style constraints.
user-invocable: true
disable-model-invocation: true
---

# Translate Document

## Overview

Single-pass translation of markdown content to Traditional Chinese with glossary compliance, draft isolation, progress tracking, and one Git checkpoint commit per completed batch.

**Core principle:** Draft first, verify before writeback, never overwrite source with unverified output.

## The Process

### Step 1: Resolve Scope and Preconditions

1. Verify required files exist:
   - `glossary.json`
   - `style-decisions.json`
   - `data/translation-progress.json`
   If any are missing, stop and ask user to run `/init-doc` first.

2. Resolve target files:
   - If `$ARGUMENTS` specifies concrete file paths or a scoped pattern → use those directly as the current batch.
   - Otherwise (no args, `all`, or `next`) → **auto-select from `translation-progress.json`**:
     1. **Resume first**: collect all files with status `in_progress` (highest priority).
     2. **Then queue**: collect files with status `not_started`, in chapter order.
     3. Display selected files to user in Traditional Chinese before proceeding:
        ```
        翻譯進度：已完成 X / Y 個章節
        本批次已從進度表自動選取以下檔案：
        - [in_progress 繼續] <file>
        - [not_started 新增] <file>
        …
        是否繼續？或請指定其他範圍。
        ```
     4. Wait for user confirmation or override.
   - The selected target set for this run is one batch. If only one file is selected, that single file is the batch.

### Step 2: Create Task List

Create tasks with:
- one item per target file
- a batch checkpoint commit item
- a final verification item

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
- **摘要翻譯**：精簡翻譯重點規則，省略範例與冗長說明

Persist mode before translating.

### Step 5: Prepare Draft Directory

For each target file, obtain its draft path (this also creates the directory):

```bash
uv run python scripts/draft.py path <TARGET_FILE>
```

Use the printed path as `<DRAFT_FILE>` for that file.

### Step 6: Translate Per File

For each target file:

1. Mark task item `in_progress`
2. Update `translation-progress.json` status to `in_progress`
3. Read source content, `glossary.json`, and `style-decisions.json`
4. Get draft path:
   ```bash
   DRAFT_FILE=$(uv run python scripts/draft.py path <TARGET_FILE>)
   ```
   Translate to `$DRAFT_FILE`:
   - Preserve the `_draft_source` field already in the stub frontmatter; do not remove it
   - Traditional Chinese only (Taiwan usage), no Simplified Chinese
   - Preserve markdown structure exactly (frontmatter, headings, lists, tables, links, code blocks)
   - Treat `frontmatter.title` as the page title; do not restate it anywhere in the body as a heading of any level (`#`, `##`, etc.)
   - If the source page opens with an overview/introduction block that has no heading, translate it as plain body content; do not invent a `#` or `## 概覽` heading
   - Preserve image links exactly; if an image link appears within the source flow for a paragraph, keep the same link but place it near the middle of the translated paragraph instead of splitting the paragraph into separate blocks
   - Use glossary mappings exactly
   - Manual translation only (no script-generated prose)
   - Do NOT overwrite source file; write only to `$DRAFT_FILE`
5. Self-review the draft against source:
   - Missing or truncated content?
   - Glossary violations?
   - Markdown structure broken?
   - Added any heading of any level that simply restates `frontmatter.title`?
   - Added `概覽`/overview heading that does not exist in the source?
   - Image links preserved and kept inside the paragraph flow without splitting the paragraph?
   - Full-width punctuation correct?
   - Content contamination: any paragraph or block that has no corresponding source in the original file?
   - Untranslated English: any English words left untranslated (excluding code/dice notation such as `1d6`, `+2`)? Terminology must match `glossary.json`; proper nouns follow `style-decisions.json` policy.
   - Fix any issues found in the draft directly
6. Writeback:
   ```bash
   uv run python scripts/draft.py writeback <TARGET_FILE>
   ```
7. **Immediately** update `translation-progress.json`:
   - Set file status to `completed`
   - Recalculate `_meta.completed` (count of completed entries)
   - Update `_meta.updated` to current timestamp
   Do NOT defer this update; write it before moving to the next file.
8. Mark task item completed

**Unknown term handling:**

```bash
uv run python scripts/term_edit.py --term "<TERM>" --set-zh "<ZH>" --status approved --mark-term
uv run python scripts/term_read.py --fail-on-forbidden
```

Then continue translating with the updated glossary.

### Step 7: Batch Checkpoint Commit

After all files in the current batch are processed:

1. Run `git status --short` and verify batch scope before staging.
2. Stage **only** files touched by this batch:
   - completed translated source files from this batch
   - `data/translation-progress.json`
   - `glossary.json` if changed in this batch
   - `style-decisions.json` if changed in this batch
3. Create one checkpoint commit for the batch:

```bash
git commit -m "progress: X/Y"
```

4. Commit message rules:
   - keep it short and progress-only
   - use the current completion count from `translation-progress.json`
   - do not mention filenames, rationale, or extra prose
5. Never stage or commit unrelated user changes.
6. If no file reached `completed` in this batch, skip the commit.

### Step 8: Final Verification

```bash
uv run python scripts/validate_glossary.py
uv run python scripts/term_read.py --fail-on-missing --fail-on-forbidden
```

Mark final verification task item completed.

## Progress Sync Contract (Required)

1. Sync task list and `translation-progress.json` at file start and file close.
2. Never defer sync until end-of-run.
3. Create the batch checkpoint commit immediately after batch completion; do not postpone it to a later batch.

## When to Stop and Ask for Help

Stop when:
- mode policy is unclear
- source text ambiguity changes mechanics meaning
- repeated terminology conflicts block translation integrity

## When to Revisit Earlier Steps

Return to Step 1 or 4 when:
- target scope changes
- translation mode changes
- glossary decisions change materially

## Red Flags

Never:
- overwrite source before self-review
- use regex/batch replacement to generate translated prose
- leave progress tracker stale for translated files
- invent translations for unknown terms (use term_edit.py workflow)
- add any body heading that restates `frontmatter.title`
- invent an overview heading that does not exist in the source

## Next Step

After translation, run `/check-consistency` and `/check-completeness` as needed.

## Example Usage

```text
/translate
/translate docs/src/content/docs/rules/basic.md
/translate rules
/translate all
```
