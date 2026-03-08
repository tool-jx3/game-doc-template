# Split Planner Prompt Template

Use this template when dispatching the split planner subagent.

**Purpose:** Produce an initial deterministic split config draft based on source TOC landmarks.

```text
Task tool (general-purpose):
  description: "Draft chapter split config for <SOURCE_PAGES_FILE>"
  prompt: |
    You are planning chapter split configuration for one extracted markdown source.

    ## Inputs

    - Source pages file: <SOURCE_PAGES_FILE>
    - Draft config output path: <DRAFT_CONFIG_PATH>
    - style-decisions.json (document_format, proper_nouns)

    ## Hard Constraints

    - Do not ask the user whether to split.
    - Build config compatible with `scripts/split_chapters.py`.
    - Use lowercase kebab-case ASCII for section/file slugs.
    - Use semantic TOC-derived or heading-derived slugs for every file.
    - Never invent generic numeric-only file slugs or titles such as `1`, `2`, `3`, `part-1`, `part-2`, `一`, `二`, or `三` unless the source itself uses that numbered label as the real heading.
    - Preserve TOC order from source.
    - Use contiguous, non-overlapping page ranges derived from TOC boundaries.
    - If splitting is not necessary, produce one section with one `index` file covering full range.
    - When a long chapter needs internal subdivision, prefer nested semantic file paths in `files` (for example `combat/damage`) so output can use subdirectories without changing the top-level section grouping.

    ## Critical: Page Number Mapping

    Page numbers in `pages` arrays MUST be PDF physical page numbers matching `<!-- PAGE N -->` markers in the source file, NOT print page numbers from the book's TOC or footer.

    To determine correct page numbers:
    1. Scan the source file for `<!-- PAGE N -->` markers.
    2. Find which PAGE marker contains each TOC heading or section start.
    3. Use THAT marker number as the page number.

    Print page numbers and PDF page numbers often differ (e.g., cover, TOC, or blank pages shift the offset). Always verify by locating the actual heading text within the `<!-- PAGE N -->` block.

    ## Planning Basis

    - Basis is source TOC structure and heading landmarks.
    - Prefer actual subordinate headings from the source over arbitrary page-count splits.
    - Avoid purely semantic refactoring not present in source TOC.
    - If a chapter is long but lacks trustworthy subordinate headings, keep it as one file and report that risk instead of fabricating numbered parts.

    ## Required Output (JSON Only)

    {
      "draft_config_path": "<DRAFT_CONFIG_PATH>",
      "chapters_config": {
        "source": "<SOURCE_PAGES_FILE>",
        "output_dir": "docs/src/content/docs",
        "chapters": {
          "section-slug": {
            "title": "...",
            "order": 1,
            "files": {
              "index": {
                "title": "...",
                "description": "...",
                "pages": [1, 10],
                "order": 0
              },
              "subtopic-slug/detail-slug": {
                "title": "...",
                "description": "...",
                "pages": [11, 16],
                "order": 1
              }
            }
          }
        }
      },
      "planning_notes": ["..."],
      "toc_evidence": [{ "toc_item": "...", "start_page": 1, "end_page": 10 }],
      "risk_notes": ["..."]
    }
```
