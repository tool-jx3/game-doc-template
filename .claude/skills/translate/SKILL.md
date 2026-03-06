---
name: translate
description: Use when translating one file, one section, or all docs with glossary and style constraints.
user-invocable: true
disable-model-invocation: true
---

# Translate Document

## Overview

Single-pass translation of markdown content to Traditional Chinese with glossary compliance, draft isolation, and progress tracking.

**Core principle:** Draft first, verify before writeback, never overwrite source with unverified output.

## The Process

### Step 1: Resolve Scope and Preconditions

1. Verify required files exist:
   - `glossary.json`
   - `style-decisions.json`
   - `data/translation-progress.json`
   If any are missing, stop and ask user to run `/init-doc` first.

2. Resolve target files:
   - If `$ARGUMENTS` specifies concrete file paths or a scoped pattern → use those directly.
   - Otherwise (no args, `all`, or `next`) → **auto-select from `translation-progress.json`**:
     1. **Resume first**: collect all files with status `in_progress` (highest priority).
     2. **Then queue**: collect files with status `not_started`, in chapter order.
     3. Display selected files to user in Traditional Chinese before proceeding:
        ```
        翻譯進度：已完成 X / Y 個章節
        已從進度表自動選取以下檔案：
        - [in_progress 繼續] <file>
        - [not_started 新增] <file>
        …
        是否繼續？或請指定其他範圍。
        ```
     4. Wait for user confirmation or override.

### Step 2: Create Task List

Create tasks with:
- one item per target file
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

```bash
mkdir -p .claude/skills/translate/.state/drafts
```

### Step 6: Translate Per File

For each target file:

1. Mark task item `in_progress`
2. Update `translation-progress.json` status to `in_progress`
3. Read source content, `glossary.json`, and `style-decisions.json`
4. Translate to draft file (`.claude/skills/translate/.state/drafts/<filename>`)
   - Traditional Chinese only (Taiwan usage), no Simplified Chinese
   - Preserve markdown structure exactly (frontmatter, headings, lists, tables, links, code blocks)
   - Use glossary mappings exactly
   - Manual translation only (no script-generated prose)
   - Do NOT overwrite source file; write only to draft path
5. Self-review the draft against source:
   - Missing or truncated content?
   - Glossary violations?
   - Markdown structure broken?
   - Full-width punctuation correct?
   - Fix any issues found in the draft directly
6. Writeback: replace source with draft
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

### Step 7: Final Verification

```bash
uv run python scripts/validate_glossary.py
uv run python scripts/term_read.py --fail-on-missing --fail-on-forbidden
```

Mark final verification task item completed.

## Progress Sync Contract (Required)

1. Sync task list and `translation-progress.json` at file start and file close.
2. Never defer sync until end-of-run.

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

## Next Step

After translation, run `/check-consistency` and `/check-completeness` as needed.

## Example Usage

```text
/translate
/translate docs/src/content/docs/rules/basic.md
/translate rules
/translate all
```
