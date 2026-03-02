---
name: check-consistency
description: Use when auditing terminology consistency across translated documentation.
user-invocable: true
disable-model-invocation: true
---

# Check Terminology Consistency

## Overview

Audit translated docs against glossary decisions, detect terminology drift, and produce actionable fixes.

**Core principle:** Validate first, fix with explicit decisions, then re-validate until clean.

## The Process

### Step 1: Load Scope and Baseline

1. Resolve scope from `$ARGUMENTS` or default to all docs under `docs/src/content/docs/`.
2. Confirm `glossary.json` and `style-decisions.json` exist.
3. Create TodoWrite items for scan, decision, fix, and recheck.

### Step 2: Run Consistency Scan (Fail-Closed)

Run:

```bash
uv run python scripts/validate_glossary.py
uv run python scripts/term_read.py --fail-on-forbidden
```

Optional machine-readable output:

```bash
uv run python scripts/term_read.py --json
```

If glossary validation fails, stop and fix schema/data first.

### Step 3: Produce Report

Report with three groups:
- missing from glossary
- inconsistent translations
- untranslated residual English terms

Reference format:

```markdown
## Consistency Report

### Missing from Glossary
- `Term` (files: path:line, path:line)

### Inconsistent Usage
- `Term`: "Translation A" (3x), "Translation B" (2x)

### Untranslated Terms
- "English" in path:line
```

### Step 4: Resolve and Apply Fixes

For each issue:
1. Ask user in Traditional Chinese when a decision is required.
2. Add or update glossary entries:

```bash
uv run python scripts/term_edit.py --term "<TERM>" --cal
uv run python scripts/term_edit.py --term "<TERM>" --set-zh "<ZH>" --status approved --mark-term
```

3. Apply document replacements carefully.

### Step 5: Re-verify and Close

Re-run scan until no critical terminology issues remain:

```bash
uv run python scripts/term_read.py --fail-on-forbidden
```

Update TodoWrite statuses and close all items.

## Progress Sync Contract (Required)

1. Mark scan item `in_progress` before running scripts.
2. Mark each terminology decision item after user confirmation.
3. Mark recheck item only after clean scan result.

## When to Stop and Ask for Help

Stop when:
- glossary schema is invalid and ambiguous to repair
- term decisions affect tone/mechanics and user preference is unknown
- replacement scope may cause unintended global regressions

## When to Revisit Earlier Steps

Return to Step 1 when:
- scope changes
- glossary updates happen mid-run
- new untranslated files are added

## Red Flags

Never:
- auto-apply term changes without recording decision context
- skip re-validation after edits
- ignore unresolved forbidden terms

## Next Step

If terminology is clean, continue with `/check-completeness` or `/super-translate`.

## Example Usage

```text
/check-consistency
/check-consistency rules
```
