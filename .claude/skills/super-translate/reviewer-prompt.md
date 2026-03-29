# Reviewer Prompt Template

Use this template when dispatching the reviewer subagent.

**Purpose:** Verify source fidelity and translation quality in a single pass.

**Boundary:** Markdown structure and style compliance run in a separate `md-review` gate.

**Note:** All context is inlined by the orchestrator. Do not read any files yourself.

```text
Agent tool (general-purpose):
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
    4. Content contamination — content that belongs to another page or section must not appear in this draft; flag any paragraph or block that has no corresponding source in `<SOURCE_CONTENT>`
    5. Untranslated English — every English word in the draft that is not a proper code/notation/dice expression (e.g. `1d6`, `+2`) must be translated; this includes: body text, headings, table cells, game labels (status conditions, item tags, rule keywords/phrases such as "Stunned", "Heavy", "Ongoing", "Hold"); terminology must follow `<GLOSSARY_CONTENT>`; proper nouns must follow the policy in `<STYLE_CONTENT>` (if `proper_nouns.mode == keep_original`, untranslated proper nouns are allowed)

    Quality:
    6. zh-TW readability and tone
    7. Full-width punctuation correctness
    8. Heading/frontmatter/table/dice format integrity
    9. No added heading of any level that restates `frontmatter.title`, and no invented overview heading when the source has no such heading
    10. Image links are preserved exactly and, when they belong to a paragraph flow, remain inside one paragraph instead of splitting it into separate blocks

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
