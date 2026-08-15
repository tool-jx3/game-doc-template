## Context

See proposal.md - Why. Relevant current state:

- `translate` and `bilingual-translate` generate drafts directly in the main Claude session (recommended model: `sonnet`); `super-translate` dispatches a translator subagent via the `Agent` tool at `model: opus`, with a separate `reviewer` (opus) and `md-review` (haiku) gate, and a `refiner` (sonnet) that repairs failures. All three already write to an isolated draft path (`scripts/draft.py`) before any writeback, and all three already carry a self-review or reviewer-JSON gate before writeback is allowed.
- A local Codex CLI is available on this machine: `codex-cli 0.147.0`, authenticated via ChatGPT login (confirmed via `codex-companion.mjs setup --json`, the same check `codex:setup` performs).
- This project already ships a `codex` plugin with two relevant pieces:
  - `codex:setup` — calls `codex-companion.mjs setup --json` directly; this is a read-only status check, not scoped to any specific subagent.
  - `codex:codex-cli-runtime` — documents `codex-companion.mjs task "<prompt>"` as the way to delegate work to Codex, but is explicitly scoped: "Use this skill only inside the `codex:codex-rescue` subagent." Its contract (forwarder-only, `--write` sandbox by default, model/effort left unset unless the user asks) is built for ad-hoc rescue/diagnosis requests, not for a skill-internal, deterministic draft-generation step.

## Goals / Non-Goals

**Goals:**
- Route draft *generation* (the token-heavy step) for `translate`, `super-translate`, `bilingual-translate` to a local Codex CLI when available, at a fixed low-cost model/effort default.
- Leave every existing review/verification gate exactly as strict as it is today, regardless of draft origin.
- Degrade to today's Claude-only behavior with no user-visible failure whenever Codex isn't usable.

**Non-Goals:**
- Changing `super-translate`'s reviewer, md-reviewer, or refiner agents — those stay Claude-side (opus/haiku/sonnet) exactly as today. Only the translator step is affected.
- Changing `chapter-split`, `term-decision`, or `terminology-management` — out of scope per the proposal.
- Building a general-purpose "any skill can call Codex" framework. This is scoped to the three translation-execution skills' draft step.
- Reusing `codex:codex-rescue` or `codex-companion.mjs task` for the delegation itself (see Decisions) — only its `setup --json` status check is reused.

## Decisions

**1. Invoke `codex exec` directly; do not reuse `codex-companion.mjs task` / `codex:codex-rescue`.**
`codex-cli-runtime` explicitly scopes `task` to the rescue subagent, and that subagent's contract (leave model/effort unset by default, default to `--write` broad-sandbox, "forwarder not orchestrator", no repo inspection outside the forwarded prompt) doesn't fit a skill-internal step that needs deterministic model/effort control and a file-scoped write. Draft generation instead shells out to `codex exec` directly, from within the translate/super-translate/bilingual-translate skill's own process.
*Alternative considered:* dispatch through `codex:codex-rescue` anyway — rejected, since it would silently drop the model/effort control that is the entire point of this change, and would violate that subagent's documented scope.

**2. Reuse `codex-companion.mjs setup --json` for the availability check.**
This is the exact mechanism `codex:setup` already uses, is read-only, and is not scoped to the rescue subagent. It reports `ready`, `codex.available`, and `auth.loggedIn` in one call — sufficient to decide the branch (route to Codex / offer install / fall back silently).

**3. Default model `gpt-5.6-luna`, effort `low`.**
Matches the user's own standing global routing rule ("Translation, formatting, extraction — mechanical single-shot tasks → route with `--model gpt-5.6-luna --effort low`"). `codex exec` has no `--effort` flag directly; effort is set via `-c model_reasoning_effort=<value>` (confirmed from `codex exec --help`; accepted values per `codex-cli-runtime`: none/minimal/low/medium/high/xhigh).
*Risk:* model naming can drift. See Risks below — implementation must smoke-test the literal invocation against the installed CLI before shipping, not assume this name is still valid at apply time.

**4. Sandbox mode: `workspace-write`, scoped to the project's existing draft-isolation paths.**
Codex needs to write the draft file. `workspace-write` (not `danger-full-access`) keeps Codex bounded to the project directory, consistent with the existing draft isolation design (`draft.py` already creates per-skill draft paths under `.state/<skill>/`).

**5. Context inlining, mirroring `super-translate/translator-prompt.md`'s existing pattern.**
`codex exec` takes a single non-interactive prompt — there's no back-and-forth file-reading session the way an `Agent`-dispatched subagent has. The invoking skill must inline source content, `glossary.json`, and `style-decisions.json` into the Codex prompt itself, exactly as `super-translate` already does for its Claude translator subagent. `translate` and `bilingual-translate` currently read files in-session because Claude itself does the drafting; when routing to Codex they adopt the same inline-everything pattern for that call only.

**6. Project-level tiering preference gates everything, asked once before any Codex probing.**
This repo is a template copied by other users via `/new-project`, so "Codex available" cannot be the only gate — some downstream users won't want their translation work routed to Codex at all, regardless of whether it's installed. The skill checks `style-decisions.json` for a Codex tiering preference on its first run in a project; if unset, it asks once and persists the answer (same file/pattern already used for `translation_mode`). If disabled, the skill never probes for Codex, never offers to install it, and always drafts in Claude — for every subsequent run, with no further prompting. If enabled, proceed to availability detection (Decision 7).
*Alternative considered:* gate purely on Codex availability with no persisted preference (the original framing) — rejected once the "template copied by other users" angle surfaced: a user with Codex installed for unrelated work would otherwise have no way to keep this specific project Claude-only.

**7. Install-offer and decline-memory, mirroring `codex:setup`'s existing three-way flow (only reached when tiering is enabled).**
Not installed + npm available + no prior decline on record → ask once (same two options `codex:setup` uses: `Install Codex (Recommended)` / `Skip for now`). Declined → write a **project**-type memory entry (per the auto-memory system's classification: an ongoing decision about this project's tooling, not a cross-project behavioral preference) recording the decline, so later runs in this project skip the *install* prompt specifically — this is independent of the Decision 6 tiering preference, which stays enabled; only the ready-to-actually-invoke branch is affected.

## Risks / Trade-offs

- **Codex draft quality/structure may differ from Claude** (block-shape fidelity, terminology adherence) → Mitigated by the unconditional review gate (spec Requirement: "Claude review gate is unconditional") that already exists for exactly this purpose. A Codex draft that fails review is handled identically to a failing Claude draft — same fix-in-place loop in `translate`/`bilingual-translate`, same refiner loop in `super-translate`.
- **Model/CLI drift**: `gpt-5.6-luna` or the `-c model_reasoning_effort` flag shape may not match the installed Codex CLI by the time this is implemented or in a future environment → Mitigated by requiring a smoke test of the literal command during implementation (tasks.md), and by the fallback-on-failure requirement (spec) — an invocation that errors because of a bad flag/model falls back to Claude rather than hard-failing the run.
- **Added latency** from shelling out to an external process per file vs. in-session generation → Accepted trade-off; the explicit goal is token cost, not wall-clock time.
- **Auth expiry mid-run** (ChatGPT login could lapse) → Covered by the same fallback-on-failure requirement; one file's Codex call failing doesn't abort the batch.
- **`super-translate`'s parallel dispatch** ("2+ independent files → dispatch multiple translator agents concurrently") could mean multiple concurrent `codex exec` subprocesses, risking local resource or Codex-side rate limits → Not fully resolved here; flagged as an implementation-time concern for tasks.md (may need a concurrency cap independent of the existing Claude-subagent concurrency).

## Resolved Questions

- **Per-run opt-out** (e.g., forcing Claude-only for one quality-critical `super-translate` batch): not needed. Confirmed with the user — when tiering is enabled for the project, Codex-first is unconditional for every run; no flag/argument surface added for this.
- **Users who don't want Codex at all**: covered by Decision 6's persisted, per-project tiering preference, asked once on first run and never re-asked — resolves the "template copied by other users" concern the per-run question didn't address.
