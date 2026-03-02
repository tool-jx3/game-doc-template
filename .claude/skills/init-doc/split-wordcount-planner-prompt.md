# Split Wordcount Planner Prompt Template

Use this template when dispatching the split wordcount planner subagent.

**Purpose:** Rebalance TOC-based split draft by word count while keeping TOC order.

```text
Task tool (general-purpose):
  description: "Rebalance split config by wordcount for <SOURCE_PAGES_FILE>"
  prompt: |
    You are rebalancing chapter split config by word count.

    ## Inputs

    - Source pages file: <SOURCE_PAGES_FILE>
    - Draft config path: <DRAFT_CONFIG_PATH>
    - Draft config JSON content (from TOC planner)

    ## Rules

    - Keep TOC order and TOC boundaries as first priority.
    - Adjust split granularity using word count as second priority.
    - Preferred target is roughly 800-2200 words per file.
    - Below 500 or above 2800 words is allowed only with explicit TOC-based reason.
    - Keep config compatible with `scripts/split_chapters.py`.
    - Do not ask user whether to split.

    ## Output JSON Only

    {
      "draft_config_path": "<DRAFT_CONFIG_PATH>",
      "chapters_config": {
        "source": "<SOURCE_PAGES_FILE>",
        "output_dir": "docs/src/content/docs",
        "chapters": {}
      },
      "wordcount_estimate": [{ "file": "section-slug/index", "words": 1200 }],
      "exceptions": [{ "file": "...", "reason": "TOC constraint" }],
      "unresolved_critical": []
    }
```
