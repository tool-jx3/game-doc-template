#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "$PROJECT_ROOT"

# --- Glossary stats ---
glossary_stats=$(uv run python - <<'PYEOF' 2>/dev/null || echo "Glossary not yet initialized."
import json
g = json.load(open("glossary.json"))
terms = {k: v for k, v in g.items() if not k.startswith("_") and isinstance(v, dict)}
approved = sum(1 for v in terms.values() if v.get("status") == "approved")
pending  = sum(1 for v in terms.values() if v.get("status") == "pending")
total    = len(terms)
print(f"{total} terms ({approved} approved, {pending} pending)")
PYEOF
)

# --- Style decisions summary ---
style_summary=$(uv run python - <<'PYEOF' 2>/dev/null || echo "(no records yet)"
import json
s = json.load(open("style-decisions.json"))
lines = []
for k, v in s.items():
    if k.startswith("_"):
        continue
    if isinstance(v, dict):
        if "decision" in v:
            lines.append(f"  {k}: {v['decision']}")
        elif "mode" in v:
            lines.append(f"  {k}: {v['mode']}")
print("\n".join(lines) if lines else "(no records yet)")
PYEOF
)

# --- Translation progress ---
# Bounded by design: this hook's output is injected into every session's
# context unconditionally (startup/resume/clear/compact), so listing every
# chapter here would grow without limit as a project's corpus grows. Only
# in_progress items (normally few) print in full; not_started items get a
# capped preview — the full per-file list is one `progress_read.py` call away.
translation_progress=$(uv run python - <<'PYEOF' 2>/dev/null || echo "(translation-progress.json not found — run /init-doc to create it)"
import json
p = json.load(open("data/translation-progress.json"))
chapters = p.get("chapters", [])
if not chapters:
    print("No chapters tracked yet.")
else:
    NOT_STARTED_PREVIEW_LIMIT = 5
    total     = len(chapters)
    completed = sum(1 for c in chapters if c.get("status") == "completed")
    lines = [f"{completed}/{total} chapters completed"]

    in_progress = [c for c in chapters if c.get("status") == "in_progress"]
    not_started = [c for c in chapters if c.get("status") == "not_started"]

    def fmt(c):
        title = c.get("title", c.get("id", "?"))
        fpath = c.get("file", "")
        fname = fpath.split("/")[-1] if fpath else ""
        return f"  {title} ({fname})"

    if in_progress:
        lines.append(f"in_progress ({len(in_progress)}):")
        lines.extend(fmt(c) for c in in_progress)
    if not_started:
        shown = not_started[:NOT_STARTED_PREVIEW_LIMIT]
        lines.append(f"not_started ({len(not_started)}), next {len(shown)}:")
        lines.extend(fmt(c) for c in shown)
        remaining = len(not_started) - len(shown)
        if remaining > 0:
            lines.append(f"  …and {remaining} more (run progress_read.py for the full list)")
    print("\n".join(lines))
PYEOF
)

# --- Escape for JSON string embedding ---
escape_for_json() {
    local s="$1"
    s="${s//\\/\\\\}"
    s="${s//\"/\\\"}"
    s="${s//$'\r'/}"
    s="${s//$'\t'/\\t}"
    s="$(printf '%s' "$s" | awk '{printf "%s\\n", $0}' | sed '$ s/\\n$//')"
    printf '%s' "$s"
}

context=$(cat <<CONTEXT
<project-context>
## Terminology

glossary.json: ${glossary_stats}

Scripts (run from project root):
- Generate term candidates : uv run python scripts/term_generate.py --min-frequency 2
- Calculate evidence (standalone) : uv run python scripts/term_edit.py --term "<TERM>" --cal
- Approve / update term (auto-cal): uv run python scripts/term_edit.py --term "<TERM>" --set-zh "<ZH>" --status approved --mark-term
- Read consistency report   : uv run python scripts/term_read.py
- Batch-calc evidence       : uv run python scripts/term_cal_batch.py
- Update progress           : uv run python scripts/progress_edit.py --file <path> --status <status>
- Read progress report      : uv run python scripts/progress_read.py
- Manage translation drafts : uv run python scripts/draft.py --skill <skill> <path|chunk-path|writeback|clean> [source]
- Record style decision     : uv run python scripts/style_decisions.py <subcommand>

Rules: always run term_read.py before translating; approve new terms before use.

## Style Decisions (style-decisions.json)

${style_summary}

To update: use uv run python scripts/style_decisions.py subcommands (init / set-site / set-translation-mode / ...). Do not edit the JSON by hand.

## Translation Progress (data/translation-progress.json)

${translation_progress}

Completed chapters aren't listed individually here (unbounded as a project grows); use progress_read.py --status completed for the full list.
To update: uv run python scripts/progress_edit.py --file <path> --status <not_started|in_progress|completed>
</project-context>
CONTEXT
)

context_escaped=$(escape_for_json "$context")

cat <<EOF
{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": "${context_escaped}"
  }
}
EOF

exit 0
