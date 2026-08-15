# Codex Draft Tier

Shared by `translate`, `super-translate`, and `bilingual-translate`. Reused by relative path from `../super-translate/` and `../bilingual-translate/`.

**Purpose:** delegate draft *generation* (the token-heavy step) to a local Codex CLI when the project has opted in and Codex is usable, while every existing review/writeback gate stays unchanged and unconditional.

## 1. Resolve Codex Tiering Preference (once per project)

Check `style-decisions.json.codex_tier.enabled`.

- **Unset** → ask once, Traditional Chinese: "這個專案要在翻譯草稿階段優先使用本機 Codex（較低階模型、低 effort）以節省 Claude token 嗎？" Persist the answer via the style script (schema-validated — `codex_tier` is a declared schema property; never hand-edit the JSON):
  ```bash
  uv run python scripts/style_decisions.py merge-json --patch '{"codex_tier": {"enabled": true}}'
  ```
  (or `"enabled": false`).
- **Set** → use it silently. Never ask again for this project.
- **`enabled: false`** → skip the rest of this file entirely for every run. Draft generation always happens in the Claude session/subagent, exactly as before this feature existed.

## 2. Codex Availability (only when tiering is enabled)

```bash
node "$(find ~/.claude/plugins/cache/openai-codex -maxdepth 4 -name codex-companion.mjs | head -1)" setup --json
```

Read `.ready`, `.codex.available`, `.auth.loggedIn`.

**If the probe itself fails** — the `find` returns no path (plugin cache absent), `node` is missing, the command exits non-zero, or the output is not parseable JSON — treat it exactly as **not available** below. Never surface the probe error to the user as a run failure; the fallback path exists precisely for this.

- **Available + authenticated** → route drafts to Codex (Section 3).
- **Not available, `npm` available, `codex_tier.install_declined` not set** → `AskUserQuestion`, options `Install Codex (Recommended)` / `Skip for now` (same UX as `codex:setup`). If installed, re-run the check. If declined, record it in the project itself (portable across machines and collaborators, unlike agent memory):
  ```bash
  uv run python scripts/style_decisions.py merge-json --patch '{"codex_tier": {"install_declined": true}}'
  ```
  and proceed on the Claude-only path for this run.
- **Not available, `codex_tier.install_declined: true`** → proceed on the Claude-only path silently. No prompt.
- **Available but `--enabled: false` per Section 1** → unreachable; Section 1 already short-circuited.

## 3. Codex Invocation (verified working shape)

```bash
codex exec \
  -m gpt-5.6-luna \
  -c model_reasoning_effort="low" \
  -s workspace-write \
  -C "<PROJECT_ROOT>" \
  --skip-git-repo-check \
  --output-schema "<SCHEMA_FILE>" \
  -o "<RESULT_FILE>" \
  --json \
  "<PROMPT>" \
  < /dev/null
```

- `-m gpt-5.6-luna` is the verified-working model as of 2026-08 (openspec tasks.md 1.1). Model names churn: if `style-decisions.json.codex_tier.model` is set, use that instead; if the invocation fails with an unknown-model error, find the current equivalent, record it via `merge-json --patch '{"codex_tier": {"model": "<name>"}}'`, and update this file.
- `-C` the actual project root (not a scratch dir) so Codex's writes land in the real `.state/<skill>/drafts/...` path.
- `--skip-git-repo-check` is defensive; harmless when `-C` is already a trusted git repo.
- `<PROMPT>` must inline everything Codex needs — it does not have the calling skill's context. Include: source file content, `glossary.json`, `style-decisions.json` (esp. `translation_notes`), `./translator-style.md` (register, proper-noun policy, POV, terminology glossing, sentence structure), the target draft path to write to, and every hard constraint the calling skill already enforces for Claude-authored drafts (preserve structure, don't restate `frontmatter.title` as a heading, keep dice/code notation untranslated, etc.).
- `<SCHEMA_FILE>` / `<RESULT_FILE>`: when the calling skill needs a structured self-check back (as `super-translate`'s translator step does), write a JSON Schema matching the required shape, pass it via `--output-schema`, and read `<RESULT_FILE>` afterward — ignore the noisy `--json` event stream on stdout; only the schema-constrained file output is reliable. Verified: a low-effort Codex run reliably returns exactly the `translator-prompt.md` structure-check shape this way.
- Read `<RESULT_FILE>` (or the written draft file) only after the process exits; do not parse intermediate stream events.

## 4. Review Gate (unconditional, unchanged)

Whatever generated the draft — Codex or Claude — the calling skill's existing self-review checklist (`translate`, `bilingual-translate`) or reviewer/md-reviewer JSON gate (`super-translate`) runs exactly as before. A Codex-authored draft that fails review is fixed/refined exactly like a Claude-authored one; nothing about draft origin changes review criteria or lets a draft skip straight to writeback.

**Automated backstop:** `.claude/hooks/terminology-check.py` (PostToolUse) fires on both publish paths — after every `draft.py ... writeback` Bash call (translate/super-translate; Codex- and Claude-authored drafts alike), and after every Write/Edit targeting a file under `docs/src/content/docs/` (bilingual-translate publishes final files directly, with no writeback command). It warns (via `additionalContext`, never blocking) if the published file contains a forbidden term variant from `glossary.json` or a machine-detectable structure defect. It can false-positive (e.g. a match inside a code block or proper noun), so treat it as a prompt to double-check, not a verdict.

## 5. Fallback

If the Codex invocation errors, times out, or the process exits non-zero: generate that file's draft directly in the Claude session/subagent instead, and continue the batch. Never surface this as a hard failure to the user — it's a silent per-file fallback.
