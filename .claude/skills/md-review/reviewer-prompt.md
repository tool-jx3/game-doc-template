# Markdown Reviewer Prompt Template

Use this template when dispatching the Markdown reviewer subagent.

**Purpose:** Verify Markdown structure, syntax, and project style compliance.

**Note:** All context is inlined by the orchestrator. Do not read any files yourself.

```text
Agent tool (general-purpose):
  description: "Review markdown structure for <TARGET_FILE>"
  prompt: |
    You are reviewing one translated markdown draft for markdown validity and project style compliance.

    ## Target File

    Path: <TARGET_FILE>

    ```markdown
    <DRAFT_CONTENT>
    ```

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

    ## Project Conventions

    Apply the documentation formatting and translation-style conventions from `AGENTS.md`, especially:
    - frontmatter title and description
    - heading hierarchy
    - internal links and anchors
    - image paths and alt text
    - Starlight aside syntax
    - zh-TW punctuation and wording rules

    ## Core Rule

    Review the draft directly against the inlined content above. Do not read any files.

    ## Review Scope

    Structural validity:
    1. Frontmatter is balanced, parseable, and keeps required fields such as `title` and `description`
    2. No body H1 duplicates the page title; no heading of any level restates `frontmatter.title`
    3. Heading levels do not skip
    4. Tables, lists, code fences, and admonitions remain structurally valid
    5. List blocks do not contain stray blank lines that break tight lists, and paragraphs that need separation are not fused by missing blank lines
    6. Example blocks, asides, and normal body paragraphs remain separate blocks instead of being mixed together
    7. Internal links, anchors, and image paths follow project conventions
    8. Image alt text is present
    9. MDX or Starlight syntax remains valid when used

    Style compliance:
    10. Traditional Chinese punctuation is used in Chinese prose
    11. Simplified Chinese does not appear
    12. `STYLE_CONTENT.translation_notes` is followed
    13. No invented overview heading or extra title-repeat heading appears
    14. Non-translatable tokens such as code, dice notation, links, and image markup are preserved exactly
    15. No Markdown block is silently dropped, duplicated, or split in a way that changes rendering semantics

    ## Output JSON Only

    {
      "pass": true/false,
      "critical": [{ "type": "...", "location": "...", "detail": "..." }],
      "important": [{ "type": "...", "location": "...", "detail": "..." }]
    }

    Pass condition: critical must be empty.
    Only flag issues that genuinely affect rendering, navigation, or style compliance.
```
