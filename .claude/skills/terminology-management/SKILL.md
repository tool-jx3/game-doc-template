---
name: terminology-management
description: Use when creating, editing, validating, or enforcing glossary-driven terminology.
---

# Terminology Management

## Overview

Maintain glossary quality and enforce terminology consistency across all translated content.

**Core principle:** Glossary is the source of truth; validation must run before and after any terminology update.

## The Process

### Step 1: Load Glossary Baseline

1. Load `glossary.json`.
2. Confirm schema validity:

```bash
uv run python scripts/validate_glossary.py
```

3. Create TodoWrite items for candidate generation, decisions, and verification.

### Step 2: Generate and Classify Candidates

Run:

```bash
uv run python scripts/term_generate.py --min-frequency 2
```

Classify each candidate as:
- managed game term
- normal prose (not managed)

If `proper_nouns.mode != keep_original`, repeated proper nouns (`>=2`) must be managed.

### Step 3: Edit Glossary Safely

For unmanaged terms, `--cal` is auto-run when editing:

```bash
uv run python scripts/term_edit.py --term "<TERM>" --set-zh "<ZH_TERM>" --status approved --mark-term
```

To run `--cal` standalone (inspect evidence without editing):

```bash
uv run python scripts/term_edit.py --term "<TERM>" --cal
```

### Step 4: Validate Usage Across Docs

Run:

```bash
uv run python scripts/term_read.py --fail-on-forbidden
```

Check for:
- missing managed terms
- inconsistent variants
- unintended untranslated residual English terms

### Step 5: Apply Fixes and Recheck

1. Apply approved replacements where needed.
2. Re-run `term_read.py` until clean.

## Progress Sync Contract (Required)

1. Track each term candidate and decision with TodoWrite.
2. Mark a term item complete only after `term_read.py` is clean for that change.

## When to Stop and Ask for Help

Stop when:
- glossary policy conflicts are unresolved
- a term has culturally nuanced ambiguity affecting tone/mechanics
- bulk changes risk unintended semantic shifts

## When to Revisit Earlier Steps

Return to Step 2 when:
- corpus changes significantly
- proper noun policy changes

## Red Flags

Never:
- bypass glossary schema validation
- leave inconsistent managed terms unresolved

## Next Step

Continue with `/check-consistency`, `/translate`, or `/super-translate`.
