---
name: chapter-split
description: Use when extracted rulebook markdown needs to be split into semantic documentation files and navigation. Trigger this skill from `init-doc`, future append/add-document flows, or whenever regenerated `_pages.md` source invalidates the existing chapter map. Do not use this skill for temporary translation chunking; that belongs to a separate draft-only translation workflow.
---

# Chapter Split

## Overview

Split one extracted `_pages.md` source into semantic documentation files, then regenerate site navigation from the resulting chapter map.

**Core principle:** Keep publication structure semantic and stable; do not overload chapter split with temporary translation chunking.

## The Process

### Step 1: Resolve Scope and Preconditions

1. Resolve source pages markdown from `$ARGUMENTS` or the caller handoff.
2. Require a `_pages.md` source produced by `extract_pdf.py`.
3. Require `style-decisions.json` if present; reuse existing formatting and proper-noun decisions instead of re-asking.
4. Reuse the caller's image retention decision if available:
   - `preserve_images = true` → enable image manifest handling
   - `preserve_images = false` → disable images in split config
5. Default config output is `chapters.json` unless the caller explicitly provides another path.

### Step 2: Create TodoWrite

Create items for:
- split planning
- image split policy
- split execution
- navigation regeneration
- output validation

### Step 3: Draft Chapter Config with Two Focused Agents

Run split planning with two focused agents.
Pipeline: `toc-planner -> wordcount-planner`.

Split policy for both planners:
- Prefer semantic chapter/file boundaries from the source TOC or clear in-text subheadings.
- Do not break one long chapter into generic numbered parts like `1`, `2`, `3`, `part-1`, or `一`, `二`, `三` unless those are the actual source headings.
- When a long chapter needs internal subdivision, keep the top-level section slug stable and use nested file paths inside `files` (for example `equipment/weapons`) so the output can use subdirectories.
- If no trustworthy subordinate headings exist, keep the chapter as one file and surface the risk instead of inventing arbitrary numbered splits.

1. Create draft config path:
   - `.claude/skills/chapter-split/.state/chapters.draft.json`
2. Dispatch toc planner using `./split-planner-prompt.md` to generate TOC-aligned draft `chapters_config`.
3. Dispatch wordcount planner using `./split-wordcount-planner-prompt.md` to rebalance file granularity based on word count while preserving TOC order.
4. If wordcount planner reports unresolved critical issues, stop and ask user in Traditional Chinese before writing the final config.

### Step 4: Finalize Config and Image Policy

Before writing the final config:
- if `preserve_images = true`, include:

```json
{
  "images": {
    "enabled": true,
    "assets_dir": "docs/src/assets/extracted",
    "repeat_file_size_threshold": 5
  }
}
```

- if `preserve_images = false`, include:

```json
{
  "images": {
    "enabled": false
  }
}
```

#### Bilingual mode

Read `style-decisions.json` for `translation_mode.mode`.
If `mode == "bilingual"`, add to the final config:

```json
{
  "mode": "bilingual"
}
```

`split_chapters.py` will resolve the effective output path as `<output_dir>/bilingual/`. Do NOT manually set `output_dir` to include `bilingual/` — the script handles that automatically.

Write the final config to `chapters.json` unless the caller explicitly provided another config path.

### Step 5: Execute Split and Regenerate Navigation

Run:

```bash
uv run python scripts/split_chapters.py
uv run python scripts/generate_nav.py
```

If a non-default config path is used, pass it to `split_chapters.py --config <CONFIG_PATH>`.
Current limitation: `generate_nav.py` still reads root `chapters.json`, so callers using another config path must sync it back to root before regenerating navigation.

### Step 6: Validate Output Quality

Validate:
- heading continuity
- page coverage completeness
- image path integrity
- frontmatter correctness

Preview if needed:

```bash
cd docs && bun dev
```

### Step 7: Handoff

Return the finalized chapter map and generated docs to the caller:
- `init-doc` should continue with progress tracker creation and final gate
- manual invocations: if `translation_mode.mode == "bilingual"`, next skill is `/bilingual-translate`; otherwise continue to `/translate` or `/super-translate`

## Prompt Templates

Prompt templates are colocated with this skill:
- `./split-planner-prompt.md`
- `./split-wordcount-planner-prompt.md`

## Dispatch Templates

Use these fixed dispatch patterns:

### toc-planner

```text
Task tool (general-purpose):
  description: "Draft TOC-based split config for <SOURCE_PAGES_FILE>"
  prompt template: ./split-planner-prompt.md
  placeholders:
    <SOURCE_PAGES_FILE>, <DRAFT_CONFIG_PATH>
```

### wordcount-planner

```text
Task tool (general-purpose):
  description: "Rebalance split config by wordcount for <SOURCE_PAGES_FILE>"
  prompt template: ./split-wordcount-planner-prompt.md
  placeholders:
    <SOURCE_PAGES_FILE>, <DRAFT_CONFIG_PATH>
```

## Progress Sync Contract (Required)

1. Keep TodoWrite updated at every step.
2. Mark blockers immediately and include failing command/context.
3. Mark split complete only after output validation succeeds.

## When to Stop and Ask for Help

Stop when:
- extracted source is unreadable or page markers are broken
- chapter split planners cannot produce a usable config
- split output corrupts structure repeatedly
- navigation regeneration cannot be reconciled safely

## When to Revisit Earlier Steps

Return to earlier steps when:
- source markdown is regenerated
- TOC interpretation changes
- image retention policy changes

## Red Flags

Never:
- use this skill for temporary translation chunking
- invent arbitrary numbered split files when the source has no matching heading
- skip validation before handing results back to the caller
