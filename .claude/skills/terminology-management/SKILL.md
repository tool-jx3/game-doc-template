---
name: terminology-management
description: 術語互動管理與一致性檢查。Use when creating/editing glossary terms, reading terms with site-wide validation, or making terminology decisions.
---

# Terminology Management

## Glossary Structure

Location: `glossary.json` (project root)

```json
{
  "Move": {
    "zh": "動作",
    "notes": "PbtA 系統核心機制"
  },
  "Playbook": {
    "zh": "劇本",
    "notes": "角色模板，也可譯為「職業書」"
  }
}
```

## Interactive Workflow (Required)

When this skill is invoked, always run this loop:

1. **Generate candidates**: run `term_generate.py` on target corpus.
2. **CAL first for unmanaged terms**: run `term_edit.py --cal --term "<term>"` before editing.
3. **Classify term candidates**: decide whether each candidate is a real game term or normal prose.
   - If `style-decisions.json -> proper_nouns.mode != keep_original`, any proper noun that appears `>=2` times must be classified as a managed term.
4. **Edit termbase**: add/update/disable terms with reasons via `term_edit.py`.
5. **Read and validate**: run `term_read.py` to report missing/forbidden/unknown terms.

Important:
- If a term is already marked as managed in `glossary.json`, `term_edit.py --cal` skips full-site search for that term.
- For unmanaged terms, editing requires `--cal` first unless `--force` is explicitly used.
- Re-run full-site search only when content fingerprint changes.
- Term matching backend:
  - Prefer `spaCy` lemma matching when installed.
  - Fallback to `inflect`-based singular/plural matching when `spaCy` is unavailable.

## Suggested Script Contract

Use script-driven operations under `scripts/`:

- `term-edit`: interactive create/update for glossary entries
- `term-generate`: discover high-frequency term candidates from docs
- `term-read`: load glossary + validate usage with cached index

Example invocation pattern:

```bash
uv run python scripts/term_read.py
uv run python scripts/term_generate.py --min-frequency 2
uv run python scripts/term_edit.py --term "Stress" --cal
uv run python scripts/term_edit.py --term "Stress" --set-zh "壓力" --status approved --mark-term
```

## Operations

### Add Term

1. Check if term exists in glossary
2. If new, run `--cal` first, then add with translation and context notes
3. Update all existing documents with new term

### Check Consistency

Run `term_read.py` on all `.md` files in target root:

1. Extract English terms (capitalized words, quoted terms)
2. Cross-reference with `glossary.json`
3. Report:
   - Missing terms (not in glossary)
   - Inconsistent usage (same term, different translations)
   - Untranslated terms (English in final output)

### Batch Replace

When terminology decision is made:

1. Record in `style-decisions.json`
2. Find all occurrences across docs
3. Replace with consistent translation
4. Verify no orphaned terms remain

## Style Decisions

Location: `style-decisions.json` (project root)

```json
{
  "dice_notation": {
    "decision": "保留原文",
    "alternatives": ["翻譯為中文"],
    "reason": "2d6 等骰子標記為國際通用，保留更清晰"
  },
  "game_title": {
    "decision": "使用官方中文名",
    "alternatives": ["音譯", "意譯"],
    "reason": "遵循官方授權翻譯"
  }
}
```

## Consistency Report Format

```markdown
## Terminology Report

### Missing from Glossary
- `Harm` (found in: combat.md:15, conditions.md:23)
- `Hold` (found in: basic-moves.md:42)

### Inconsistent Usage
- `Move`: "動作" (5x), "行動" (2x)
  - Files: rules/index.md, combat.md

### Untranslated
- "Experience" in characters/advancement.md:18
```

## Priority Categories

| Category | Handling |
|----------|----------|
| Core mechanics | Must be consistent, add to glossary first |
| Proper nouns | If `proper_nouns.mode != keep_original` and frequency `>=2`, must be added to glossary and managed consistently; check official translations and record decision |
| Flavor text | More flexible, prioritize readability |
| UI/System terms | Match Starlight conventions |
