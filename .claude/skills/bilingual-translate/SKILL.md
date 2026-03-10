---
name: bilingual-translate
description: Use when translating in bilingual mode — produces Chinese primary + English blockquote markdown. Single-pass, no multi-round review. Requires translation_mode=bilingual in style-decisions.json.
user-invocable: true
disable-model-invocation: true
---

# Bilingual Translate

## Overview

Single-pass bilingual translation. Produces documents where each Chinese paragraph is followed by the English original as a blockquote.

**Output format:**

```markdown
中文翻譯段落文字。

> Original English paragraph text here.
```

**Core principle:** Draft-first with bilingual_prep.py placeholders. Write directly to bilingual output dir. No multi-round review loop.

## Task Initialization (MANDATORY)

Before ANY action, create tasks using TaskCreate:
- One task per target file
- One task for batch checkpoint
- One task for final verification

## The Process

### Step 1: Resolve Scope and Preconditions

1. Verify required files:
   - `glossary.json`
   - `style-decisions.json` with `translation_mode.mode == "bilingual"`
   - `chapters.json` with `"mode": "bilingual"`
   If any missing or mode mismatch, stop and ask user to run `/init-doc` first.

2. Resolve target files from `$ARGUMENTS` or auto-select from `translation-progress-bilingual.json` (if it exists). If the progress file does not exist, treat all files from `chapters.json` as `not_started`.

3. Display selected files to user in Traditional Chinese before proceeding.

**Verification:** Target file list confirmed; all required files and mode settings present.

### Step 2: Terminology Preflight (Fail-Closed)

```bash
uv run python scripts/validate_glossary.py
uv run python scripts/term_read.py --fail-on-missing --fail-on-forbidden
```

If preflight fails, stop and fix terminology first.

**Verification:** Both commands exit 0.

### Step 3: Prepare Bilingual Draft

For each target file, determine the source English markdown path from `data/markdown/` (the `_pages.md` source referenced in `chapters.json`).

Determine the output path: `docs/src/content/docs/bilingual/<section>/<file>.md` (from `chapters.json` + `mode=bilingual`).

Run bilingual_prep.py to generate the draft with placeholders in `.claude/skills/bilingual-translate/.state/drafts/`:

```bash
uv run python scripts/bilingual_prep.py <SOURCE_FILE> <DRAFT_FILE>
```

**Verification:** Draft file exists and contains `<!-- TODO: 翻譯 -->` placeholders.

### Step 4: Translate Per File

For each target file:

1. Mark task `in_progress`
2. Read draft, `glossary.json`, and `style-decisions.json`
3. For each `<!-- TODO: 翻譯 -->` placeholder: replace it with the Chinese translation of the English text in the immediately following blockquote line(s)
4. Update frontmatter `title` to Traditional Chinese; add `bilingual: true` if not present
5. Single-pass self-review:
   - Any `<!-- TODO: 翻譯 -->` left untranslated?
   - Glossary violations?
   - Full-width punctuation correct in Chinese text?
   - English blockquote lines (starting with `>`) preserved exactly — no modifications?
   - Content contamination (paragraphs with no source)?
6. Write final file to `docs/src/content/docs/bilingual/<path>`
7. Update `translation-progress-bilingual.json` (create if absent):
   - Set file status to `completed`
   - Update `_meta.completed` and `_meta.updated`
8. Mark task completed

**Verification:** Self-review checklist passes; output file written; progress JSON updated.

### Step 5: Batch Checkpoint Commit

After all files in the batch are processed:

1. Run `git status --short` and verify batch scope before staging.
2. Stage only files touched by this batch:
   - Translated bilingual files
   - `translation-progress-bilingual.json`
   - `glossary.json` if changed
   - `style-decisions.json` if changed
3. Commit:

```bash
git commit -m "progress (bilingual): X/Y"
```

Where X/Y is current completion from `translation-progress-bilingual.json`.

**Verification:** `git log -1` shows progress commit.

### Step 6: Final Verification

```bash
uv run python scripts/validate_glossary.py
uv run python scripts/term_read.py --fail-on-missing --fail-on-forbidden
```

Mark final verification task completed.

**Verification:** Both commands exit 0; all tasks completed.

## Red Flags

| Thought | Reality |
|---------|---------|
| "Modify the English blockquote lines" | Never alter `>` lines. They are source text. |
| "Skip bilingual_prep, I'll format manually" | bilingual_prep ensures consistent structure. Always use it. |
| "translation-progress-bilingual.json doesn't exist, skip tracking" | Create it on first run. |
| "One file done, no need for checkpoint" | Every completed batch gets a commit. |
| "Skip terminology preflight, it was fine last time" | Glossary changes between runs. Always preflight. |

## When to Stop and Ask for Help

Stop when:
- mode mismatch (style-decisions says bilingual but chapters.json doesn't)
- source markdown is missing or unreadable
- terminology conflicts block translation integrity

## Example Usage

```text
/bilingual-translate
/bilingual-translate docs/src/content/docs/bilingual/rules/combat.md
/bilingual-translate all
```
