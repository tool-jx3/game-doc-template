# game-doc-template 全面整修 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 依據 `plans/2026-07-26-project-overhaul-design.md`（已核准 spec）修復模板專案的建置失敗、hooks 失效、技能斷鏈與模板汙染，使 `bun run build` 與 `uv run pytest` 全綠、`clean_sample_data.py --yes` 冪等產出乾淨空白模板。

**Architecture:** 四階段（Phase A 基礎修復 → B 模板清空 → C 技能系統 → D 腳本/測試/CI/安全），每階段內任務可依序獨立驗證與 commit。Phase A 先修 hooks 避免後續開發被壞 hook 干擾；Phase B 先擴充清理腳本再用它產生空白狀態；Phase C 純文件/技能檔編輯；Phase D 含 TDD 的 Python 修復與安全重寫。

**Tech Stack:** Python 3.13（uv）、pytest、Astro 5 + Starlight（bun）、Vercel Edge Functions（Web Crypto）、bash hooks。

## Global Constraints

- 工作分支：`fix/project-review`（已存在，勿另開分支）。
- 所有使用者可見文字一律繁體中文（zh-TW、台灣用語、全形標點）；程式碼註解沿用各檔既有語言。
- Python 慣例遵循 `.claude/rules/python.md`：新檔案首行 import 為 `from __future__ import annotations`；用 `PROJECT_ROOT = Path(__file__).resolve().parents[1]`；所有 `open()`/`read_text()`/`write_text()`/`subprocess.run(text=True)` 必須帶 `encoding="utf-8"`。
- 不新增任何第三方相依（Python 與 npm 皆同）。
- 測試指令一律 `uv run pytest`（testpaths 為 `scripts/tests`）；docs 建置一律 `cd docs && bun run build`。
- `.github/template.yml` 不得修改。
- 每個 commit 訊息結尾附上：

  ```
  Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01US3TEe1Pu3mFHCjjwzq8Fg
  ```

- 注意：`PostToolUse` pytest hook 在 Task 2 完成前對任何 `.py` 編輯都會觸發全樹掃描並可能超時輸出錯誤——那是已知的待修 bug，忽略其 stderr 即可，不要因此改變實作。
- 計畫中的單行 `git commit -m "..."` 為簡寫；實際執行時一律改為多行訊息，於結尾附上上述兩行 trailer。
- 模型路由決策（寫入技能檔時照抄）：super-translate translator=**opus**、reviewer=**opus**、refiner=**sonnet**、md-review 子代理=**haiku**；`/translate` 與 `/bilingual-translate` 為主執行緒流程，加註「建議於 sonnet 會話執行」。

---

## Phase A：基礎修復

### Task 1: settings.json 清理與既有修正入庫

**Files:**
- Modify: `.claude/settings.json`
- Delete: `.claude/hooks/permission-check.py`
- Commit（一併收下工作區既有修正）: `.python-version`（已是 `3.13`）

**Interfaces:**
- Produces: settings.json 僅剩 SessionStart 與 pytest-check 兩個 hook；pytest hook `timeout: 60`（Task 2 依賴）。

- [ ] **Step 1: 改寫 `.claude/settings.json`** — 移除 `matcher: "Agent"` 整個區塊、pytest hook timeout 提高為 60。完整新內容：

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "startup|resume|clear|compact",
        "hooks": [
          {
            "type": "command",
            "command": "bash \"$CLAUDE_PROJECT_DIR/.claude/hooks/session-start.sh\"",
            "async": false
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "uv run python \"$CLAUDE_PROJECT_DIR/.claude/hooks/pytest-check.py\"",
            "timeout": 60
          }
        ]
      }
    ]
  }
}
```

- [ ] **Step 2: 刪除 `.claude/hooks/permission-check.py`**（`git rm`）。
- [ ] **Step 3: 驗證** — `git diff` 確認 `.python-version` 內容為 `3.13`；`python -c "import json;json.load(open('.claude/settings.json'))"` 通過。
- [ ] **Step 4: Commit**

```bash
git add .claude/settings.json .python-version
git rm .claude/hooks/permission-check.py
git commit -m "fix: remove broken permission-check hook, align python version to 3.13"
```

### Task 2: 修復 pytest-check.py

**Files:**
- Modify: `.claude/hooks/pytest-check.py`

**Interfaces:**
- Produces: hook 只對 `scripts/` 下的 `.py` 觸發；內部 pytest timeout 45 秒。

- [ ] **Step 1: 套用四處修改**：
  1. 刪除第 10 行 `import os`（未使用）。
  2. `is_python_file_change()` 的結尾改為（只對 scripts/ 觸發）：

```python
    if not file_path.endswith('.py'):
        return False
    normalized = file_path.replace('\\', '/')
    return '/scripts/' in normalized or normalized.startswith('scripts/')
```

  3. `has_test_files()` 整個函式改為（不再全樹遍歷）：

```python
def has_test_files() -> bool:
    """Check if scripts/tests contains any test files."""
    tests_dir = Path.cwd() / "scripts" / "tests"
    if not tests_dir.is_dir():
        return False
    return any(tests_dir.glob("test_*.py"))
```

  4. `run_pytest()` 中 `timeout=15` 改為 `timeout=45`，且對應的 TimeoutExpired 訊息改為 `"Pytest timeout (45s) - tests may be hanging or too slow"`。

- [ ] **Step 2: 手動驗證觸發判斷**：

```bash
echo '{"tool_name":"Edit","tool_input":{"file_path":"D:/x/README.md"}}' | uv run python .claude/hooks/pytest-check.py; echo "exit=$?"
echo '{"tool_name":"Edit","tool_input":{"file_path":"D:/Code/trpg-doc/game-doc-template/scripts/term_read.py"}}' | uv run python .claude/hooks/pytest-check.py; echo "exit=$?"
```

Expected: 第一條 exit=0 立即返回；第二條實際跑 pytest（scripts/tests 現有測試應全綠，exit=0）。

- [ ] **Step 3: Commit** — `git add .claude/hooks/pytest-check.py && git commit -m "fix: scope pytest hook to scripts/, align timeouts"`

### Task 3: 修復 session-start.sh

**Files:**
- Modify: `.claude/hooks/session-start.sh`

- [ ] **Step 1: 套用六處修改**：
  1. 三處 heredoc 呼叫 `python3 -` 全部改為 `uv run python -`（第 9、21、38 行）。
  2. 移除幻影狀態：`status_icon` 映射中刪除 `"reviewed":    "★",` 一行；`completed` 統計改為 `sum(1 for c in chapters if c.get("status") == "completed")`；第 97 行圖例改為 `Status legend: · not_started  ▶ in_progress  ✓ completed`。
  3. 第 91 行改為：`To update: use uv run python scripts/style_decisions.py subcommands (init / set-site / set-translation-mode / ...). Do not edit the JSON by hand.`
  4. 第 98 行改為：`To update: uv run python scripts/progress_edit.py --file <path> --status <not_started|in_progress|completed>`
  5. Scripts 清單（第 80-83 行區塊）補三行：

```
- Batch-calc evidence       : uv run python scripts/term_cal_batch.py
- Update progress           : uv run python scripts/progress_edit.py --file <path> --status <status>
- Record style decision     : uv run python scripts/style_decisions.py <subcommand>
```

  6. 輸出 JSON 移除重複鍵：`cat <<EOF` 區塊改為只輸出 `hookSpecificOutput`：

```bash
cat <<EOF
{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": "${context_escaped}"
  }
}
EOF
```

  7. `escape_for_json()` 在反斜線/引號處理後補兩行（CR 移除、tab 跳脫）：

```bash
    s="${s//$'\r'/}"
    s="${s//$'\t'/\\t}"
```

- [ ] **Step 2: 驗證** — `bash .claude/hooks/session-start.sh | uv run python -c "import json,sys; d=json.load(sys.stdin); print(d['hookSpecificOutput']['additionalContext'][:120])"`。Expected: 合法 JSON，且 context 顯示 glossary 實際條目數（目前為 26 terms），不再是「Glossary not yet initialized」。
- [ ] **Step 3: Commit** — `git commit -am "fix: session-start hook uses uv, correct guidance, drop phantom reviewed status"`

### Task 4: 版控衛生

**Files:**
- Modify: `.gitignore`、`gh-clone.sh`
- Untrack: `.claude/settings.local.json`

- [ ] **Step 1: `.gitignore` 修改**：
  1. `data/pdfs/` 與 `data/markdown/` 兩行改為（讓 `.gitkeep` 可入庫；被忽略「目錄」內的檔案無法用 `!` 重新納入，必須改成 `/*` 形式）：

```gitignore
data/pdfs/*
!data/pdfs/.gitkeep
data/markdown/*
!data/markdown/.gitkeep
```

  2. 檔尾補兩行：`.pytest_cache/` 與 `chapters_*.json`。
  3. 刪除第 43-45 行過時註解區塊（`# Lock files (optional...)` 至 `# bun.lockb`）。
- [ ] **Step 2: 解除追蹤本機設定** — `git rm --cached .claude/settings.local.json`（檔案保留在磁碟上）。
- [ ] **Step 3: `gh-clone.sh` 修位置參數 bug** — 第 4 行的判斷改為：

```bash
if [ -z "$1" ] || [ "${1#--}" != "$1" ]; then
```

- [ ] **Step 4: 驗證** — `git check-ignore .pytest_cache chapters_extra.json .claude/settings.local.json` 三者皆被忽略；`bash gh-clone.sh --public` 印出 Usage 並退出（不會建 repo）。
- [ ] **Step 5: Commit** — `git add -A && git commit -m "chore: gitignore hygiene, untrack settings.local.json, fix gh-clone arg check"`

---

## Phase B：模板清空

### Task 5: 擴充 clean_sample_data.py（TDD）

**Files:**
- Modify: `scripts/clean_sample_data.py`
- Test: `scripts/tests/test_clean_sample_data.py`（新建）

**Interfaces:**
- Produces: 新函式 `reset_chapters(apply: bool)`、`reset_style_decisions(apply: bool)`、`remove_progress_files(apply: bool)`、`reset_astro_config(apply: bool)`、`write_placeholder_index(apply: bool)`、`remove_plans_dir(apply: bool)`；模組常數 `CHAPTERS_PATH`、`STYLE_PATH`、`PROGRESS_GLOB_DIR`、`ASTRO_CONFIG`、`INDEX_MDX`、`PLANS_DIR`。`main()` 依序呼叫全部清理函式。測試以 monkeypatch 模組常數指向 `tmp_path`。

- [ ] **Step 1: 寫失敗測試** `scripts/tests/test_clean_sample_data.py`：

```python
from __future__ import annotations

import json

import clean_sample_data as csd


def _patch_paths(monkeypatch, tmp_path):
    monkeypatch.setattr(csd, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(csd, "CHAPTERS_PATH", tmp_path / "chapters.json")
    monkeypatch.setattr(csd, "STYLE_PATH", tmp_path / "style-decisions.json")
    monkeypatch.setattr(csd, "PROGRESS_GLOB_DIR", tmp_path / "data")
    monkeypatch.setattr(csd, "ASTRO_CONFIG", tmp_path / "docs" / "astro.config.mjs")
    monkeypatch.setattr(csd, "INDEX_MDX", tmp_path / "docs" / "src" / "content" / "docs" / "index.mdx")
    monkeypatch.setattr(csd, "PLANS_DIR", tmp_path / "plans")


def test_reset_chapters_writes_placeholder(monkeypatch, tmp_path):
    _patch_paths(monkeypatch, tmp_path)
    (tmp_path / "chapters.json").write_text('{"source": "old"}', encoding="utf-8")
    csd.reset_chapters(apply=True)
    data = json.loads((tmp_path / "chapters.json").read_text(encoding="utf-8"))
    assert data["source"] == "data/markdown/YOUR-RULEBOOK_pages.md"
    assert "example-section" in data["chapters"]


def test_reset_style_decisions_keeps_only_meta(monkeypatch, tmp_path):
    _patch_paths(monkeypatch, tmp_path)
    (tmp_path / "style-decisions.json").write_text(
        '{"_meta": {"description": "d", "updated": "x"}, "site": {"title": "YZE"}}',
        encoding="utf-8",
    )
    csd.reset_style_decisions(apply=True)
    data = json.loads((tmp_path / "style-decisions.json").read_text(encoding="utf-8"))
    assert list(data.keys()) == ["_meta"]


def test_remove_progress_files(monkeypatch, tmp_path):
    _patch_paths(monkeypatch, tmp_path)
    (tmp_path / "data").mkdir()
    for name in ("translation-progress.json", "translation-progress-bilingual.json"):
        (tmp_path / "data" / name).write_text("{}", encoding="utf-8")
    csd.remove_progress_files(apply=True)
    assert not list((tmp_path / "data").glob("translation-progress*.json"))


def test_reset_astro_config_title_and_sidebar(monkeypatch, tmp_path):
    _patch_paths(monkeypatch, tmp_path)
    cfg = tmp_path / "docs" / "astro.config.mjs"
    cfg.parent.mkdir(parents=True)
    cfg.write_text(
        "const SITE_CONFIG = {\n\ttitle: 'Cairn',\n};\n"
        "export default defineConfig({\n\tsidebar: [\n\t\t{ label: 'X', slug: 'bilingual/x' },\n\t],\n});\n",
        encoding="utf-8",
    )
    csd.reset_astro_config(apply=True)
    text = cfg.read_text(encoding="utf-8")
    assert "title: '遊戲規則文件'" in text
    assert "bilingual/x" not in text
    assert "sidebar: []," in text


def test_write_placeholder_index_and_remove_plans(monkeypatch, tmp_path):
    _patch_paths(monkeypatch, tmp_path)
    (tmp_path / "plans").mkdir()
    (tmp_path / "plans" / "x.md").write_text("x", encoding="utf-8")
    csd.write_placeholder_index(apply=True)
    csd.remove_plans_dir(apply=True)
    index = tmp_path / "docs" / "src" / "content" / "docs" / "index.mdx"
    assert index.exists()
    assert "title:" in index.read_text(encoding="utf-8")
    assert not (tmp_path / "plans").exists()


def test_idempotent_second_run(monkeypatch, tmp_path):
    _patch_paths(monkeypatch, tmp_path)
    csd.reset_chapters(apply=True)
    first = (tmp_path / "chapters.json").read_text(encoding="utf-8")
    csd.reset_chapters(apply=True)
    assert (tmp_path / "chapters.json").read_text(encoding="utf-8") == first
```

- [ ] **Step 2: 跑測試確認失敗** — `uv run pytest scripts/tests/test_clean_sample_data.py -v`。Expected: FAIL（`AttributeError: ... has no attribute 'CHAPTERS_PATH'` 等）。
- [ ] **Step 3: 實作**。在 `clean_sample_data.py` 常數區（第 14-19 行後）新增：

```python
CHAPTERS_PATH = PROJECT_ROOT / "chapters.json"
STYLE_PATH = PROJECT_ROOT / "style-decisions.json"
PROGRESS_GLOB_DIR = PROJECT_ROOT / "data"
ASTRO_CONFIG = PROJECT_ROOT / "docs" / "astro.config.mjs"
INDEX_MDX = PROJECT_ROOT / "docs" / "src" / "content" / "docs" / "index.mdx"
PLANS_DIR = PROJECT_ROOT / "plans"

CHAPTERS_PLACEHOLDER = {
    "source": "data/markdown/YOUR-RULEBOOK_pages.md",
    "output_dir": "docs/src/content/docs",
    "mode": "zh_only",
    "chapters": {
        "example-section": {
            "title": "Example Section",
            "order": 1,
            "files": {
                "index": {
                    "title": "Example Chapter",
                    "description": "格式參考用佔位章節；執行 /init-doc 或 /chapter-split 後會被真實內容取代。",
                    "pages": [1, 2],
                    "order": 0,
                }
            },
        }
    },
}

INDEX_PLACEHOLDER = """---
title: 遊戲規則文件
description: 使用 game-doc-template 建立的規則書文件站。執行 /init-doc 開始設定。
template: splash
hero:
  title: 遊戲規則文件
  tagline: 尚未初始化——請在專案中執行 /init-doc 匯入規則書。
---

## 開始使用

1. 將規則書 PDF 放入 `data/pdfs/`
2. 執行 `/init-doc` 完成抽取、章節切分與術語初始化
3. 執行 `/translate` 或 `/super-translate` 開始翻譯
"""
```

再新增六個函式（風格對齊既有 `clean_glossary`，dry-run 時只印出動作）：

```python
def _write_json(path: Path, data: dict, apply: bool, label: str) -> None:
    print(f"reset {label}: {path.relative_to(PROJECT_ROOT)}")
    if apply:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def reset_chapters(apply: bool) -> None:
    _write_json(CHAPTERS_PATH, CHAPTERS_PLACEHOLDER, apply, "chapters")


def reset_style_decisions(apply: bool) -> None:
    description = "翻譯與格式風格決策記錄"
    if STYLE_PATH.exists():
        try:
            meta = json.loads(STYLE_PATH.read_text(encoding="utf-8")).get("_meta", {})
            description = meta.get("description") or description
        except (json.JSONDecodeError, OSError):
            pass
    _write_json(STYLE_PATH, {"_meta": {"description": description, "updated": ""}}, apply, "style-decisions")


def remove_progress_files(apply: bool) -> None:
    if not PROGRESS_GLOB_DIR.exists():
        return
    for path in sorted(PROGRESS_GLOB_DIR.glob("translation-progress*.json")):
        remove_path(path, apply)


def reset_astro_config(apply: bool) -> None:
    if not ASTRO_CONFIG.exists():
        return
    import re

    text = ASTRO_CONFIG.read_text(encoding="utf-8")
    text = re.sub(r"title: '[^']*',", "title: '遊戲規則文件',", text, count=1)
    text = re.sub(r"sidebar: \[.*?\n(\s*)\],", "sidebar: [],", text, flags=re.DOTALL, count=1)
    print(f"reset astro config: {ASTRO_CONFIG.relative_to(PROJECT_ROOT)}")
    if apply:
        ASTRO_CONFIG.write_text(text, encoding="utf-8")


def write_placeholder_index(apply: bool) -> None:
    print(f"write placeholder index: {INDEX_MDX.relative_to(PROJECT_ROOT)}")
    if apply:
        INDEX_MDX.parent.mkdir(parents=True, exist_ok=True)
        INDEX_MDX.write_text(INDEX_PLACEHOLDER, encoding="utf-8")


def remove_plans_dir(apply: bool) -> None:
    if PLANS_DIR.exists():
        remove_path(PLANS_DIR, apply)
```

`main()` 在 `clean_glossary(apply)` 之後依序加入呼叫：`reset_chapters(apply)`、`reset_style_decisions(apply)`、`remove_progress_files(apply)`、`reset_astro_config(apply)`、`write_placeholder_index(apply)`、`remove_plans_dir(apply)`。同時把 `clean_glossary` 中的 `except Exception:` 改為 `except (json.JSONDecodeError, OSError):`。
- [ ] **Step 4: 跑測試確認通過** — `uv run pytest scripts/tests/test_clean_sample_data.py -v`。Expected: PASS（全部 6 個）。
- [ ] **Step 5: Commit** — `git add scripts/clean_sample_data.py scripts/tests/test_clean_sample_data.py && git commit -m "feat: clean_sample_data resets full template state (chapters, style, progress, astro, index, plans)"`

### Task 6: 產生空白模板狀態＋docs 手動重置

**Files:**
- Modify: `chapters.json`、`style-decisions.json`、`glossary.json`、`docs/astro.config.mjs`、`docs/src/content/docs/index.mdx`、`docs/package.json`、`vercel.json`、`docs/README.md`
- Delete: `data/translation-progress.json`、`docs/src/styles/custom-light.css`、`docs/src/assets/hero.jpg`
- Create: `data/pdfs/.gitkeep`、`data/markdown/.gitkeep`

- [ ] **Step 1: 執行清理腳本** — `uv run python scripts/clean_sample_data.py --yes`，然後**立即還原 plans/**（模板 repo 自身要保留）：`git checkout -- plans/`。
- [ ] **Step 2: docs 手動重置（腳本未涵蓋部分）**：
  1. `docs/astro.config.mjs`：刪除 head 區塊中兩組 `og:image` / `twitter:image` meta 標籤（引用 `/og-image.jpg` 的四個物件項）；確認 title 已為「遊戲規則文件」、sidebar 已為 `[]`。
  2. 刪除 `docs/src/styles/custom-light.css`（無人引用）與 `docs/src/assets/hero.jpg`（69 bytes 假圖；佔位 index.mdx 不引用任何圖片）。
  3. `docs/package.json`：移除 `"@astrojs/vercel"` 相依（未設 adapter，純死依賴），並執行 `cd docs && bun install` 更新 lockfile。
  4. `vercel.json`：刪除 `"source": "/fonts/(.*)"` 整個 headers 物件（無此目錄）。
  5. `docs/README.md` 整檔改寫為：

```markdown
# docs — 文件網站

本目錄是由 [game-doc-template](../README.md) 管理的 Astro 5 + Starlight 文件站，內容（`src/content/docs/`）與側欄（`astro.config.mjs` 的 `sidebar`）由專案根目錄的轉換管線產生：`/init-doc` 抽取規則書 → `/chapter-split` 切分章節（`scripts/split_chapters.py` 依 `chapters.json`）→ `scripts/generate_nav.py` 重寫首頁與側欄。

## 指令

| 指令 | 說明 |
| --- | --- |
| `bun install` | 安裝相依 |
| `bun run dev` | 本地開發（localhost:4321） |
| `bun run build` | 建置到 `./dist/` |
| `bun run preview` | 預覽建置結果 |

手動編輯 `src/content/docs/` 的內容會在下次執行管線時被覆寫；請透過翻譯工作流程（`/translate`、`/super-translate`）修改。
```

- [ ] **Step 3: 建立 data 佔位** — `New-Item data/pdfs/.gitkeep, data/markdown/.gitkeep`（空檔案）。
- [ ] **Step 4: 驗證**：
  - `cd docs && bun run build` — Expected: PASS（sidebar 已清空，無 bilingual 死連結）。
  - `git grep -l "Fria Ligan\|Year Zero\|Cairn" -- ':!plans' ':!.git'` — Expected: 無輸出。
  - 冪等：再跑一次 `uv run python scripts/clean_sample_data.py --yes && git checkout -- plans/`，`git status --short` 與第一次執行後一致。
- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: reset template to blank state; fix docs build (empty sidebar, placeholder index)"`

### Task 7: 刪除維護者工作文件與 openspec

**Files:**
- Delete: `docs/agent-system/`、`docs/plans/`、`docs/superpowers/`、`openspec/`

- [ ] **Step 1:** `git rm -r docs/agent-system docs/plans docs/superpowers openspec`
- [ ] **Step 2: 驗證** — `cd docs && bun run build` 仍通過（這些目錄不在 build 範圍，應無影響）。
- [ ] **Step 3: Commit** — `git commit -m "chore: remove maintainer working docs and finished openspec change from template"`

### Task 8: new-project 自動清理

**Files:**
- Modify: `.claude/skills/new-project/SKILL.md`、`README.md`、`scripts/README.md`

- [ ] **Step 1: `new-project/SKILL.md`** — 在複製模板（`cp -r "$TEMPLATE_ROOT" <TARGET_DIR>`，約第 87 行）之後的步驟中，新增必跑步驟：

```markdown
### 清理模板範例資料（必要，不可跳過）

複製完成後立即在新專案目錄執行：

```bash
uv run python scripts/clean_sample_data.py --yes
```

此步驟會重置 `glossary.json`、`chapters.json`、`style-decisions.json`、`docs/astro.config.mjs`（標題與側欄）、刪除 `data/translation-progress*.json` 與 `plans/`，並寫入佔位首頁，確保新專案不含模板殘留。
```

- [ ] **Step 2: `README.md`** — 找到 `clean_sample_data.py` 的「（可選）」段落（約第 244-257 行），改寫為：說明 new-project 會自動執行；補上實際行為完整清單（清 `data/markdown/*`、`docs/src/content/docs/**`、範例圖片、重置 glossary／chapters／style-decisions／astro 標題與側欄、刪除 translation-progress 與 plans/、寫入佔位首頁）。
- [ ] **Step 3: `scripts/README.md`** — 同步該腳本條目的行為描述（同上清單）。
- [ ] **Step 4: Commit** — `git commit -am "feat: new-project auto-runs clean_sample_data after clone"`

---

## Phase C：技能系統

### Task 9: 刪除 optimized-translating 與 pdf-translation

**Files:**
- Delete: `.claude/skills/optimized-translating/`（含 references/、templates/）、`.claude/skills/pdf-translation/`

- [ ] **Step 1:** `git rm -r .claude/skills/optimized-translating .claude/skills/pdf-translation`
- [ ] **Step 2: 驗證** — `git grep -ril "optimized-translating\|pdf-translation" -- ':!plans'`。Expected: 無輸出（若 README/CLAUDE.md 有殘留引用，於此一併刪除該行）。
- [ ] **Step 3: Commit** — `git commit -m "refactor: remove optimized-translating and pdf-translation skills (superseded per design spec)"`

### Task 10: Frontmatter 修正與 AGENTS.md 引用修復

**Files:**
- Modify: `.claude/skills/md-review/SKILL.md`、`.claude/skills/term-decision/SKILL.md`、`.claude/skills/check-consistency/SKILL.md`、`.claude/skills/final-proofread/SKILL.md`、`.claude/skills/md-review/reviewer-prompt.md`、`.claude/skills/super-translate/SKILL.md`

- [ ] **Step 1: Frontmatter**：
  - `md-review`、`term-decision`、`check-consistency` 三個 SKILL.md：刪除 frontmatter 中的 `disable-model-invocation: true` 一行（保留 `user-invocable: true`）。
  - `final-proofread/SKILL.md`：frontmatter 補一行 `disable-model-invocation: true`（在 `user-invocable: true` 之後）。
- [ ] **Step 2: AGENTS.md 引用改指 rules**（三處）：
  - `md-review/SKILL.md:32`：「`AGENTS.md` Integrated Conventions」→「`.claude/rules/docs-conventions.md`（文件格式與翻譯風格規範）」。
  - `md-review/reviewer-prompt.md:45`：同上替換（保留其後列舉的檢查面向文字）。
  - `super-translate/SKILL.md:93`：「project conventions from `AGENTS.md`」→「project conventions from `.claude/rules/docs-conventions.md`」。
- [ ] **Step 3: 驗證** — `git grep -n "AGENTS.md" -- .claude/skills`。Expected: 無輸出。`git grep -c "disable-model-invocation" -- .claude/skills` 應為 8 個檔案（原 10 − 開放 3 ＋ final-proofread 1）。
- [ ] **Step 4: Commit** — `git commit -am "fix: open dependency skills to model invocation, repoint AGENTS.md refs to rules"`

### Task 11: 模型路由寫入技能檔＋刪除 model-routing.md＋輪數統一

**Files:**
- Modify: `.claude/skills/super-translate/SKILL.md`、`.claude/skills/translate/SKILL.md`、`.claude/skills/bilingual-translate/SKILL.md`、`CLAUDE.md`
- Delete: `.claude/rules/model-routing.md`

- [ ] **Step 1: `super-translate/SKILL.md`** — 四個派遣步驟（約第 85、90、92、95 行）明確標註模型：
  - translator 派遣：「Agent tool (general-purpose)」→「Agent tool (general-purpose, **model: opus**)」
  - reviewer 派遣：→「(general-purpose, **model: opus**)」
  - md-review 派遣（經 md-review skill 或 reviewer-prompt）：→「(general-purpose, **model: haiku**)」
  - refiner 派遣：→「(general-purpose, **model: sonnet**)」

  並在 SKILL.md 開頭流程說明後新增小節：

```markdown
## 模型路由（固定，勿依會話模型浮動）

| 角色 | model 參數 | 理由 |
| --- | --- | --- |
| translator | opus | 初稿品質決定迭代輪數 |
| reviewer | opus | 品質裁判需要最強模型 |
| md-reviewer | haiku | 清單式結構核對，無需判斷力 |
| refiner | sonnet | 執行 reviewer 的具體修改清單 |
```

- [ ] **Step 2: `md-review/reviewer-prompt.md` 與 `md-review/SKILL.md`** — 派遣說明處（reviewer-prompt.md:10 一帶）加註 `model: haiku`。
- [ ] **Step 3: `translate/SKILL.md` 與 `bilingual-translate/SKILL.md`** — 各在開頭（Preflight 之前）加一行註記：

```markdown
> 模型建議：本技能為主執行緒流程，依成本路由決策建議於 **sonnet** 會話執行；高階模型會話亦可執行，但屬超規格花費。
```

- [ ] **Step 4: 刪除 rule** — `git rm .claude/rules/model-routing.md`。
- [ ] **Step 5: `CLAUDE.md` 輪數統一** — 指令表中 `/super-translate` 說明「(up to 3 iterations)」改為「(up to 2 iterations)」。
- [ ] **Step 6: 驗證** — `git grep -rn "model-routing" -- ':!plans'` 無輸出；`git grep -n "3 iterations" CLAUDE.md` 無輸出。
- [ ] **Step 7: Commit** — `git commit -am "feat: bake model routing into skill dispatch steps, drop model-routing rule, unify iteration cap at 2"`

### Task 12: docs-conventions.md 對齊與 md-review 檢查清單

**Files:**
- Modify: `.claude/rules/docs-conventions.md`、`.claude/skills/md-review/SKILL.md`

- [ ] **Step 1: `docs-conventions.md` 三處修訂**：
  - 「MUST include `sidebar: order:`」一條改為：「側欄順序由 `split_chapters.py` 產生的 `_meta.yml` 驅動（starlight-auto-sidebar）；個別頁面**不需要** `sidebar.order`，僅在需要覆蓋自動排序時使用。」
  - 「MUST reserve H1 for title (from frontmatter)」一條改為：「頁面標題僅由 frontmatter `title` 提供；**正文禁止**出現任何重複 frontmatter 標題的標題（含 H1）。」
  - `……` 刪節號規則保留原文不動。
- [ ] **Step 2: `md-review/SKILL.md` 檢查清單** — 在 zh-TW 標點檢查項處補：「刪節號必須使用 `……`，不得使用 `...`」。
- [ ] **Step 3: Commit** — `git commit -am "docs: align docs-conventions with pipeline reality, add ellipsis check to md-review"`

### Task 13: final-proofread 雙語支援＋chapter-split 路徑統一

**Files:**
- Modify: `.claude/skills/final-proofread/SKILL.md`、`.claude/skills/chapter-split/SKILL.md`

- [ ] **Step 1: `final-proofread/SKILL.md`** — 前置檢查（約第 30、39 行）改為模式感知：

```markdown
1. 讀取 `style-decisions.json` 的 `translation_mode.mode`。
2. `mode == "bilingual"` 時：進度檔為 `data/translation-progress-bilingual.json`，內容根目錄為 `docs/src/content/docs/bilingual/`；`progress_read.py` 需帶 `--progress-file data/translation-progress-bilingual.json`。
3. 其他模式：維持 `data/translation-progress.json` 與 `docs/src/content/docs/`。
```

  文中所有寫死 `data/translation-progress.json` 或 `progress_read.py --json`（無 `--progress-file`）之處，改為引用上述步驟選定的進度檔。
- [ ] **Step 2: `chapter-split/SKILL.md`** — 第 66-67 行的 topology 草稿路徑 `.claude/skills/chapter-split/.state/topology.draft.json` 改為 `.state/chapter-split/topology.draft.json`（與 chapters.draft.json 同目錄）。
- [ ] **Step 3: 驗證** — `git grep -n "skills/chapter-split/.state" -- .claude` 無輸出。
- [ ] **Step 4: Commit** — `git commit -am "fix: final-proofread supports bilingual mode, unify chapter-split draft paths"`

### Task 14: 刪除 .agents/＋補齊 gemini commands

**Files:**
- Delete: `.agents/`
- Create: `.gemini/commands/md-review.toml`、`.gemini/commands/bilingual-translate.toml`、`.gemini/commands/fix-ref.toml`、`.gemini/commands/final-proofread.toml`

- [ ] **Step 1:** `git rm -r .agents`
- [ ] **Step 2: 新增四個 TOML**。先 `cat .gemini/commands/translate.toml` 取得現行格式（description ＋ prompt 指向 `.gemini/skills/<name>/SKILL.md` 並重申 zh-TW 互動守則），四個新檔照同一版型撰寫，內容對應：
  - `md-review.toml` — description: 「檢查 Markdown 結構與文件風格合規」；prompt 指向 `.gemini/skills/md-review/SKILL.md`。
  - `bilingual-translate.toml` — description: 「單次雙語翻譯（中文為主、英文引用）」；指向 `.gemini/skills/bilingual-translate/SKILL.md`。
  - `fix-ref.toml` — description: 「將印刷頁碼引用轉為站內連結」；指向 `.gemini/skills/fix-ref/SKILL.md`。
  - `final-proofread.toml` — description: 「出版前三關品質總檢」；指向 `.gemini/skills/final-proofread/SKILL.md`。
- [ ] **Step 3: 驗證** — `ls .gemini/commands` 共 12 個 TOML，與 CLAUDE.md 指令表對齊。
- [ ] **Step 4: Commit** — `git commit -am "chore: drop drifted .agents copy, complete gemini command coverage"`

### Task 15: CLAUDE.md／README／scripts README 同步

**Files:**
- Modify: `CLAUDE.md`、`README.md`、`scripts/README.md`

- [ ] **Step 1: `CLAUDE.md`**：
  1. Slash Skills 表補一列：`| /terminology-management | Glossary-driven terminology creation, edit, validation, and enforcement |`（表成 13 列）。
  2. Law 7 最後一條改為：「`/init-doc`, `/translate`, `/super-translate`, and `/bilingual-translate` must run terminology read/consistency checks first」。
  3. Workflow 步驟 5 改為：「Use `translate` or `super-translate`（bilingual 模式改用 `bilingual-translate`）to translate target chapters…（其餘不變）」。
  4. Tech Stack 的 PDF Processing 改為：「markitdown, pymupdf, opendataloader-pdf（預設引擎，需 Java 11+）」；Frontend 補「＋ starlight-auto-sidebar」。
- [ ] **Step 2: `README.md`**：
  1. 指令表補齊至 12 個（新增 `/md-review`、`/bilingual-translate`、`/fix-ref`、`/final-proofread` 四列，說明抄 CLAUDE.md 表）。
  2. 工作流程補步驟：翻譯完成後 `/fix-ref`，出版前 `/final-proofread`。
  3. 抽取章節補 opendataloader 段落：預設引擎為 opendataloader-pdf（自動偵測；需 Java 11 以上，無 Java 時自動退回 pymupdf/markitdown）。
  4. 刪除「`.codex/agents -> .claude/agents`」一行（兩者皆不存在）；`.agents/` 相關描述一併刪除。
  5. 補一段 Windows 註記：「Windows 使用者需啟用 `git config core.symlinks true` 並以系統管理員或開發者模式 clone，`.codex/`、`.gemini/skills` 的 symlink 才會實體化。」
- [ ] **Step 3: `scripts/README.md`** — 腳本清單補齊 26 支（每支一行用途，含 `_*.py` 標註「內部共用庫」）；系統依賴段補：Java 11+（opendataloader）、tesseract＋chi_tra 語言包（OCR）、bun（handoff gate 的 docs build）。
- [ ] **Step 4: 驗證** — `.claude/skills/` 目錄數（13）＝ CLAUDE.md 表列數＝ README 表列數＋1（terminology-management 在 README 可併入說明）；`git grep -n "codex/agents" README.md` 無輸出。
- [ ] **Step 5: Commit** — `git commit -am "docs: sync CLAUDE.md/README/scripts README with actual skills, scripts, and engines"`

---

## Phase D：腳本修正＋測試＋CI＋安全

### Task 16: Windows 編碼修復＋bun 前置檢查

**Files:**
- Modify: `scripts/init_handoff_gate.py`、`scripts/_ocr_lib.py`、`scripts/_opendataloader_lib.py`
- Test: `scripts/tests/test_init_handoff_gate.py`（新建）

- [ ] **Step 1: 寫失敗測試** `scripts/tests/test_init_handoff_gate.py`：

```python
from __future__ import annotations

import init_handoff_gate as gate


def test_missing_bun_reported(monkeypatch, tmp_path):
    monkeypatch.setattr(gate.shutil, "which", lambda _cmd: None)
    result = gate.check_bun_available()
    assert result is False


def test_run_cmd_uses_utf8(monkeypatch):
    captured = {}

    def fake_run(cmd, cwd, capture_output, text, encoding):
        captured["encoding"] = encoding

        class P:
            returncode = 0
            stdout = ""
            stderr = ""

        return P()

    monkeypatch.setattr(gate.subprocess, "run", fake_run)
    gate.run_cmd(["echo"], cwd=gate.PROJECT_ROOT)
    assert captured["encoding"] == "utf-8"
```

- [ ] **Step 2: 確認失敗** — `uv run pytest scripts/tests/test_init_handoff_gate.py -v`。Expected: FAIL（無 `shutil`、無 `check_bun_available`、`run_cmd` 無 encoding 參數）。
- [ ] **Step 3: 實作** `init_handoff_gate.py`：
  1. import 區補 `import shutil`。
  2. `run_cmd` 的 `subprocess.run(...)` 補 `encoding="utf-8"`。
  3. 新增函式並於 `main()` 中 `--skip-docs-build` 判斷前使用：

```python
def check_bun_available() -> bool:
    """檢查 bun 是否在 PATH 上（docs build 需要）。"""
    return shutil.which("bun") is not None
```

`main()` 中：若 `not args.skip_docs_build and not check_bun_available()`，將 `report["ok"] = False`、`report["checks"].append({"cmd": ["bun", "run", "build"], "returncode": -1, "stdout": "", "stderr": "bun 未安裝或不在 PATH — 請安裝 bun 或改用 --skip-docs-build", "cwd": str(root / "docs")})`，並跳過 bun 檢查項（不執行 `run_cmd`）。
  4. `_ocr_lib.py` 第 78、107 行與 `_opendataloader_lib.py` 第 46-51 行的 `subprocess.run(..., text=True, ...)` 各補 `encoding="utf-8"`。
- [ ] **Step 4: 確認通過** — `uv run pytest scripts/tests/test_init_handoff_gate.py -v`；再跑全套 `uv run pytest`。Expected: PASS。
- [ ] **Step 5: Commit** — `git commit -am "fix: utf-8 subprocess decoding on win32, explicit bun availability gate"`

### Task 17: CLI 死開關、leaf 統一、yaml_safe 共用、雜項修正

**Files:**
- Modify: `scripts/term_cal_batch.py`、`scripts/generate_nav.py`、`scripts/split_chapters.py`、`scripts/_markdown_utils.py`、`scripts/_term_lib.py`、`scripts/extract_pdf.py`、`scripts/draft.py`、`scripts/style_decisions.py`、`pyproject.toml`
- Test: `scripts/tests/test_markdown_utils.py`（增補）、`scripts/tests/test_generate_nav.py`（修改）

- [ ] **Step 1: 寫失敗測試**。`scripts/tests/test_markdown_utils.py` 增補：

```python
from _markdown_utils import yaml_safe


def test_yaml_safe_quotes_fullwidth_colon():
    assert yaml_safe("戰鬥：基礎") == '"戰鬥：基礎"'


def test_yaml_safe_plain_ascii_untouched():
    assert yaml_safe("Introduction") == "Introduction"


def test_yaml_safe_escapes_quotes_and_backslash():
    assert yaml_safe('a "b" \\c:') == '"a \\"b\\" \\\\c:"'
```

- [ ] **Step 2: 確認失敗** — `uv run pytest scripts/tests/test_markdown_utils.py -v`（ImportError: `yaml_safe`）。
- [ ] **Step 3: 實作**：
  1. 把 `generate_nav.py` 的 `yaml_safe()`（第 99-128 行，含全形冒號的版本）整段搬到 `scripts/_markdown_utils.py`；`generate_nav.py` 改 `from _markdown_utils import yaml_safe`；`split_chapters.py` 刪除自己的 `_yaml_safe()`（第 150-155 行），改 import 共用 `yaml_safe` 並更新呼叫點。
  2. `generate_nav.py` 刪除死程式碼 `first_leaf_path()`（第 87-96 行）——它同時是 leaf 判準矛盾的來源（其餘函式一律以「有 `files` 即群組、否則為 leaf」判斷，維持現狀即為統一）。同步刪除 `scripts/tests/test_generate_nav.py` 中對 `first_leaf_path` 的測試。
  3. `term_cal_batch.py` 第 52-57 行改為：

```python
    parser.add_argument(
        "--skip-managed",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Skip already-managed (approved/is_term) glossary entries; use --no-skip-managed to include them.",
    )
```

  4. `_term_lib.py`：刪除 `count_terms_batch` 函式內的 `from collections import defaultdict as _dd` 重複 import（改用模組層級的 `defaultdict`）。
  5. `extract_pdf.py:653` 與 `split_chapters.py:599` 的 `Path(__file__).parent.parent` 改為 `Path(__file__).resolve().parents[1]`；`draft.py:34` 的 `ROOT = Path(__file__).parent.parent` 改為 `ROOT = Path(__file__).resolve().parents[1]`。
  6. `split_chapters.py` 移除未使用 import：`image_coverage_ratio`、`image_page_dimensions`（第 49、52 行）。
  7. `style_decisions.py:296` 的 `--page-text-engine` choices 補 `"opendataloader"`。
  8. `pyproject.toml` 刪除整個 `[project.optional-dependencies]` 區塊（opendataloader 已是硬依賴），然後 `uv lock` 更新 lockfile。
- [ ] **Step 4: 確認通過** — `uv run pytest`。Expected: 全綠（含 generate_nav 既有測試在刪除 first_leaf_path 測試後）。
- [ ] **Step 5: Commit** — `git commit -am "fix: shared yaml_safe, unify leaf definition, BooleanOptionalAction, resolve() roots, opendataloader engine choice"`

### Task 18: _opendataloader_lib 分頁抽取＋progress_edit 測試

**Files:**
- Modify: `scripts/_opendataloader_lib.py`
- Test: `scripts/tests/test_opendataloader_lib.py`（新建）、`scripts/tests/test_progress_edit.py`（新建）

**Interfaces:**
- Produces: `_opendataloader_lib.split_pages_content(content: str, total_pages: int) -> list[tuple[int, str]] | None`（純函式；無法可靠切分時回傳 `None`）。

- [ ] **Step 1: 寫失敗測試** `scripts/tests/test_opendataloader_lib.py`：

```python
from __future__ import annotations

from _opendataloader_lib import split_pages_content


def test_exact_page_count():
    content = "p1\n---\np2\n---\np3"
    assert split_pages_content(content, 3) == [(1, "p1"), (2, "p2"), (3, "p3")]


def test_tolerates_off_by_two():
    content = "p1\n---\np2\n---\np3"
    result = split_pages_content(content, 5)
    assert result is not None
    assert len(result) == 3


def test_formfeed_separator():
    assert split_pages_content("a\x0cb", 2) == [(1, "a"), (2, "b")]


def test_unsplittable_returns_none():
    assert split_pages_content("single blob of text", 10) is None


def test_empty_pages_filtered():
    content = "p1\n---\n\n---\np2"
    assert split_pages_content(content, 2) == [(1, "p1"), (2, "p2")]
```

`scripts/tests/test_progress_edit.py`：

```python
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import progress_edit


def _sample() -> dict:
    return {
        "_meta": {"total_chapters": 0, "completed": 0, "updated": ""},
        "chapters": [
            {"id": "a", "file": "docs/a.md", "status": "not_started"},
            {"id": "b", "file": "docs/b.md", "status": "completed"},
        ],
    }


def test_recalculate_meta_counts():
    data = _sample()
    progress_edit.recalculate_meta(data)
    assert data["_meta"]["total_chapters"] == 2
    assert data["_meta"]["completed"] == 1


def test_find_entry_by_file_and_id():
    data = _sample()
    assert progress_edit.find_entry(data, "docs/a.md")["id"] == "a"
    assert progress_edit.find_entry(data, "b")["id"] == "b"
    assert progress_edit.find_entry(data, "missing") is None


def test_cli_status_update(tmp_path: Path):
    progress = tmp_path / "progress.json"
    progress.write_text(json.dumps(_sample(), ensure_ascii=False), encoding="utf-8")
    script = Path(progress_edit.__file__)
    proc = subprocess.run(
        [sys.executable, str(script), "--progress-file", str(progress),
         "--file", "docs/a.md", "--status", "completed"],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert proc.returncode == 0, proc.stderr
    data = json.loads(progress.read_text(encoding="utf-8"))
    assert data["chapters"][0]["status"] == "completed"
    assert data["_meta"]["completed"] == 2
```

- [ ] **Step 2: 確認失敗** — `uv run pytest scripts/tests/test_opendataloader_lib.py scripts/tests/test_progress_edit.py -v`。Expected: opendataloader ImportError；progress_edit 三測應直接 PASS（函式已存在）——若 CLI 測失敗，檢查輸出後修。
- [ ] **Step 3: 實作** `_opendataloader_lib.py` — 從 `convert_pdf_pages()` 抽出純函式（放在 `convert_pdf_pages` 之前）：

```python
def split_pages_content(content: str, total_pages: int) -> list[tuple[int, str]] | None:
    """依分隔符（\\n---\\n 或換頁符）切分內容；無法可靠切分時回傳 None。"""
    page_separator_pattern = re.compile(r"\n---\n|\f")
    raw_pages = [p for p in page_separator_pattern.split(content) if p.strip()]
    if len(raw_pages) == total_pages or (
        len(raw_pages) > 1 and abs(len(raw_pages) - total_pages) <= 2
    ):
        return [(i + 1, text.strip()) for i, text in enumerate(raw_pages)]
    return None
```

`convert_pdf_pages()` 第 140-158 行改為：

```python
    split_result = split_pages_content(content, total_pages)
    if split_result is not None:
        pages = split_result
    else:
        pages = _convert_pages_individually(pdf_path, total_pages, progress_every)
```

- [ ] **Step 4: 確認通過** — `uv run pytest`。Expected: 全綠。
- [ ] **Step 5: Commit** — `git commit -am "test: cover opendataloader page splitting and progress_edit; extract split_pages_content"`

### Task 19: 根目錄 tests/ 遷移與刪除

**Files:**
- Modify/Create: `scripts/tests/test_term_tools.py`、`scripts/tests/test_style_decisions.py`、`scripts/tests/test_draft.py`、`scripts/tests/test_validate_glossary.py`、`scripts/tests/test_init_create_progress.py`、`scripts/tests/test_bilingual_prep.py`、`scripts/tests/test_split_chapters_bilingual.py`、`scripts/tests/test_style_decisions_bilingual.py`（視來源測試切檔，檔名可合併調整）
- Delete: `tests/`（整個目錄）

**遷移規則（每個來源測試依此處理）：**
1. 只遷移「唯一覆蓋」模組的測試：`clean_sample_data`（若與 Task 5 新測試重複則捨棄舊測）、`draft`、`style_decisions`、`term_generate`／`term_edit`／`term_read`、`validate_glossary`、`_term_lib`、`init_create_progress`、`init_handoff_gate`（與 Task 16 新測試合併）、`bilingual_prep`、三個 bilingual 測試檔。`tests/test_scripts.py` 中 `TestExtractPdf`、`TestSplitChapters` 類與 `scripts/tests/` 既有測試重複——**直接捨棄**。
2. `unittest.TestCase` 改寫為 pytest 風格：`tempfile.TemporaryDirectory` → `tmp_path` fixture；`self.assertEqual(a, b)` → `assert a == b`；`unittest.mock.patch` → `monkeypatch`。
3. 刪除所有 `sys.path` 自插（`scripts/tests/conftest.py` 已處理 path）。
4. 已知必修點：
   - `tests/test_split_chapters_bilingual.py:31` 的 `cwd="/Users/weihung/projects/game-doc-template"` → 改用 `cwd=PROJECT_ROOT`（自 conftest 或 `Path(__file__).resolve().parents[2]` 取得）。
   - 同檔 `:7` 與 `:28` 的 `write_text(...)` 補 `encoding="utf-8"`。
   - `tests/test_style_decisions_bilingual.py:20` 的 `read_text()` 補 `encoding="utf-8"`。
   - 來源測試若引用已搬移的函式（`analyze_pymupdf_text_noise`、`classify_page_layout`、EPUB 相關——現居 `_layout_lib`／`_epub_lib`），該測試屬重複覆蓋，捨棄。
   - 所有 `subprocess.run(..., text=True)` 補 `encoding="utf-8"`。

- [ ] **Step 1: 逐檔遷移**（依上述規則）。每完成一個目標檔就跑 `uv run pytest scripts/tests/<新檔> -v` 確認綠燈再遷下一個。
- [ ] **Step 2: 刪除來源** — `git rm -r tests`；確認 `.pytest_cache/` 未被追蹤。
- [ ] **Step 3: 全套驗證** — `uv run pytest`。Expected: 全綠，總測試數 > 300（264 既有＋新增與遷移）。
- [ ] **Step 4: Commit** — `git commit -am "test: migrate unique-coverage tests from root tests/ into scripts/tests, drop stale duplicates"`

### Task 20: CI 更新

**Files:**
- Modify: `.github/workflows/terminology-check.yml`

- [ ] **Step 1: 修改 workflow**：
  1. `uv python install 3.12` → `uv python install`（無參數時依 `.python-version`）。
  2. 在 `uv sync` 之後新增兩個步驟：

```yaml
      - name: Run tests
        run: uv run pytest

      - name: Validate style decisions
        run: uv run python scripts/validate_style_decisions.py
```

  3. 術語步驟維持 `validate_glossary.py` 與 `term_read.py --fail-on-forbidden` 不變。
- [ ] **Step 2: 驗證** — `uv run python -c "import yaml,io;yaml.safe_load(io.open('.github/workflows/terminology-check.yml',encoding='utf-8'))"`（若環境無 pyyaml，改以 `bun x yaml` 或目視檢查縮排）。本地模擬：依序執行 workflow 中每個 run 指令，全部 exit 0（空白模板下 `validate_style_decisions.py` 與空 glossary 必須通過——若失敗，屬 Task 6 重置內容問題，回頭修資料而非放寬 CI）。
- [ ] **Step 3: Commit** — `git commit -am "ci: run pytest and style validation, track python version from .python-version"`

### Task 21: Vercel 密碼閘道安全強化

**Files:**
- Create: `lib/site-auth-shared.ts`
- Modify: `middleware.ts`、`api/site-auth.ts`

**Interfaces:**
- Produces: `lib/site-auth-shared.ts` 匯出 `COOKIE_NAME: string`、`MAX_AGE_SECONDS: number`、`createAuthCookieValue(password: string): Promise<string>`、`verifyAuthCookieValue(value: string | null, password: string): Promise<boolean>`、`sanitizeRedirect(redirect: string | null | undefined): string`、`escapeHtml(s: string): string`。兩個消費端皆以相對路徑 import；兩者皆為 Edge runtime（Web Crypto 可用）。

- [ ] **Step 1: 新建 `lib/site-auth-shared.ts`**（完整內容）：

```typescript
export const COOKIE_NAME = "site_auth";
export const MAX_AGE_SECONDS = 60 * 60 * 24 * 30;

async function hmacSign(payload: string, secret: string): Promise<string> {
  const enc = new TextEncoder();
  const key = await crypto.subtle.importKey(
    "raw",
    enc.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const sig = await crypto.subtle.sign("HMAC", key, enc.encode(payload));
  return btoa(String.fromCharCode(...new Uint8Array(sig)))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
}

function timingSafeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

/** cookie 值格式：`<expiresEpochSeconds>.<base64url(HMAC-SHA256(expires, password))>` */
export async function createAuthCookieValue(password: string): Promise<string> {
  const expires = Math.floor(Date.now() / 1000) + MAX_AGE_SECONDS;
  const payload = String(expires);
  return `${payload}.${await hmacSign(payload, password)}`;
}

export async function verifyAuthCookieValue(
  value: string | null,
  password: string,
): Promise<boolean> {
  if (!value || !password) return false;
  const dot = value.indexOf(".");
  if (dot <= 0) return false;
  const payload = value.slice(0, dot);
  const expires = Number(payload);
  if (!Number.isFinite(expires) || expires * 1000 < Date.now()) return false;
  return timingSafeEqual(value.slice(dot + 1), await hmacSign(payload, password));
}

/** 只接受站內相對路徑，阻擋 open redirect（`//evil.com`、絕對網址、反斜線變體）。 */
export function sanitizeRedirect(redirect: string | null | undefined): string {
  if (!redirect) return "/";
  if (!redirect.startsWith("/") || redirect.startsWith("//") || redirect.startsWith("/\\")) {
    return "/";
  }
  return redirect;
}

export function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}
```

- [ ] **Step 2: 改寫 `middleware.ts`**：
  1. 刪除本地 `hashPassword`（第 4-12 行）。
  2. 檔頭加 `import { COOKIE_NAME, escapeHtml, verifyAuthCookieValue } from "./lib/site-auth-shared";`（原 `const COOKIE_NAME` 一行刪除）。
  3. `middleware` 函式改為 `export default async function middleware(request: Request)`；驗證段改為：

```typescript
  const cookieHeader = request.headers.get("cookie");
  const authCookie = getCookie(cookieHeader, COOKIE_NAME);
  if (await verifyAuthCookieValue(authCookie, PASSWORD)) {
    return;
  }
```

  4. 登入頁插值處（第 77 行）`value="${redirectPath}"` 改為 `value="${escapeHtml(redirectPath)}"`（`getLoginHTML` 內）。
- [ ] **Step 3: 改寫 `api/site-auth.ts`**（完整替換，Edge runtime、Web 標準簽名、移除 `@vercel/node`）：

```typescript
import {
  COOKIE_NAME,
  MAX_AGE_SECONDS,
  createAuthCookieValue,
  sanitizeRedirect,
} from "../lib/site-auth-shared";

export const config = { runtime: "edge" };

export default async function handler(request: Request): Promise<Response> {
  if (request.method !== "POST") {
    return new Response(JSON.stringify({ error: "Method not allowed" }), {
      status: 405,
      headers: { "Content-Type": "application/json" },
    });
  }

  const form = await request.formData();
  const password = String(form.get("password") ?? "");
  const redirect = sanitizeRedirect(String(form.get("redirect") ?? "/"));
  const expected = process.env.SITE_PASSWORD || "";
  const origin = new URL(request.url).origin;

  if (expected && password === expected) {
    const value = await createAuthCookieValue(expected);
    return new Response(null, {
      status: 302,
      headers: {
        Location: new URL(redirect, origin).toString(),
        "Set-Cookie": `${COOKIE_NAME}=${value}; HttpOnly; Secure; SameSite=Lax; Max-Age=${MAX_AGE_SECONDS}; Path=/`,
      },
    });
  }

  const errorUrl = new URL(redirect, origin);
  errorUrl.searchParams.set("error", "1");
  return new Response(null, {
    status: 302,
    headers: { Location: errorUrl.toString() },
  });
}
```

- [ ] **Step 4: 驗證** — `cd docs && bun x tsc --noEmit ../middleware.ts ../api/site-auth.ts ../lib/site-auth-shared.ts --target es2022 --module esnext --moduleResolution bundler --skipLibCheck`。Expected: 無型別錯誤（`@vercel/node` import 已移除，無未解析模組）。
- [ ] **Step 5: Commit** — `git add lib middleware.ts api && git commit -m "fix(security): HMAC-signed auth cookie with expiry, redirect allowlist, shared verification logic"`

### Task 22: 總驗收

**Files:** 無新增修改（只驗證；發現問題回到對應 task 修）。

- [ ] **Step 1:** `cd docs && bun run build` — PASS。
- [ ] **Step 2:** `uv run pytest` — 全綠；`ls tests` 不存在，測試僅在 `scripts/tests/`。
- [ ] **Step 3:** `bash .claude/hooks/session-start.sh | uv run python -c "import json,sys;json.load(sys.stdin);print('ok')"` — ok。
- [ ] **Step 4: 懸空引用掃描**（皆應無輸出）：

```bash
git grep -ril "optimized-translating" -- ':!plans'
git grep -ril "pdf-translation" -- ':!plans'
git grep -rn  "model-routing" -- ':!plans'
git grep -n   "AGENTS.md" -- .claude/skills
git grep -l   "Fria Ligan\|Year Zero\|Cairn" -- ':!plans'
```

- [ ] **Step 5: 冪等驗證** — `uv run python scripts/clean_sample_data.py --yes` 連跑兩次，`git status --short` 兩次結果一致；完成後 `git checkout -- plans/` 還原。
- [ ] **Step 6: 清單一致性** — `.claude/skills/` 下 13 個技能目錄，與 CLAUDE.md 表格一致。
- [ ] **Step 7: Commit（如驗收過程有微調）** — `git commit -am "chore: final verification fixes"`（無異動則跳過）。
