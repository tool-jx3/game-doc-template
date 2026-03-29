# Refiner Prompt Template

Use this template when dispatching the refiner subagent.

**Purpose:** Apply translation-review and Markdown-review findings to the draft while preserving correct content.

**Note:** All context is inlined by the orchestrator. Do not read any files yourself.

```text
Agent tool (general-purpose):
  description: "Refine draft for <TARGET_FILE>"
  prompt: |
    You are refining a translated markdown draft using translation-review and Markdown-review findings.

    ## Source File

    Path: <TARGET_FILE>

    ```markdown
    <SOURCE_CONTENT>
    ```

    ## Draft File (current version to fix)

    Path: <DRAFT_FILE>

    ```markdown
    <DRAFT_CONTENT>
    ```

    ## Translation Reviewer Findings

    ```json
    <REVIEW_JSON>
    ```

    ## Markdown Reviewer Findings

    ```json
    <MD_REVIEW_JSON>
    ```

    ## Glossary

    ```json
    <GLOSSARY_CONTENT>
    ```

    ## Style Decisions

    ```json
    <STYLE_CONTENT>
    ```

    ## Rules

    - Fix all critical findings from both review streams first.
    - Preserve already-correct content.
    - Keep markdown structure intact.
    - Treat `frontmatter.title` as the only page title. Remove any added body heading of any level that restates it.
    - If the draft introduced an overview heading that does not exist in the source, remove that heading but keep the translated paragraph content.
    - Preserve image links exactly. If an image belongs inside a paragraph flow, place the same markdown link near the middle of that paragraph and do not split the paragraph around it.
    - Preserve valid frontmatter, heading hierarchy, tables, links, and Starlight syntax.
    - Remove stray blank lines that break list structure, restore required blank lines between paragraphs or blocks, and keep examples or asides separated from surrounding body text.
    - Do not introduce new term variants unless approved in the glossary.
    - If a required term is missing from the glossary, flag it in unresolved issues.
    - Write the updated draft back to <DRAFT_FILE>.

    ## Output JSON Only

    {
      "draft_path": "<DRAFT_FILE>",
      "changes": [{ "location": "...", "summary": "..." }],
      "unresolved": [{ "type": "...", "detail": "..." }]
    }
```
