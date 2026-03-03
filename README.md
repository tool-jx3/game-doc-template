# 遊戲文件模板 (Game Documentation Template)

基於 Astro + Starlight 的遊戲規則文件模板，專為 TRPG 設計，也適用於任何遊戲規則文件。

## 快速開始

### 1. 建立專案

```bash
./gh-clone.sh my-game-docs           # 建立 private repo
./gh-clone.sh my-game-docs --public  # 建立 public repo
cd my-game-docs
```

或使用 GitHub 網頁的「Use this template」按鈕。

### 2. 安裝依賴

```bash
# 前端（文件網站）
cd docs
bun install  # 或 npm install

# 回到專案根目錄
cd ..

# Python/uv 工具鏈（PDF 處理）
# 注意：已改為在「專案根目錄」初始化，不在 scripts/ 子目錄
uv sync  # 或 pip install markitdown pymupdf

# 術語 POS/lemma（spaCy 模型）
uv run python -m ensurepip --upgrade
uv run python -m spacy download en_core_web_sm
```

### 3. 啟動開發伺服器

```bash
cd docs
bun dev
```

開啟 http://localhost:4321 預覽網站。

---

## 自訂設定

### 網站標題與基本設定

編輯 `docs/astro.config.mjs` 頂部的 `SITE_CONFIG`：

```javascript
const SITE_CONFIG = {
  title: "您的遊戲名稱",
  defaultLocale: "zh-TW",
  localeLabel: "繁體中文",
  allowIndexing: false, // SEO 設定
};
```

### 圖片資源

| 檔案       | 位置                       | 說明                        |
| ---------- | -------------------------- | --------------------------- |
| 背景圖     | `docs/public/bg.jpg`       | 1920x1080，深色低對比度為佳 |
| 社群分享圖 | `docs/public/og-image.jpg` | 1200x630                    |
| 首頁主圖   | `docs/src/assets/hero.jpg` | 560x560，會裁切成圓形       |
| 網站圖示   | `docs/public/favicon.svg`  | 32x32                       |

### 背景圖設定

預設使用純色背景。如需背景圖片：

1. 將圖片放入 `docs/public/bg.jpg`
2. 編輯 `docs/src/styles/custom.css`，取消 `body` 區塊中背景圖片的註解

若要調整半透明遮罩透明度，修改同檔案中的 `.main-pane` 區塊。

### 主題配色

編輯 `docs/src/styles/custom.css` 的 `:root` 區塊修改顏色變數。

預設色票風格（只需修改 H 值）：

- **冷色系**：藍青紫，適合科幻、海洋、神秘
- **暖色系**：橘金紅，適合冒險、戰鬥、熱情
- **自然系**：綠黃棕，適合奇幻、森林、治癒
- **暗黑系**：紫洋紅紅，適合恐怖、哥德、邪惡
- **史詩系**：金銅紅，適合中世紀、王國、榮耀

### 側邊欄結構

編輯 `docs/astro.config.mjs` 的 `sidebar` 區塊調整目錄結構。

---

## 使用 AI 輔助翻譯（支援 Claude Code、Codex CLI、Gemini CLI）

本專案已內建：

- `AGENTS.md -> CLAUDE.md`
- `.codex/skills -> .claude/skills`
- `.codex/agents -> .claude/agents`
- `.gemini/settings.json`（`context.fileName = "CLAUDE.md"`）
- `.gemini/skills -> .claude/skills`
- `.gemini/commands/*.toml`（將 slash 指令映射到既有 skills）

### 使用原則

- 建議流程：`new-project` → `init-doc` → `translate`（或高品質版 `super-translate`）
- `translate`：單輪線性翻譯，適合快速草稿；`super-translate` (beta)：多 agent 審查循環（最多 2 輪），適合正式發布
- 翻譯前先確認術語（`glossary.json`），交付前執行一致性與完整性檢查

### 快速開始

1. 建立新專案

```bash
new-project ~/Downloads/your-game.pdf
```

2. 初始化資料與術語

```bash
init-doc
```

3. 開始翻譯

```bash
translate
```

4. 高品質翻譯（推薦正式發布使用）

```bash
super-translate [target]
```

多 agent 審查循環（Translator → Reviewer → Refiner），最多迭代 2 輪，自動修正術語不一致、殘留英文、簡體字等問題。(beta)

### 常用指令對照

| 功能                             | 指令                         |
| -------------------------------- | ---------------------------- |
| 建立新專案                       | `new-project <pdf-path>`     |
| 初始化翻譯專案                   | `init-doc`                   |
| 翻譯章節或檔案                   | `translate [target]`         |
| 翻譯＋多輪審查（beta）           | `super-translate [target]`   |
| 術語一致性檢查                   | `check-consistency`          |
| 術語決策與批次替換               | `term-decision`              |
| 內容完整性檢查                   | `check-completeness`         |

---

## 本專案工作流程（簡版）

1. 準備來源檔  
   把規則 PDF 放到 `data/pdfs/`。

2. 初始化專案（建議）  
   執行 `init-doc`（或手動執行清理、提取、切章），建立可翻譯的初始內容。

3. 提取 PDF 與章節裁切（Python）
   1. `uv run python scripts/extract_pdf.py data/pdfs/your-rulebook.pdf`
   2. `uv run python scripts/split_chapters.py --init`
   3. 編輯 `chapters.json`（設定章節與頁碼範圍）
   4. `uv run python scripts/split_chapters.py`  
      產出檔案到 `docs/src/content/docs/`。

4. 術語預處理
   原則：`glossary.json` 是唯一術語來源，先定義再翻譯，避免同詞多譯。  
   建議指令：
   1. `uv run python scripts/term_generate.py --min-frequency 2`（找高頻候選詞）
   2. `uv run python scripts/term_edit.py --term "<TERM>" --cal`（做全站證據計算）
   3. `uv run python scripts/term_edit.py --term "<TERM>" --set-zh "<ZH>" --status approved --mark-term`（核准術語）

5. 執行翻譯（套用術語表）
   翻譯時以 `glossary.json` 優先，並保留 Markdown 結構。原理：翻譯不是逐句自由發揮，而是「內容翻譯 + 術語套版」。
   - `translate`：單輪翻譯，適合快速草稿或已有良好術語表的情況。
   - `super-translate` (beta)：多 agent 翻譯審查循環，Translator → Reviewer → Refiner 最多迭代 2 輪，自動修正術語不一致、殘留英文、簡體字等問題，適合正式發布前的高品質輸出。

6. 術語校驗與完整性檢查  
   原則：翻譯後再做一次全站術語稽核，收斂不一致。  
   建議指令：
   1. `uv run python scripts/validate_glossary.py`（檢查術語表格式）
   2. `uv run python scripts/term_read.py`（檢查缺漏詞、禁用詞、未知高頻詞）
   3. `check-completeness`（檢查內容缺頁與規則缺漏）

7. 預覽與調整樣式  
   在 `docs/` 下執行 `bun dev`，檢查頁面、目錄、連結、圖片與主題樣式。

8. 建置與部署  
   `bun run build` 後部署到 Vercel（或其他靜態站台服務）。

---

## PDF 內容提取（手動流程）

若不使用 AI 輔助，可手動執行：

```bash
# 請在專案根目錄執行

# 1. 提取 PDF
uv run python scripts/extract_pdf.py data/pdfs/your-rulebook.pdf

# 2. 產生章節設定範例
uv run python scripts/split_chapters.py --init

# 3. 編輯 chapters.json 設定章節結構

# 4. 拆分章節
uv run python scripts/split_chapters.py
```

`uv sync` 會在專案根目錄建立 `.venv` 與 `uv.lock`，之後所有 Python 腳本請從根目錄以 `uv run python scripts/...` 執行。

### 清除範例資料（可選）

```bash
uv run python scripts/clean_sample_data.py --yes
```

會清除：

- `data/markdown/*`
- `docs/src/content/docs/**/*.md|.mdx`

不會清除：

- `data/pdfs/*`（授權來源 PDF）

---

## 部署

### Vercel（推薦）

1. 推送到 GitHub
2. 在 Vercel 匯入專案
3. 自動部署

### 密碼保護（可選）

在 Vercel 環境變數設定 `SITE_PASSWORD` 即可啟用密碼保護：

1. 進入 Vercel 專案設定 → Environment Variables
2. 新增 `SITE_PASSWORD`，值為您想要的密碼
3. 重新部署

未設定此變數則不啟用保護。

### 手動建置

```bash
cd docs
bun run build
# 輸出在 docs/dist/
```

---

## 授權

MIT License
