# Refiner Prompt Template

Use this template when dispatching the refiner subagent.

**Purpose:** Apply reviewer findings to the draft while preserving correct content.

**Note:** All context is inlined by the orchestrator. Do not read any files yourself.

```text
Task tool (general-purpose):
  description: "Refine draft for <TARGET_FILE>"
  prompt: |
    You are refining a translated markdown draft using reviewer findings.

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

    ## Reviewer Findings

    ```json
    <REVIEW_JSON>
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

    - Fix all critical findings first.
    - Preserve already-correct content.
    - Keep markdown structure intact.
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
