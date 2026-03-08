---
name: check-completeness
description: Use when validating translated documentation for missing rule content.
user-invocable: true
disable-model-invocation: true
---

# Check Completeness

## Overview

Validate that translated docs preserve source rule coverage, structure, and navigability.

**Core principle:** Compare against source with evidence, then patch gaps and re-check.

## The Process

### Step 1: Resolve Scope and Inputs

1. Resolve target from `$ARGUMENTS` or all sections.
2. Load source with page markers: `data/markdown/<name>_pages.md`.
3. Load outputs under `docs/src/content/docs/` and `chapters.json`.
4. Create TodoWrite items for comparison, repair, and verification.

### Step 2: Perform Structural Comparison

Check:
- page coverage mapped from `chapters.json`
- heading hierarchy parity (H2/H3)
- table count parity
- list structure parity

### Step 3: Perform Content Integrity Checks

Check:
- rule coverage
- examples retained per translation mode
- internal link and anchor integrity

### Step 4: Report Gaps

Reference format:

```markdown
## Completeness Report

### Missing Content
- Pages 45-47 not in any chapter

### Incomplete Sections
- rules/combat.md: 2 tables in source, 1 in output

### Broken References
- [Invalid Link](/path/) in file.md:15
```

### Step 5: Repair and Re-verify

1. Restore missing content from source.
2. Fix broken structure/links.
3. Re-run completeness checks.
4. Repeat until critical gaps are cleared.

## Progress Sync Contract (Required)

1. Update TodoWrite after each section audit.
2. Mark each repaired gap with path reference.
3. Mark verification done only after final clean pass.

## When to Stop and Ask for Help

Stop when:
- source structure is ambiguous and split decision affects meaning
- missing content cannot be mapped reliably to a target file
- repairs would conflict with user-selected summary mode expectations

## When to Revisit Earlier Steps

Return to Step 1 when:
- chapter mapping changes
- source extraction is regenerated
- user changes completeness expectations

## Red Flags

Never:
- ignore page coverage mismatches
- silently drop examples required by current mode
- finalize with unresolved broken links

## Next Step

After completeness is clean, run `/check-consistency` and proceed to `/super-translate` if needed.

## Example Usage

```text
/check-completeness
/check-completeness rules
/check-completeness characters
```
