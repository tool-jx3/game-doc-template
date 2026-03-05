---
name: super-translate
description: Use when high-quality translation is needed with multi-agent review loops and strict progress tracking.
user-invocable: true
disable-model-invocation: true
---

# Super Translate

## Overview

Run iterative translation with a single reviewer loop.
Pipeline: `translator -> reviewer -> refiner` (max 2 iterations).

**Core principle:** Source-fidelity and quality checked in one pass; no overwrite unless reviewer passes.

## The Process

### Step 1: Resolve Scope and Preconditions

1. Load targets from `$ARGUMENTS` or ask user in Traditional Chinese.
2. Verify required files:
- `data/translation-progress.json`
- `glossary.json`
- `style-decisions.json`
3. If missing, stop and ask user to initialize first.

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

### Step 5: Prepare Draft Directory

```bash
mkdir -p .claude/skills/super-translate/.state/drafts
```

### Step 6: Execute Per Batch (Default First 3 Files)

For each target file:
1. mark TodoWrite item `in_progress`
2. update `translation-progress.json` status to `in_progress`
3. dispatch translator using `./translator-prompt.md` to produce draft only (do not overwrite source)
4. dispatch reviewer using `./reviewer-prompt.md` (combined source fidelity + quality check)
5. if fail -> dispatch refiner using `./refiner-prompt.md` -> re-run reviewer
6. cap at 2 iterations total

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
- replace source with draft
- update `translation-progress.json` status to `completed`, recalculate `_meta.completed`
- close TodoWrite file item

If blocked/failed:
- keep source unchanged
- keep `translation-progress.json` status as `in_progress`
- mark TodoWrite as blocked

### Step 8: Batch Checkpoint Report

After each batch:
- report completed/blocked/failed files
- report iteration counts
- confirm TodoWrite + progress tracker sync
- ask whether to continue next batch

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

Use these fixed dispatch patterns:

### translator

```text
Task tool (general-purpose):
  description: "Translate draft for <TARGET_FILE>"
  prompt template: ./translator-prompt.md
  placeholders:
    <TARGET_FILE>, <DRAFT_FILE>
```

### reviewer

```text
Task tool (general-purpose):
  description: "Review translation for <TARGET_FILE>"
  prompt template: ./reviewer-prompt.md
  placeholders:
    <TARGET_FILE>, <DRAFT_FILE>
```

### refiner

```text
Task tool (general-purpose):
  description: "Refine draft for <TARGET_FILE>"
  prompt template: ./refiner-prompt.md
  placeholders:
    <TARGET_FILE>, <DRAFT_FILE>, <REVIEW_JSON>
```

## Example Workflow

```text
You: Start /super-translate for rules/combat.md and rules/equipment.md

[Step 1] Load scope and verify files
[Step 2] Create TodoWrite for both targets + batch checkpoint
[Step 3] Run terminology preflight
[Step 4] Resolve translation mode
[Step 5] Prepare draft directory

Batch 1: rules/combat.md
  - translator -> draft file generated
  - reviewer -> found 1 critical issue
  - refiner -> fixed issue
  - reviewer -> pass
  - writeback + update translation-progress + TodoWrite

Batch 1: rules/equipment.md
  - translator -> draft file generated
  - reviewer -> pass
  - writeback + update translation-progress + TodoWrite

[Batch checkpoint report]
  - completed: 2, blocked: 0
  - ask user: continue next batch?

[Final verification]
  - validate_glossary + term_read
  - run check-consistency
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

## When to Stop and Ask for Help

Stop when:
- repeated critical findings remain after iteration cap
- subagent output is malformed and not safely recoverable

## Red Flags

Never:
- skip TodoWrite creation
- overwrite source with unresolved critical findings
- use script-generated prose translation
