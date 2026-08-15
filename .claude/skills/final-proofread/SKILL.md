---
name: final-proofread
description: Use when performing final quality checks before publishing the documentation site. Use when all translation is complete and you need to verify titles/descriptions are translated, check for misplaced or erroneous content, run page-reference link checks, and verify the search index.
user-invocable: true
disable-model-invocation: true
---

# Final Proofread

## Overview

Four-gate quality sweep over all translated documentation: (1) frontmatter completeness, (2) content integrity, (3) page-reference link audit, (4) search index verification.

**Core principle:** No gate skipped. All findings must be reported before the run closes.

## Task Initialization (MANDATORY)

Before ANY action, create tasks using TaskCreate:
- One task per gate (Gate 1, Gate 2, Gate 3, Gate 4)
- One task for consolidated report
- One task for fix verification

Announce: "Created 6 tasks. Starting execution..."

## The Process

### Step 1: Resolve Scope and Preconditions

1. Resolve translation mode (mode-aware preflight):
   1. 讀取 `style-decisions.json` 的 `translation_mode.mode`。
   2. `mode == "bilingual"` 時：進度檔為 `data/translation-progress-bilingual.json`，內容根目錄為 `docs/src/content/docs/bilingual/`；`progress_read.py` 需帶 `--progress-file data/translation-progress-bilingual.json`。
   3. 其他模式：維持 `data/translation-progress.json` 與 `docs/src/content/docs/`。

   Everywhere below, **the progress file** and **the content root** refer to the values resolved here.

2. Verify required files exist:
   - `glossary.json`
   - `style-decisions.json`
   - the progress file
   If any are missing, stop and ask user to run `/init-doc` first.

3. Default scope: `<content root>**/*.md`
   If `$ARGUMENTS` specifies a narrower path, restrict scope accordingly.

4. Load translation progress:
   ```bash
   uv run python scripts/progress_read.py --json --progress-file <progress file>
   ```
   (Omit `--progress-file` only when the progress file is the default `data/translation-progress.json`; `progress_read.py` falls back to it automatically.)
   Identify:
   - Files with status `completed` — primary audit targets.
   - Files with status `not_started` or `in_progress` — flag as incomplete, exclude from Gates 2–3 unless user asks to include them.

**Verification:** Mode resolved; scope resolved against the content root; progress data loaded from the progress file.

### Gate 1: Frontmatter & Site Config Completeness Check

**Goal:** Every user-facing label and description is translated to Traditional Chinese.

#### 1a. Site Configuration Files

Check the following files for untranslated English (proper nouns in `glossary.json` or `style-decisions.json` are exceptions):

1. **`docs/astro.config.mjs`** — sidebar `label` values:
   - Each sidebar group `label` must be in Traditional Chinese → untranslated English **FAIL**
2. **`docs/src/content/docs/index.mdx`** (or `index.md`) — 全站首頁，與翻譯模式無關，固定於此路徑（不隨 Step 1 解析出的 content root 變動）— homepage elements:
   - Hero `actions[].text` values → untranslated English **FAIL**
   - `<LinkCard>` / `<Card>` `title` attributes → untranslated English **FAIL**
   - `<LinkCard>` / `<Card>` `description` attributes → untranslated English **WARN**

#### 1b. Page Frontmatter

For each Markdown/MDX file in scope:

1. Parse frontmatter block.
2. Check `title`:
   - Missing or empty → **FAIL**
   - Contains any untranslated English (except proper nouns in `glossary.json` or `style-decisions.json`) → **WARN**
3. Check `description`:
   - Missing or empty → **FAIL**
   - Contains any untranslated English (same exceptions) → **WARN**
4. Check `sidebar.label` if present — same rules apply.

Collect all FAILs and WARNs. Do not stop early.

**Verification (Gate 1):** All files scanned (site config + page frontmatter); findings list produced. Mark Gate 1 task `completed`.

### Gate 2: Content Integrity Check

**Goal:** Detect misplaced, duplicated, or erroneous content that breaks documentation integrity.

For each file in scope:

1. **Duplicate headings:** Check for identical heading text at the same level within a file. Report duplicates.
2. **Heading hierarchy violations:** Detect heading level skips (e.g., H2 → H4). Report each violation with file and line.
3. **Orphan content blocks:** Check for English prose in body text (outside code blocks, dice notation, proper nouns approved in glossary). Any untranslated body text → **FAIL**.
4. **Broken internal links:** For each Markdown link matching `/...` pattern, confirm the target route exists under the content root. Report broken links.
5. **Image path validity:** For each image reference, confirm the file exists at the resolved path. Report missing images.
6. **Frontmatter title restated as body heading:** If the body contains an H1 (`#`) that matches `frontmatter.title`, report it as a violation.

Do not auto-fix any finding in this gate. Collect all issues for the consolidated report.

**Verification (Gate 2):** All integrity checks complete; findings list produced. Mark Gate 2 task `completed`.

### Gate 3: Page Reference Audit

**Goal:** Confirm no printed page-number references remain in the documentation.

Scan all in-scope files for page-reference patterns:

- `第 N 頁` / `第N頁` / `見第 N 頁` / `參見 N 頁`
- `page N` / `pages N-N` / `p. N` / `pp. N-N`
- `12 page` / `P.N`

For each match:
1. Classify as **navigational** (needs `fix-ref`) or **non-navigational** (literal citation, print layout note, or index entry that is not a reader navigation cue).
2. Record navigational matches as Gate 3 FAILs with file and line.
3. If any navigational matches are found, invoke the `fix-ref` skill inline:

   ```
   Invoke fix-ref skill for the files with navigational page references.
   ```

**Verification (Gate 3):** Scan complete; all navigational page refs resolved or escalated. Mark Gate 3 task `completed`.

### Gate 4: Search Index Verification

**Goal:** Confirm the zh-TW search layer works on the final build (see `docs/search/README.md`).

1. Build the site with search post-processing, then run the acceptance script:

   ```bash
   cd docs && bun install && bun run build && bun run verify-search
   ```

2. If `docs/search/verify-cases.json` does not exist, the script runs generic checks only (segmentation health, term-in-vocab rate) and prints a hint. In that case, propose corpus-specific cases to the user following the「驗收（verify-search）」section of `docs/search/README.md`, and create the file once confirmed.
3. Record every verify-search failure line as a Gate 4 FAIL. Do not adjust thresholds to make failures pass; threshold changes require user confirmation.

**Verification (Gate 4):** verify-search exited 0, or all failures are recorded as findings. Mark Gate 4 task `completed`.

### Step 2: Consolidated Report

Produce a single report in Traditional Chinese:

```markdown
## 最終校對報告

### Gate 1 — Frontmatter 與站台設定完整性
#### FAIL（必須修復）
- `astro.config.mjs`: sidebar label "Introduction" 未翻譯
- `index.mdx`: hero action "Introduction" 未翻譯
- `index.mdx`: LinkCard title "Combat & Damage" 未翻譯
- `<file>`: title 缺失 / description 為英文
#### WARN（建議修復）
- `index.mdx`: LinkCard description 含未翻譯英文
- `<file>`: description 含未翻譯英文詞彙

### Gate 2 — 內容完整性
#### 重複標題
- `<file>` 第 N 行：重複標題 "..."
#### 標題層級跳躍
- `<file>` 第 N 行：H2 → H4
#### 未翻譯英文段落
- `<file>` 第 N 行：...
#### 斷裂內部連結
- `<file>`: `/rules/missing-route/`
#### 缺失圖片
- `<file>`: `../../assets/missing.png`
#### 標題重複於文章首行
- `<file>` 第 N 行：H1 與 frontmatter.title 相同

### Gate 3 — 頁碼參照
#### 已修復
- (fix-ref 已處理的項目列表)
#### 待確認（非導航性）
- `<file>` 第 N 行：`page 3`（疑似非導航性，請確認）

### Gate 4 — 搜尋驗收
#### FAIL（必須處理）
- `verify-search`：「<查詢>」回傳 N 筆，超過上限 M
#### 提示
- 尚未建立 `docs/search/verify-cases.json`，僅執行通用檢查

### 整體結論
- Gate 1: X 個 FAIL，Y 個 WARN
- Gate 2: X 個問題
- Gate 3: X 個已修復，Y 個待確認
- Gate 4: 驗收通過／X 個 FAIL
```

Mark consolidated report task `completed`.

### Step 3: Fix Verification

For each FAIL that was auto-fixed (Gate 3 via `fix-ref`):

1. Re-scan the edited files to confirm the pattern no longer appears.
2. Confirm all internal links introduced by `fix-ref` resolve correctly.

For FAILs that require manual intervention (Gate 1, Gate 2):

1. Ask user in Traditional Chinese for each FAIL item.
2. Apply agreed fixes directly.
3. Re-scan the affected file after each fix.

After all fixes are applied:

```bash
uv run python scripts/validate_glossary.py
uv run python scripts/term_read.py --fail-on-missing --fail-on-forbidden
```

Mark fix verification task `completed`.

## Red Flags

| Thought | Reality |
|---------|---------|
| "Skip Gate 2, translations look fine" | Heading violations and broken links are invisible without scanning. NEVER skip. |
| "I'll fix as I scan instead of reporting first" | Collect all findings first; fix in Step 3. No interleaving. |
| "This English looks like a proper noun, skip it" | Check `glossary.json` and `style-decisions.json` first. If not listed, it is a WARN. |
| "fix-ref already ran before, Gate 3 must be clean" | Always re-scan. New pages may have been added since. |
| "Gate 3 matches look non-navigational" | Classify explicitly and report. Never silently drop a match. |
| "The description only has a game title in English" | Check `style-decisions.json` proper noun policy. If no exception, report as WARN. |
| "Site config and homepage are not translation targets" | Sidebar labels, hero buttons, and card titles are user-facing. They MUST be checked in Gate 1a. |

## When to Stop and Ask

Stop when:
- A Gate 2 broken link cannot be mapped to any existing route.
- A Gate 3 reference is ambiguous (navigational vs. non-navigational is unclear).
- A Gate 1 FAIL involves a term that is not yet in the glossary and requires a user decision.
- A Gate 4 failure looks like an outdated threshold rather than a search regression (content changed since the case was written) — threshold changes need user confirmation.

## Example Usage

```text
/final-proofread
/final-proofread docs/src/content/docs/rules/
```
