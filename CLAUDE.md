# game-doc-template

Convert PDF game rulebooks into a Traditional Chinese Markdown documentation site.

## Immutable Laws

<law>

**Law 1: Communication**

- Concise, actionable responses
- No unnecessary explanations
- No summary files unless explicitly requested

**Law 2: Skill Discovery**

- MUST check available skills before starting work
- Invoke applicable skills for specialized knowledge
- If ANY skill relates to the task, MUST use Skill tool to delegate

**Law 3: Convention Consultation**

- When task relates to documentation formatting or translation style, check the "Integrated Conventions" section in this file
- MUST apply the listed conventions

**Law 4: Parallel Processing**

- MUST use Task tool for independent operations
- Batch file searches and reads with agents

**Law 5: Reflexive Learning**

- Important discoveries -> remind user: `/reflect`

**Law 6: Traditional Chinese Only**

- All user-facing outputs must be Traditional Chinese.
- Translation target language is fixed to zh-TW (Taiwan usage).
- Simplified Chinese is not allowed.
- Mainland China-specific wording is not allowed.
- Terminology must remain consistent.

**Law 7: Terminology Consistency**

- Must follow term mappings in `glossary.json`.
- New terms must be added to the glossary before use.
- Preserve source meaning and avoid over-localization.
- Proper noun policy (person/place/org/brand/product names) is user-configurable during `/init-doc`; do not hardcode a single rule.
- Terminology workflow must reuse `.claude/skills/terminology-management/SKILL.md`.
- `/init-doc` and `/translate` must run terminology read/consistency checks first.

**Law 8: zh-TW Writing Conventions**

- MUST use Traditional Chinese punctuation in all user-facing Chinese text（：，。、；「」『』（）……）
- MUST avoid Mainland China-specific wording and prefer Taiwan usage

**Law 9: User Consultation for Complex Terms**

- For rare characters, puns, or culturally nuanced terms, MUST consult user before finalizing terminology decisions when ambiguity affects meaning or tone

**Law 10: Traditional Chinese User Interaction**

- MUST use Traditional Chinese in all user interactions and conversations

</law>

## Quick Reference

### Slash Skills

| Command               | Description                                                           |
| --------------------- | --------------------------------------------------------------------- |
| `/new-project`        | Create a new project from template and set up a private GitHub repo   |
| `/init-doc`           | Initial setup: extract content, pick images/theme, and build glossary |
| `/translate`          | Translate a specific section or file                                  |
| `/check-consistency`  | Validate terminology consistency                                      |
| `/term-decision`      | Make terminology decisions and batch replace                          |
| `/check-completeness` | Check for missing rule content                                        |

### Tech Stack

- **Frontend**: Astro 5 + Starlight (bun/npm)
- **Scripts**: Python 3.11+ (uv)
- **PDF Processing**: markitdown, pymupdf

### Key Paths

| Path                                             | Description                                        |
| ------------------------------------------------ | -------------------------------------------------- |
| `docs/`                                          | Astro documentation site                           |
| `docs/src/content/docs/`                         | Markdown content                                   |
| `scripts/`                                       | Python processing scripts                          |
| `data/pdfs/`                                     | Source PDF files                                   |
| `data/markdown/`                                 | Extracted Markdown                                 |
| `data/markdown/images/`                          | Extracted images                                   |
| `glossary.json`                                  | Terminology glossary                               |
| `style-decisions.json`                           | Style decision records                             |
| `.claude/skills/terminology-management/SKILL.md` | Terminology interaction skill (edit/generate/read) |

### Terminology Scripts

- Generate candidates: `uv run python scripts/term_generate.py --min-frequency 2`
- Calculate evidence before editing unmanaged term: `uv run python scripts/term_edit.py --term "<TERM>" --cal`
- Approve/update term: `uv run python scripts/term_edit.py --term "<TERM>" --set-zh "<ZH>" --status approved --mark-term`
- Read consistency report: `uv run python scripts/term_read.py`
- Validate glossary schema: `uv run python scripts/validate_glossary.py`

### Data File Formats

**glossary.json**

```json
{
  "english_term": {
    "zh": "Traditional Chinese translation",
    "notes": "Usage context or notes"
  }
}
```

**style-decisions.json**

```json
{
  "category": {
    "decision": "Selected wording",
    "alternatives": ["Other options"],
    "reason": "Reason for the choice"
  }
}
```

### Workflow

1. Use `new-project` skill to initialize a new project (when needed)
2. Use `init-doc` skill to complete extraction, chapter structuring, and initial terminology mapping
3. Use `term-decision` skill to handle terminology decisions and batch replacements
4. Use `translate` skill to translate target chapters or files
5. Use `check-consistency` skill to validate terminology and style consistency
6. Use `check-completeness` skill to check rule content completeness

## Integrated Conventions

### Scope

- Applies to: `docs/src/content/docs/**/*.md`

### Markdown Format

#### Frontmatter

```yaml
---
title: 頁面標題
description: SEO 描述（一句話）
sidebar:
  order: 0 # Lower = higher position
---
```

#### Headings

- H1: Reserved for title (from frontmatter)
- H2: Main sections
- H3: Subsections
- Never skip levels (H2 → H4)

#### Links

- Internal: `/rules/combat/` (absolute from docs root)
- Cross-reference: `[基本動作](/rules/basic-moves/)`
- Anchor: `[見下方](#section-name)`

#### Images

- Path: `../../assets/image-name.jpg` (relative from .md)
- Alt text: Always provide descriptive alt
- Store in: `docs/src/assets/`

#### Starlight Components

- Asides: `:::note[標題]`, `:::tip`, `:::caution`, `:::danger`
- Cards: Import from `@astrojs/starlight/components`
- Tabs: Use for alternative content views

#### Tables

- Use for structured data, stats, quick reference
- Keep columns concise
- Align consistently

#### Dice Tables

- Use Markdown tables for random encounters and loot generation
- Include clear roll ranges (e.g., `1-2`, `3-4`, `5-6`) with no overlaps or gaps
- Prefer `1d6`, `1d20`, `2d6` notation and preserve source probability structure
- Add notes when reroll rules, duplicate handling, or conditional entries are required

### Translation Style

#### Language

- Use Traditional Chinese (繁體中文) exclusively
- Never use Simplified Chinese characters
- Maintain formal but accessible tone

#### Punctuation

- Use full-width punctuation：，。、；：「」『』（）
- Use half-width for: numbers, English, code
- Ellipsis: use `……` (two full-width), not `...`

#### Numbers

- Use Arabic numerals for: dice (2d6), stats, page refs
- Use Chinese for: 一個、兩次、三種 in prose
- Keep original notation: +1, -2, 1d6+3

#### Proper Nouns

- Check `glossary.json` first
- Game titles: use official Chinese name if exists
- Character/proper-name handling: follow `style-decisions.json` policy selected by user during `/init-doc`
- Record decisions in `style-decisions.json`

#### Mechanics Terms

- Maintain consistency across all documents
- Prioritize clarity over literal translation
- Add glossary entry before first use

#### Culturally Nuanced Terms

- For rare characters, puns, and culturally loaded wording, propose 2-3 candidate translations with brief rationale
- If options change tone, setting implications, or mechanics interpretation, ask user to decide before finalizing glossary entries
