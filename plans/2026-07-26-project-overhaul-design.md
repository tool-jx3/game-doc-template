# game-doc-template 全面整修設計（Spec）

- 日期：2026-07-26
- 分支：`fix/project-review`（自 `tmp-new` 分出）
- 狀態：待使用者審閱
- 來源：四路專案審查（技能系統／Python 腳本／docs 網站／版控衛生）＋ 使用者逐項裁決

## 1. 目標與背景

本 repo 是「PDF 遊戲規則書 → zh-TW 文件站」的模板專案。審查發現三類問題：

1. **現在就是壞的**：docs 網站因 sidebar 指向已刪除內容而無法建置；SessionStart hook 在 Windows 靜默失敗導致每次 session 誤報專案狀態；兩個 PostToolUse hooks 掛錯事件而完全無作用；技能互相呼叫但被呼叫方設為模型不可呼叫。
2. **模板汙染**：殘留兩代舊專案資料（Cairn 標題＋Year Zero Engine 全套設定，含 Fria Ligan 版權文字）；`clean_sample_data.py` 只覆蓋約四成該清的內容；`settings.local.json` 被追蹤且含其他專案的絕對路徑。
3. **互相矛盾的規則**：五套翻譯技能世界觀衝突；文件與程式碼多處數字、清單、流程不一致；根目錄 `tests/` 永遠不被 pytest 收集。

目標：修完後，`bun run build` 與 `uv run pytest` 全綠；`clean_sample_data.py --yes` 跑完即為理想空白模板（冪等）；技能、文件、腳本三者說法一致。

## 2. 決策總表（均經使用者裁決）

| # | 議題 | 決定 |
|---|------|------|
| 1 | 模板出廠狀態 | 完全空白模板 |
| 2 | 翻譯技能裁決 | 模型路由整併進技能派遣步驟後，刪除 `optimized-translating` 與 `pdf-translation` |
| 3 | super-translate 審查輪數 | 統一為 2 輪（改 CLAUDE.md） |
| 4 | Hooks | `session-start.sh`、`pytest-check.py` 修復；`permission-check.py` 刪除 |
| 5 | 跨工具目錄 | 刪除 `.agents/`；保留 `.codex/`、`.gemini/` symlink 並補齊 gemini commands |
| 6 | model-routing.md | 刪除，路由規則以技能檔為單一來源 |
| 7 | 維護者工作文件 | 刪除 docs/ 下 6 份舊文件；未來 spec 放根目錄 `plans/` |
| 8 | 技能斷鏈 | `md-review`、`term-decision`、`check-consistency` 移除 `disable-model-invocation` |
| 9 | 測試與 CI | 根目錄 `tests/` 唯一覆蓋部分遷入 `scripts/tests/` 後刪除；CI 加 pytest、版本改讀 `.python-version` |
| 10 | 部署安全 | HMAC-SHA256 簽章 cookie＋redirect 白名單＋共用驗證邏輯 |
| 11 | 品質修正範圍 | 只做修正型；美化型重構（`_io_lib` 抽取、CLI 一致化）延後 |
| 12 | 分支策略 | 於 `fix/project-review` 分支進行，四批段階式 commit |
| 13 | chapters.json | 重置為最小佔位範例檔（保留格式參考） |
| 14 | openspec/ | 整個目錄刪除 |
| 15 | .github/template.yml | 不動 |
| 16 | 模型路由 | 見 §2.1 |
| 17 | final-proofread | 補 `disable-model-invocation: true`（與入口型技能對稱） |
| 18 | 佔位圖 | 刪除 hero.jpg／og-image 引用，圖片由 `/init-doc` 流程向使用者取得 |
| 19 | new-project | clone 後自動執行 `clean_sample_data.py --yes` |

### 2.1 模型路由（寫入各技能派遣步驟）

| 角色 | 模型 | 理由摘要 |
|------|------|----------|
| `/super-translate` translator | opus | 初稿品質決定迭代輪數；2 輪上限下的便宜保險 |
| `/super-translate` reviewer | opus | 品質裁判需要最強模型（LLM-as-a-judge） |
| `/super-translate` refiner | sonnet | 執行 reviewer 的具體修改清單，範圍有界 |
| md-review 結構審查（被 super-translate 呼叫或獨立執行時的子代理派遣） | haiku | 清單式核對，無需判斷力，省 3–10 倍成本 |
| `/translate` | sonnet | 效率管線定位，自我檢查清單兜底 |
| `/bilingual-translate` | sonnet | 與 /translate 對齊的效率定位 |

## 3. 批次 1：基礎修復

### 3.1 既有修正入庫
- 首個實作 commit 收下工作區兩個修正：`.python-version` → `3.13`；`.claude/settings.json` hooks 指令改 `uv run python`。

### 3.2 Hooks
- 刪除 `.claude/hooks/permission-check.py`，並移除 `settings.json` 中對應的 PostToolUse 註冊（掛錯事件無作用＋Windows 無窮迴圈＋與內建權限系統重疊）。
- `pytest-check.py`：
  - 觸發條件收斂為 `scripts/**/*.py`（含 `scripts/tests/`）；其他路徑的 `.py` 不觸發。
  - glob 範圍限定 `scripts/` 目錄，不再全樹遍歷（不進 `.venv`、`node_modules`）。
  - `settings.json` hook timeout 提高至 60 秒、內部 pytest timeout 45 秒，消除預算矛盾。
  - 移除未使用的 `import os`。
- `session-start.sh`：
  - 三處 `python3` → `uv run python`（修 Windows 靜默失敗——每次 session 誤報「Glossary not yet initialized」的根因）。
  - 「直接編輯 JSON」指引改為指向 `style_decisions.py` 與 `progress_edit.py` CLI。
  - 移除腳本不支援的幻影 `reviewed/★` 狀態。
  - 腳本清單補齊：`progress_edit.py`、`progress_read.py`、`style_decisions.py`、`draft.py`、`term_cal_batch.py`。
  - 移除無效的重複 `additional_context` 輸出鍵。
  - 跳脫函式補控制字元（`\r`、`\t`）處理。

### 3.3 版控衛生
- `.gitignore`：增補 `.pytest_cache/`、`chapters_*.json`（多來源中間產物）；移除過時的 `bun.lockb` 註解段。
- `git rm --cached .claude/settings.local.json`（檔案留在本機，不再入版控）。
- `gh-clone.sh`：修位置參數 bug（`./gh-clone.sh --public` 目前會建立名為 `--public` 的 repo）。

### 3.4 驗證
- 手動執行 `session-start.sh`，確認輸出合法 JSON 且正確讀出 glossary 實際狀態。
- 修改一個 `scripts/` 下的 `.py` 檔，確認 pytest hook 在時限內完成；修改 `scripts/` 外的 `.py` 檔，確認不觸發。

## 4. 批次 2：模板清空（完全空白模板）

### 4.1 資料檔重置
- `glossary.json`：只留 `_meta`（清除 26 條 YZE 術語）。
- `chapters.json`：重置為最小佔位範例——保留完整欄位結構（`source`、`output_dir`、`mode`、一個含 `title`/`slug`/`pages` 的示例章節），值改為明顯的佔位內容（如 `data/markdown/YOUR-RULEBOOK_pages.md`），供使用者參考格式。
- `data/translation-progress.json`：刪除（session-start 對缺檔已有「run /init-doc」正常提示）。
- `style-decisions.json`：重置為僅含 `_meta` 的空骨架；YZE 站名、Fria Ligan 版權文字、「雙語模式測試」註記全部清除。
- 建立 `data/pdfs/.gitkeep` 與 `data/markdown/.gitkeep`，使 CLAUDE.md 宣稱的目錄結構在 fresh clone 上真實存在。

### 4.2 docs 網站重置
- `astro.config.mjs`：title 改為佔位（「遊戲規則文件」＋TODO 註記）；sidebar 清為 `[]`（修 build 失敗根因）；移除 `og:image`／`twitter:image` meta（引用的檔案不存在）；`allowIndexing: false` 與 robots.txt 維持。
- `index.mdx`：改為極簡 zh-TW 佔位首頁，無任何失效連結、無版權文字。
- 刪除孤兒檔 `docs/src/styles/custom-light.css`（785 行，無人引用）。
- 刪除假的 `docs/src/assets/hero.jpg`（69 bytes 的 1×1 PNG 冒充 JPEG）及其引用；圖片由 `/init-doc` 流程向使用者取得。
- `docs/README.md`：從 Starlight 樣板改寫為簡短說明（本站是什麼、dev/build 指令、與轉換管線的關係）。
- `docs/package.json`：移除未使用的 `@astrojs/vercel`。
- `vercel.json`：移除無效的 `/fonts/(.*)` 快取規則。

### 4.3 工作文件與模板機制
- 刪除 `docs/agent-system/`、`docs/plans/`、`docs/superpowers/`（6 份，git 歷史保留）。
- 刪除 `openspec/` 全目錄。
- `plans/` 目錄為本次起的設計文件存放處，並加入 `clean_sample_data.py` 清除清單。
- `.github/template.yml` 不動。
- `clean_sample_data.py` 擴充為完整模板重置工具，新增：重置 `chapters.json`（至 4.1 的佔位範例）、刪除 `data/translation-progress*.json`、重置 `style-decisions.json`、重置 `astro.config.mjs` 的 title 與 sidebar、刪除 `plans/`。要求冪等，可重複執行。
- `new-project` 技能：clone 後自動執行 `uv run python scripts/clean_sample_data.py --yes`（原為手動可選）；同步更新 README 對此腳本的描述（含既有但未記載的行為：重置 glossary、刪除範例圖片）。

### 4.4 驗證
- `cd docs && bun run build` 全綠。
- 在乾淨工作區連續執行兩次 `clean_sample_data.py --yes`，結果一致（冪等）。
- 注意：清理腳本會刪除模板 repo 自身保留的 `plans/` 等追蹤內容，驗證完成後以 `git checkout -- .` 還原工作區再繼續。

## 5. 批次 3：技能系統

### 5.1 刪除與整併
- 刪除 `.claude/skills/optimized-translating/`（含 references、templates）與 `.claude/skills/pdf-translation/`。
- 模型路由依 §2.1 寫入各技能的子代理派遣步驟（super-translate 的 translator/reviewer/refiner/md-reviewer 派遣處、translate 與 bilingual-translate 的執行說明）。

### 5.2 Frontmatter 與斷鏈修復
- `md-review`、`term-decision`、`check-consistency`：移除 `disable-model-invocation: true`。
- `final-proofread`：補上 `disable-model-invocation: true`。
- 三處「`AGENTS.md` Integrated Conventions」引用（`md-review/SKILL.md`、`md-review/reviewer-prompt.md`、`super-translate/SKILL.md`）改指向 `.claude/rules/docs-conventions.md`。

### 5.3 Rules 對齊
- 刪除 `.claude/rules/model-routing.md`。
- `.claude/rules/docs-conventions.md` 與技能檢查清單的三處措辭衝突對齊：
  - sidebar 排序：改寫為「由 `_meta.yml` 驅動，不要求逐頁 `sidebar.order`」。
  - H1 規則：改寫為「正文禁止出現重複 frontmatter 標題的標題」。
  - `……` 刪節號規則：保留，並補進 md-review 檢查清單。

### 5.4 技能內容修正
- `final-proofread` 支援 bilingual 模式：讀取 `style-decisions.json` 的 `translation_mode.mode`，bilingual 時改查 `data/translation-progress-bilingual.json` 與 `bilingual/` 路徑。
- `chapter-split` 的兩個草稿路徑統一至根目錄 `.state/chapter-split/`。
- super-translate 審查輪數：CLAUDE.md 的「3 輪」改為「2 輪」。

### 5.5 跨工具與文件同步
- 刪除 `.agents/` 全目錄。
- `.gemini/commands/` 補 4 個缺漏 TOML：`md-review`、`bilingual-translate`、`fix-ref`、`final-proofread`。
- CLAUDE.md：指令表補 `terminology-management` 列；Law 7 預檢清單補 `/bilingual-translate`；工作流程步驟 5 補 bilingual 分支；Tech Stack 補 `opendataloader-pdf`（需 Java 11+）與 `starlight-auto-sidebar`。
- README：指令表補齊 12 個指令；補 opendataloader 說明（含 Java 依賴）；更新 `clean_sample_data.py` 描述與 new-project 自動清理行為；移除不存在的 `.codex/agents` 描述；補 Windows `core.symlinks` 註記。
- `scripts/README.md`：補齊腳本清單與系統依賴（Java、tesseract、bun）。

### 5.6 驗證
- 全 repo grep 無殘留：`optimized-translating`、`pdf-translation`、「AGENTS.md Integrated Conventions」、`model-routing`。
- `.claude/skills/` 目錄清單與 CLAUDE.md 指令表一致（13 個技能）。

## 6. 批次 4：腳本修正＋測試＋CI＋安全

### 6.1 修正型腳本修復
- 五處 `subprocess.run(..., text=True)` 補 `encoding="utf-8"`：`init_handoff_gate.py:41`、`_ocr_lib.py:78`、`_ocr_lib.py:107`、`_opendataloader_lib.py:46`、遷移測試中同型呼叫（消除 Windows cp950 亂碼／崩潰）。
- `init_handoff_gate.py`：加 `shutil.which("bun")` 前置檢查，缺 bun 時輸出明確 gate 失敗訊息而非 traceback。
- `term_cal_batch.py`：`--skip-managed` 死開關改 `argparse.BooleanOptionalAction`（`--skip-managed`／`--no-skip-managed`，預設 True）。
- `generate_nav.py`：兩個矛盾的 leaf 判準統一為一個。
- YAML 跳脫統一：`split_chapters._yaml_safe` 與 `generate_nav.yaml_safe` 抽至 `_markdown_utils.py` 共用（兩者目前對同一中文標題產出不同結果，屬正確性問題）。
- 死程式碼移除：`split_chapters.py` 未使用 imports、`generate_nav.first_leaf_path`、`_term_lib.count_terms_batch` 內重複 import。
- `extract_pdf.py`、`split_chapters.py`、`draft.py` 的 project root 補 `.resolve()`。
- `style_decisions.py`：`--page-text-engine` choices 補 `opendataloader`。
- `pyproject.toml`：移除殘留的 `[project.optional-dependencies]` opendataloader 群組（與硬依賴宣告衝突）。

### 6.2 測試遷移
- 根目錄 `tests/` 中屬唯一覆蓋的測試遷入 `scripts/tests/`：`clean_sample_data`、`draft`、`style_decisions`、`term_generate`／`term_edit`／`term_read`、`validate_glossary`、`_term_lib`、`init_create_progress`、`init_handoff_gate`、`bilingual_prep`、bilingual 相關三檔。
- 遷移時：改為 pytest 風格（`tmp_path`）、刪除硬編碼 macOS 路徑（`/Users/weihung/...`）、修過時 import（重構後函式已移至 `_layout_lib`／`_epub_lib`）、補 `encoding="utf-8"`。
- 與 `scripts/tests/` 重複的 `extract_pdf`、`split_chapters` 覆蓋直接捨棄。
- 完成後刪除根目錄 `tests/`。
- 新增測試：`_opendataloader_lib`（分頁啟發式，mock subprocess）、`progress_edit`（狀態變更與 `_meta` 重算）。

### 6.3 CI（`.github/workflows/terminology-check.yml`）
- Python 版本：`uv python install 3.12` → `uv python install`（無參數時讀 `.python-version`）。
- 新增 `uv run pytest` 步驟。
- 新增 `validate_style_decisions.py` 步驟。
- 術語檢查維持 `--fail-on-forbidden`（空白模板的空 glossary 必須能通過 CI；`--fail-on-missing` 屬專案內翻譯預檢，不進 CI）。

### 6.4 安全強化（Vercel 密碼閘道）
- 認證 cookie 改 HMAC-SHA256 簽章（Web Crypto，以 `SITE_PASSWORD` 為金鑰，payload 含到期時間戳），取代可偽造的 32-bit `hash*31`。
- `redirect` 參數白名單：只接受以 `/` 開頭且非 `//` 開頭的站內路徑，否則落回 `/`。
- 驗證邏輯抽至共用檔（如 `lib/site-auth-shared.ts`）供 `middleware.ts` 與 `api/site-auth.ts` import，消除兩份手動同步的複製。
- `api/site-auth.ts` 改用 Web 標準 Request/Response 簽名，移除 `@vercel/node` import（一併解決無根 package.json 宣告的缺口）。
- 登入頁 `redirectPath` 插值加 HTML escape。

### 6.5 驗證
- `uv run pytest` 全綠（含遷移與新增測試，單一測試目錄 `scripts/tests/`）。
- `cd docs && bun run build` 全綠。

## 7. 總驗收清單

1. `cd docs && bun run build` 通過。
2. `uv run pytest` 通過，且測試只存在於 `scripts/tests/`。
3. 手動執行 session-start hook，Windows 下輸出正確狀態。
4. 全 repo grep 無懸空引用（已刪技能、AGENTS.md 規範章節、model-routing）。
5. `clean_sample_data.py --yes` 冪等，執行後即為理想空白模板（無 Cairn／YZE／Fria Ligan 殘留）。
6. `.claude/skills/` 與 CLAUDE.md、README 三者的技能清單一致。

## 8. 範圍外（本次不做）

- 美化型重構：`_io_lib` 共用抽取（9 份 JSON 讀寫複製）、CLI 引數風格一致化、`split_chapters.py` 改 argparse。
- md-review 機械檢查腳本化（Python lint 化，遠期選項）。
- 分支整理（`tmp`、`tmp-new` 與 main 的合併策略，由使用者另行決定）。
- `.github/template.yml`（維持現狀）。
