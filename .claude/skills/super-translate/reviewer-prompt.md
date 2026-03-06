# Reviewer Prompt Template

Use this template when dispatching the reviewer subagent.

**Purpose:** Verify source fidelity and translation quality in a single pass.

**Note:** All context is inlined by the orchestrator. Do not read any files yourself.

```text
Task tool (general-purpose):
  description: "Review translation for <TARGET_FILE>"
  prompt: |
    You are reviewing a translated markdown draft.

    ## Source File

    Path: <TARGET_FILE>

    ```markdown
    <SOURCE_CONTENT>
    ```

    ## Draft File

    Path: <DRAFT_FILE>

    ```markdown
    <DRAFT_CONTENT>
    ```

    ## Glossary

    ```json
    <GLOSSARY_CONTENT>
    ```

    ## Style Decisions

    ```json
    <STYLE_CONTENT>
    ```

    ## Core Rule

    Verify the draft directly against the source above. Do not read any files.

    ## Review Scope

    Source fidelity:
    1. Missing or truncated content
    2. Meaning drift in mechanics/rules
    3. Glossary violations and forbidden variants

    Quality:
    4. zh-TW readability and tone
    5. Full-width punctuation correctness
    6. Heading/frontmatter/table/dice format integrity

    ## Output JSON Only

    {
      "pass": true/false,
      "critical": [{ "type": "...", "location": "...", "detail": "..." }],
      "important": [{ "type": "...", "location": "...", "detail": "..." }]
    }

    Pass condition: critical must be empty.
    Only flag issues that genuinely affect accuracy or readability.
    Do not nitpick minor stylistic preferences.
```
