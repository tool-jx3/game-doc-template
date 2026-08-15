## 1. Verify the Codex invocation surface

- [x] 1.1 Smoke-test `codex exec -m gpt-5.6-luna -c model_reasoning_effort=low ...` against the installed CLI (codex-cli 0.147.0, ChatGPT-authenticated); if the model name or flag errors, find and record the correct current equivalent. **Verified working as-is** — no substitution needed.
- [x] 1.2 Confirm `-s workspace-write` lets a non-interactive `codex exec` write a file under `.state/<skill>/drafts/...` without additional approval prompts blocking the run. **Confirmed** — file writes completed with no interactive approval blocking; `--skip-git-repo-check` needed only for non-repo working dirs (harmless default otherwise).
- [x] 1.3 Confirm whether a low-effort Codex run can reliably emit the same structured JSON self-check that `super-translate/translator-prompt.md` currently requires. **Confirmed reliable** via `--output-schema <file> -o <result-file>` — Codex returned the exact required shape at low effort. No Claude-side-only fallback needed; `translator-prompt.md` can be reused with this flag pair.
- [x] 1.4 Record the verified, literal invocation shape in one place for reuse. Done: `.claude/skills/translate/codex-tier.md` (shared reference, per user instruction to avoid repeating this across all three skill files).

## 2. Project-level Codex tiering preference

- [x] 2.1 Define the `style-decisions.json` shape for the preference. Done in `codex-tier.md` §1: `{ "codex_tier": { "enabled": true|false } }`.
- [x] 2.2 Added a short pointer to `translate/codex-tier.md` §1 from `translate/SKILL.md` Step 1.
- [x] 2.3 Added a short pointer from `super-translate/SKILL.md` Step 1.
- [x] 2.4 Added a short pointer from `bilingual-translate/SKILL.md` Step 1.

## 3. Codex availability detection and install offer

- [x] 3.1-3.3 Availability check, install-offer flow, and decline-memory handling written once in `codex-tier.md` §2, reused by pointer from all three skills (see Task 2.2-2.4) instead of being repeated per skill.

## 4. Codex-backed draft generation

- [x] 4.1 `translate/SKILL.md` Step 5 (item 4): added a Codex-routed drafting branch pointing to `codex-tier.md` §2-3/§5, with fallback. Self-review (item 5) now explicitly states it's unconditional regardless of draft origin.
- [x] 4.2 `bilingual-translate/SKILL.md` Step 4 (item 3): same treatment, with the bilingual constraint stated explicitly in the delegation instruction — only `<!-- TODO: 翻譯 -->` placeholders may be replaced, `>` lines stay byte-for-byte untouched.
- [x] 4.3 `super-translate/SKILL.md` Step 4 (item 3): added a Codex-routed branch as an alternative to the `Agent`-tool `opus` translator dispatch, with fallback. Reviewer, md-reviewer, and refiner untouched.
- [x] 4.4 **Not needed** — Task 1.3's smoke test confirmed `translator-prompt.md`'s existing required-output JSON shape works directly as Codex's `--output-schema`; no separate Codex-specific prompt file was required.

## 5. Fallback on failure

- [x] 5.1-5.2 Fallback rule written once in `codex-tier.md` §5 (silent per-file fallback to Claude drafting, batch continues), reused by pointer from all three skills instead of being repeated per skill.

## 6. Update supporting documentation in each skill

- [x] 6.1 Updated the `translate` and `super-translate` flowchart node labels to show the Codex-routing branch.
- [x] 6.2 Added a Red Flags row to `translate`, `super-translate`, and `bilingual-translate` — review/reviewer gates are unconditional regardless of draft origin.

## 8. Automated terminology backstop (added post-implementation, per user request)

- [x] 8.1 Fetched the current official PostToolUse/exit-code/`additionalContext` contract from https://code.claude.com/docs/en/hooks.md before designing, per `rcc:fetching-claude-docs`.
- [x] 8.2 Discovered Codex-authored drafts are written via the `Bash` tool (inside `codex exec`'s own process), not `Write`/`Edit` — a `Write|Edit`-matched hook would never see them. Designed the hook to match `Bash` and trigger on `draft.py ... writeback <path>` instead, the one choke point both Codex- and Claude-authored content pass through before landing in published docs.
- [x] 8.3 Wrote `.claude/hooks/terminology-check.py`: single-file check via the project's existing `_term_lib.find_term_spans` (not a full-corpus `term_read.py` scan, which would be slow at real content scale and is already covered at batch boundaries by each skill's own Step 2/Final Verification). Always exits 0; findings surface via `hookSpecificOutput.additionalContext`, never as a blocking/error signal — advisory only, per the user's explicit "warning only, could false-positive" request.
- [x] 8.4 Registered in `.claude/settings.json` (`PostToolUse`, matcher `Bash`, timeout 30).
- [x] 8.5 Tested: fast no-op path for unrelated Bash commands (~0.04s); correctly extracts the writeback target and flags a forbidden-term hit against an isolated test glossary/file; correctly stays silent against the real (currently empty) project glossary; handles empty stdin and malformed JSON without error.
- [x] 8.6 `rcc:hook-reviewer` found one real issue: the warning list was unbounded, risking silent truncation past `additionalContext`'s 10,000-char cap on a large glossary. Fixed — capped to 8 findings + an "N more" summary line, re-tested with 10 simultaneous hits to confirm the cap and summary line both fire correctly. Everything else (exit-code contract, settings.json placement/matcher, no shell injection, safe degradation) verified clean.

## 7. Verification

- [ ] 7.1 Run `/translate` on one real file with tiering enabled and Codex available; confirm the draft is Codex-authored, passes self-review, and writes back correctly. **Pending — this creates a real batch-checkpoint git commit and touches real progress tracking; needs a separate explicit go-ahead before running live rather than being auto-run as part of implementation.**
- [ ] 7.2 Run with tiering disabled; confirm zero Codex CLI invocations and zero Codex-related prompts occur. Same live-run caveat as 7.1.
- [x] 7.3 Forced a Codex failure (invalid model name) in a contained scratchpad test — confirmed a clean non-zero exit code (1) with a parseable error, giving the skill a clean signal to trigger fallback.
- [x] 7.4 `uv run pytest` (372 passed) and the docs JS test suite (63 passed) both green — this change (skill-content only) didn't break anything else.
