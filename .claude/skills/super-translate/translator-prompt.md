# Translator Prompt Template

Use this template when dispatching the translator subagent for one target file.

**Purpose:** Produce a draft translation without overwriting the source file.

**Note:** All context is inlined by the orchestrator. Do not read any files yourself.

```text
Agent tool (general-purpose):
  description: "Translate draft for <TARGET_FILE>"
  prompt: |
    You are translating one markdown file from English to Traditional Chinese (zh-TW).

    ## Source File

    Path: <TARGET_FILE>

    ```markdown
    <SOURCE_CONTENT>
    ```

    ## Glossary

    ```json
    <GLOSSARY_CONTENT>
    ```

    ## Style Decisions

    ```json
    <STYLE_CONTENT>
    ```

    ## Translator Voice & Style

    ```markdown
    <TRANSLATOR_STYLE_CONTENT>
    ```

    ## Hard Constraints

    - Traditional Chinese only (Taiwan usage), no Simplified Chinese.
    - Follow the Translator Voice & Style rules above for register, proper-noun policy, POV, terminology glossing, and sentence structure.
    - Preserve markdown structure exactly. Translate text only; do not normalize, improve, or redesign formatting.
    - Preserve every source block in the same order. A block includes frontmatter, heading, paragraph, list, table, fenced code block, admonition, blockquote, image block, HTML/MDX block, and import line.
    - Preserve frontmatter keys and YAML shape. Translate values when appropriate, but do not add or remove keys.
    - Preserve every heading at the same level. Never add, remove, merge, split, or demote/promote headings.
    - If a source line is a list item, it must remain a list item in the draft. Preserve list nesting and numbering.
    - Preserve required blank lines between adjacent blocks. Do not merge paragraph/list/table/admonition/code blocks into one paragraph. Do not insert stray blank lines that break list continuity.
    - Preserve table shape exactly: same column count, row count, and header/separator structure.
    - Preserve fenced code blocks, MDX imports/components, and admonition fences exactly.
    - Follow every applicable note in `STYLE_CONTENT.translation_notes`.
    - Treat `frontmatter.title` as the page title. Do not restate it anywhere in the body as a heading of any level (`#`, `##`, etc.).
    - If the page opens with an overview/introduction block that has no heading in the source, translate it as plain body content. Do not invent a `#` heading or `## 概覽`.
    - Preserve image links exactly. If an image link is part of a paragraph's source flow, keep the exact markdown link but reposition it near the middle of the translated paragraph; do not split that paragraph into separate blocks before and after the image.
    - Preserve mechanics meaning; no rule drift.
    - Use glossary mappings exactly.
    - Manual translation only (no script-generated prose).
    - Write output to <DRAFT_FILE> only. Do not modify <TARGET_FILE>.

    ## Unknown Terms

    If a term is missing from the glossary, do not guess. Record it in "uncertain_terms".

    ## Required Self-Check Before Writing

    Fix the draft until every item below is true:

    - Heading count and heading levels match the source.
    - No invented heading appears, including title-repeat headings and overview headings.
    - Every source list still renders as a list, with the same item grouping and nesting.
    - Required blank lines between blocks are present, and no stray blank lines break a list.
    - Every source table still has the same shape.
    - No paragraph, list, table, admonition, code fence, or image block was dropped, duplicated, or reordered.

    ## Required Output (JSON)

    {
      "draft_path": "<DRAFT_FILE>",
      "structure_check": {
        "block_order_preserved": true,
        "heading_levels_preserved": true,
        "list_structure_preserved": true,
        "table_shape_preserved": true,
        "required_blank_lines_preserved": true,
        "invented_headings": []
      },
      "uncertain_terms": [
        { "term": "...", "context": "..." }
      ],
      "risk_notes": ["..."]
    }
```
