---
name: pdf-translation
description: Use when processing PDF rulebooks, extracting content, splitting chapters, or preparing translation-ready markdown.
user-invocable: true
disable-model-invocation: true
---

# PDF Translation Workflow

## Overview

Convert a source PDF into structured markdown chapters ready for translation and review.

**Core principle:** Extract cleanly, split deterministically, and verify artifacts before translation starts.

## The Process

### Step 1: Extract PDF

Run:

```bash
uv run python scripts/extract_pdf.py data/pdfs/<filename>.pdf
```

Expected outputs in `data/markdown/`:
- `<name>.md`
- `<name>_pages.md`
- `images/<name>/`

### Step 2: Configure Chapter Mapping

1. Initialize template:

```bash
uv run python scripts/split_chapters.py --init
```

2. Edit `chapters.json` with source file, section order, file titles, and page ranges.

Reference snippet:

```json
{
  "source": "data/markdown/<name>_pages.md",
  "output_dir": "docs/src/content/docs",
  "chapters": {
    "section-slug": {
      "title": "Chapter Title",
      "order": 1,
      "files": {
        "filename": {
          "title": "Page Title",
          "description": "SEO Description",
          "pages": [1, 10],
          "order": 0
        }
      }
    }
  }
}
```

### Step 3: Split to Docs Structure

Run:

```bash
uv run python scripts/split_chapters.py
```

### Step 4: Validate Output Quality

Validate:
- heading continuity
- page coverage completeness
- image path integrity
- frontmatter correctness

Preview if needed:

```bash
cd docs && bun dev
```

### Step 5: Handoff

Hand off generated docs to `/init-doc` or `/translate` pipeline.

## Progress Sync Contract (Required)

1. Track extraction, mapping, and split steps in TodoWrite.
2. Mark split complete only after output validation.

## When to Stop and Ask for Help

Stop when:
- extraction output is unreadable/garbled
- chapter boundaries are ambiguous
- split output corrupts structure repeatedly

## When to Revisit Earlier Steps

Return to Step 2 when:
- chapter strategy changes
- extracted markdown is regenerated

## Red Flags

Never:
- split without validating page markers
- proceed with broken chapter order
- skip output validation before handoff

## Next Step

Continue with `/init-doc` for decisions and tracking setup.
