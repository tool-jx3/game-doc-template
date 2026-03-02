---
name: translate
description: Use when translating one file, one section, or all docs with glossary and style constraints.
user-invocable: true
disable-model-invocation: true
---

# Translate Document

## Overview

Translate target markdown content to Traditional Chinese with strict glossary compliance and structure preservation.

**Core principle:** Translate manually, preserve mechanics, keep formatting stable, and update progress continuously.

## The Process

### Step 1: Resolve Scope and Preconditions

1. Resolve target from `$ARGUMENTS` (`single file`, `section`, or `all`).
2. Ensure required files exist:
- `glossary.json`
- `style-decisions.json`
- `data/translation-progress.json` (if initialized)
3. Create TodoWrite items for each target file.

### Step 2: Terminology Preflight (Fail-Closed)

Run:

```bash
uv run python scripts/validate_glossary.py
uv run python scripts/term_read.py --fail-on-missing --fail-on-forbidden
```

If either command fails, stop and resolve terminology issues first.

### Step 3: Resolve Translation Mode

1. Read `style-decisions.json.translation_mode.mode`.
2. If missing, ask user in Traditional Chinese:
- **完整翻譯**：完整翻譯所有內容，保留原始結構與細節
- **摘要翻譯**：精簡翻譯重點規則，省略範例與冗長說明
3. Persist mode decision before translating.

### Step 4: Translate Per File

For each file:
1. mark TodoWrite file item `in_progress`
2. read source content and identify segments
3. apply glossary + style decisions
4. translate manually (no script-generated prose)
5. preserve markdown/frontmatter structure
6. write translated file

Unknown term flow:

```bash
uv run python scripts/term_edit.py --term "<TERM>" --cal
uv run python scripts/term_edit.py --term "<TERM>" --set-zh "<ZH>" --status approved --mark-term
uv run python scripts/term_read.py --fail-on-forbidden
```

### Step 5: Update Progress and Verify

After each file:
- update `data/translation-progress.json` matching chapter status
- refresh `_meta.updated` and recalculate `_meta.completed`
- mark TodoWrite file item completed

After batch or scope completion:

```bash
uv run python scripts/term_read.py --fail-on-forbidden
```

## Progress Sync Contract (Required)

1. Keep TodoWrite and `translation-progress.json` in sync per file.
2. Never delay progress update to end-of-run only.

## When to Stop and Ask for Help

Stop when:
- mode policy is unclear
- source text ambiguity changes mechanics meaning
- repeated terminology conflicts block translation integrity

## When to Revisit Earlier Steps

Return to Step 1 or 3 when:
- target scope changes
- translation mode changes
- glossary decisions change materially

## Red Flags

Never:
- use regex/batch replacement to generate translated prose
- overwrite structure accidentally
- leave progress tracker stale for translated files

## Next Step

After translation, run `/check-consistency` and `/check-completeness` as needed.

## Example Usage

```text
/translate
/translate docs/src/content/docs/rules/basic.md
/translate rules
/translate all
```
