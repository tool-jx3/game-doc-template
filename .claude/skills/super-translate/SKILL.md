---
name: super-translate
description: Use when high-quality translation is needed with multi-agent review loops and strict progress tracking.
user-invocable: true
disable-model-invocation: true
---

# Super Translate

## Overview

Run iterative translation with reviewer loops and strict state/progress controls.
Pipeline: `translator -> source-reviewer -> quality-reviewer -> refiner`.

**Core principle:** Source-fidelity gate first, quality gate second, no overwrite unless both pass.

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
- sub-steps: draft, source review, quality review, refine loop, writeback
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

### Step 5: Initialize Runtime State

```bash
mkdir -p .claude/skills/super-translate/.state/drafts
bash .claude/skills/super-translate/scripts/run_state.sh start \
  --targets <file1> <file2> ...
```

If initialization fails, abort run.

### Step 6: Execute Per Batch (Default First 3 Files)

For each target file:
1. mark TodoWrite item `in_progress`
2. set progress status `in_progress` and update notes
3. mark runtime `running`

```bash
bash .claude/skills/super-translate/scripts/run_state.sh update \
  --file <target_file> \
  --status running
```

4. produce draft only (do not overwrite source)
5. run source reviewer
6. if fail -> refine -> re-run source reviewer
7. after source pass, run quality reviewer
8. if fail -> refine -> re-run quality reviewer
9. cap at 3 iterations

If 3 iterations still have critical issues, ask user in Traditional Chinese:
- **保留目前草稿，不覆蓋原始檔，稍後手動修正後再續跑**
- **停止此檔案，先處理術語或規則歧義再繼續**

Unknown term handling:

```bash
uv run python scripts/term_edit.py --term "<TERM>" --cal
uv run python scripts/term_edit.py --term "<TERM>" --set-zh "<ZH>" --status approved --mark-term
uv run python scripts/validate_glossary.py
uv run python scripts/term_read.py --fail-on-missing --fail-on-forbidden
```

Then rerun the file loop.

### Step 7: Controlled Writeback and State Update

Only if both reviewer gates pass:
- atomically replace source with draft
- mark runtime `pass`
- set chapter `completed`
- recalculate `_meta.completed`
- close TodoWrite file item

If blocked/failed:
- keep source unchanged
- mark runtime `blocked` or `failed`
- keep chapter `in_progress`
- mark TodoWrite as blocked

### Step 8: Batch Checkpoint Report

After each batch:
- report completed/blocked/failed files
- report iteration counts and remaining criticals
- confirm TodoWrite + progress tracker sync
- ask whether to continue next batch

### Step 9: Final Verification

```bash
bash .claude/skills/super-translate/scripts/run_state.sh end
uv run python scripts/validate_glossary.py
uv run python scripts/term_read.py --fail-on-missing --fail-on-forbidden
```

Invoke `check-consistency` skill to validate terminology consistency across all translated files.
If any violations are found, resolve them before marking the run complete.

## Progress Sync Contract (Required)

1. Sync TodoWrite and `translation-progress.json` at file start, every review loop, and file close.
2. Never defer sync until end-of-run.

## When to Stop and Ask for Help

Stop when:
- repeated critical findings remain after iteration cap
- runtime state script fails unexpectedly
- subagent output is malformed and not safely recoverable

## When to Revisit Earlier Steps

Return to scope/mode steps when:
- user changes scope
- translation mode changes
- glossary policy changes significantly

## Red Flags

Never:
- skip TodoWrite creation
- run quality review before source review passes
- overwrite source with unresolved critical findings
- use script-generated prose translation

