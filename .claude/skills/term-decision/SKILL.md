---
name: term-decision
description: Use when selecting terminology and applying consistent replacements across documentation.
user-invocable: true
---

# Terminology Decision

## Overview

Decide contested terms, record rationale, apply replacements, and verify consistency.

**Core principle:** No global replacement without explicit term decision and verification.

## Interaction Rules

- All user interaction and candidate translations must use Traditional Chinese (zh-TW, Taiwan usage).
- Do not use Simplified Chinese or Hong Kong-specific wording in user-facing text or term candidates.

## The Process

### Step 1: Resolve Decision Scope

1. If `$ARGUMENTS` exists, focus on that term.
2. Otherwise collect candidates from:
- source glossary / terminology pages in extracted markdown
- source index / appendix term lists
- `term_read.py` inconsistency output
- `term_generate.py` missing candidates
- user-flagged terminology
3. Create TodoWrite items per term.

### Step 2: Prepare Decision Brief

Before presenting a term to the user, check whether the source book already defines or lists it in:
- glossary pages
- index pages
- summary tables / reference pages

If strong source evidence exists, do one first-pass term translation directly:
- add obvious, low-ambiguity terms to `glossary.json`
- reserve user discussion only for uncertain, tone-sensitive, or mechanics-ambiguous terms

For each term, present:
- source term
- source glossary/index evidence when available
- current variants and usage locations
- 2-3 candidate translations with short rationale
- related conventions from `style-decisions.json`

### Step 3: Ask User Decision (Traditional Chinese)

Collect:
1. chosen translation
2. allowed context-specific variants (if any)
3. rationale note

### Step 4: Persist Decision

Record in `style-decisions.json` and update `glossary.json`:

```bash
uv run python scripts/term_edit.py --term "<TERM>" --set-zh "<ZH>" --status approved --mark-term --notes "<REASON>"
```

### Step 5: Apply and Verify

1. Preview replacement impact across docs.
2. Apply approved replacements.
3. Verify:

```bash
uv run python scripts/term_read.py --fail-on-forbidden
```

## Progress Sync Contract (Required)

1. One TodoWrite item per term decision.
2. Mark replacement item complete only after verification passes.

## When to Stop and Ask for Help

Stop when:
- term choice changes mechanics interpretation
- user preference conflicts with existing glossary policy
- replacement scope is ambiguous

## When to Revisit Earlier Steps

Return to Step 2 when:
- new conflicting evidence appears
- user changes proper noun policy

## Red Flags

Never:
- apply unapproved term variants globally
- skip post-edit glossary validation
- skip post-replacement verification

## Next Step

After term decisions are stable, continue with `/translate` or `/super-translate`.

## Example Usage

```text
/term-decision
/term-decision Move
/term-decision "Basic Move"
```
