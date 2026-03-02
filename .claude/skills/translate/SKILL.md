---
name: translate
description: Start translation - translate a specified section or file
user-invocable: true
disable-model-invocation: true
---

# Translate Document

Use `pdf-translation` and `terminology-management` skills.

## Prerequisites

- `glossary.json` exists with key terms
- Files exist in `docs/src/content/docs/`
- Run `/init-doc` first if not done

## Process

### 0. Terminology Preflight (Required)

Before translating any file:

1. Invoke `terminology-management` skill.
2. Run term read/validation flow:
   - Load `glossary.json`
   - Build or reuse full-site term index
   - Report unknown high-frequency candidates
3. Resolve critical terminology conflicts first, then continue translation.

If available, prefer script flow:

```bash
uv run python scripts/term_read.py
```

### 1. Select Translation Mode

Read `style-decisions.json` and check `translation_mode.mode`:

**If mode is null (not set):**
- Use AskUserQuestion tool to ask user:
  - **Full Translation**: Translate all content completely, preserving the original structure and details
  - **Summary Translation**: Provide a concise translation that extracts key rules and omits examples and lengthy explanations
- Update `style-decisions.json` with user's choice:
  - Set `translation_mode.mode` to `"full"` or `"summary"`
  - Set `translation_mode.reason` to user's reason (if provided)

**If mode is already set:**
- Show current mode setting
- Ask if user wants to change (optional)

### 2. Select Target

If no `$ARGUMENTS`:
- List available files in `docs/src/content/docs/`
- Ask user which to translate

Scope options:
- Single file: `docs/src/content/docs/rules/basic.md`
- Section: `rules` (all files in section)
- All: `all`

### 3. Load Resources

Read:
- `glossary.json` - term mappings
- `style-decisions.json` - style choices
- `style-decisions.json.proper_nouns.mode` - proper noun translation policy selected during `/init-doc`
- `style-decisions.json.document_format` - document formatting standards decided during `/init-doc`

### 4. Translate Content

For each target file:

1. **Read source** - Load current content
2. **Identify segments** - Paragraphs, lists, tables
3. **Apply glossary** - Use consistent terminology
4. **Apply formatting standards** - Format content per `document_format` in `style-decisions.json`
5. **Translate manually** - Perform human translation segment by segment
6. **Preserve structure** - Keep frontmatter, markdown syntax

### Mandatory Translation Constraint

- Translation output must be produced by manual human translation.
- Do not use scripts, regex batch replacement, or find/replace automation to generate translated prose.
- Scripts are allowed only for terminology validation and glossary maintenance (`term_read.py`, `term_edit.py`, schema checks).

### Translation Rules

| Element | Handling |
|---------|----------|
| Frontmatter | Translate `title`, `description`; keep `sidebar` structure |
| Headings | Translate, maintain hierarchy |
| Lists | Preserve formatting, translate content |
| Tables | Keep structure, translate cells |
| Code blocks | Keep unchanged |
| Bold/Italic | Preserve markers |
| Links | Translate text, keep URLs |
| Game terms | Apply glossary strictly |
| Translation method | Manual human translation only; no script-based text replacement |
| Document format | Follow `style-decisions.json.document_format`; use enabled Starlight components per configured mapping; do not use disabled components |

### Mode-Specific Rules

**Full Translation Mode (`full`):**
- Translate all paragraphs, including examples and explanations
- Preserve the original structure without omission
- Suitable for rulebooks requiring complete reference

**Summary Translation Mode (`summary`):**
- Extract core rules and mechanisms
- Omit lengthy examples and replace with concise explanations
- Merge repeated concepts
- Use bullet points to organize key information
- Suitable for quick-reference rule summaries

### Formatting Standards Application (Required)

When `document_format` exists in `style-decisions.json`, apply during translation:

1. **Starlight Asides**: If `starlight_asides.enabled`, convert matching content (tips, warnings, notes, designer commentary) into `:::note`, `:::tip`, `:::caution`, or `:::danger` blocks per the configured `mapping`.
2. **Card Grid**: If `card_grid.enabled`, use `<CardGrid>` + `<Card>` for parallel content (character classes, item lists). Add required Starlight imports.
3. **Tabs**: If `tabs.enabled`, use `<Tabs>` + `<TabItem>` for switchable content. Add required Starlight imports.
4. **Tables**: Follow `tables.use_for` for table formatting decisions.
5. **Dice Tables**: If `dice_tables.enabled`, format random tables with clear roll ranges per configured format.
6. **Additional Guidelines**: Apply rules in `additional_guidelines` array.

If `document_format` does not exist in `style-decisions.json`, fall back to plain Markdown without Starlight components.

### 5. New Terms

When encountering unknown terms:

1. Pause and classify if it is a real game term.
2. If `proper_nouns.mode != keep_original` and it is a proper noun appearing 2+ times in corpus/target scope, it must be treated as a managed term.
3. If yes, run `term_edit.py --cal` first, then update glossary via `term_edit.py`.
4. Re-run terminology read/check (prefer cached index).
5. Continue with updated termbase.

Command pattern:

```bash
uv run python scripts/term_edit.py --term "<TERM>" --cal
uv run python scripts/term_edit.py --term "<TERM>" --set-zh "<ZH>" --status approved --mark-term
uv run python scripts/term_read.py
```

### 6. Write Output

Replace source file with translated version.

### 7. Progress Tracking

After each file:
- Report: `✓ translated: <path>`
- Show next file or completion

## Example Usage

```
/translate
/translate docs/src/content/docs/rules/basic.md
/translate rules
/translate all
```

## Output

Translated files in place, ready for `/check-consistency`.
