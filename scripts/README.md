# 內容處理腳本

本資料夾包含 PDF 提取與章節拆分工具。

## 安裝

使用 [uv](https://github.com/astral-sh/uv)（推薦）：

```bash
uv sync
uv run python -m ensurepip --upgrade
uv run python -m spacy download en_core_web_sm
```

`uv sync` 會安裝完整術語比對依賴（含 `spaCy` 與 `spacy-lookups-data`），不需額外安裝指令。
`en_core_web_sm` 需要額外下載一次，下載後可啟用 POS 標註與較準確的術語過濾。

或使用 pip：

```bash
pip install markitdown pymupdf
```

若要使用 OCR，還需要系統層級安裝 `tesseract` 與對應語言資料。
以 macOS + Homebrew 為例：

```bash
brew install tesseract
brew install tesseract-lang
tesseract --list-langs
```

建議至少確認以下語言資料可用：
- 繁體中文：`chi_tra`
- 日文：`jpn`
- 英文：`eng`

常見 OCR 語言組合：
- 繁體中文規則書：`--ocr-lang chi_tra+eng`
- 日文規則書：`--ocr-lang jpn+eng`
- 英文規則書：`--ocr-lang eng`
- 多語混排：`--ocr-lang chi_tra+jpn+eng`

預設 OCR 語言是 `chi_tra+eng`。若來源主要是日文或英文，建議明確指定較小的語言集合，通常會比一次開很多語言更穩定。

## 工作流程

### 0. 清除範例資料（建議先執行）

```bash
uv run python scripts/clean_sample_data.py --yes
```

會清除既有提取結果與範例 docs 內容，但不會刪除 `data/pdfs/` 的來源 PDF。
同時會重置 `glossary.json` 為空白術語表（保留 `_meta`）。

### 1. 提取 PDF 內容

```bash
# 將 PDF 放入 data/pdfs/ 目錄
mkdir -p data/pdfs
cp your-rulebook.pdf data/pdfs/

# 執行提取
uv run python scripts/extract_pdf.py data/pdfs/your-rulebook.pdf

# 大型 PDF 若只需要切章來源，可略過整本 markitdown
uv run python scripts/extract_pdf.py data/pdfs/your-rulebook.pdf --skip-full-markitdown

# 明確指定雙欄書
uv run python scripts/extract_pdf.py data/pdfs/your-rulebook.pdf --layout-profile double-column

# 雙欄或複雜版面若要直接指定較保守路徑
uv run python scripts/extract_pdf.py data/pdfs/your-rulebook.pdf --page-text-engine markitdown

# 掃描型 PDF 可直接走 OCR
uv run python scripts/extract_pdf.py data/pdfs/your-rulebook.pdf --page-text-engine ocr

# 日文掃描 PDF
uv run python scripts/extract_pdf.py data/pdfs/your-rulebook.pdf --page-text-engine ocr --ocr-lang jpn+eng

# 英文掃描 PDF
uv run python scripts/extract_pdf.py data/pdfs/your-rulebook.pdf --page-text-engine ocr --ocr-lang eng

# 單張圖片 OCR
uv run python scripts/extract_pdf.py data/scans/page001.jpg

# 整個 jpg/png 掃描資料夾 OCR
uv run python scripts/extract_pdf.py data/scans/your-rulebook-pages
```

輸出：
- `data/markdown/your-rulebook.md` — 純文字版本
- `data/markdown/your-rulebook_pages.md` — 含頁碼標記（用於章節拆分）
- `data/markdown/images/your-rulebook/` — 提取的圖片

說明：
- `_pages.md` 預設使用 `auto`，會先看 `style-decisions.json` 的每文件設定，否則再抽樣頁面偵測雙欄。
- 偵測結果偏向雙欄時，會用 `markitdown`。
- 偵測結果偏向單欄時，預設會用 `pymupdf`；但若抽樣文字顯示有明顯版面噪訊（例如大量長空白或側欄文字被混入正文），會自動改用 `markitdown`。
- 若要手動覆蓋，可指定 `--layout-profile single-column|double-column` 或 `--page-text-engine ocr|pymupdf|markitdown`。
- 若大型 PDF 不需要整本 `your-rulebook.md`，可用 `--skip-full-markitdown` 省掉最慢的一步。
- 圖片檔與圖片資料夾會固定走 OCR，並自動生成 `.md` 與 `_pages.md`。
- OCR 預設使用 `chi_tra+eng`。
- 日文來源建議使用 `--ocr-lang jpn+eng`；英文來源建議使用 `--ocr-lang eng`。
- 若同頁真的同時混排繁中、日文、英文，可改用 `--ocr-lang chi_tra+jpn+eng`，但仍建議優先使用最小必要語言集合。

每文件設定可寫在 `style-decisions.json`：

```json
{
  "document_format": {
    "layout_profile": "single-column",
    "documents": {
      "Household_1.2": {
        "layout_profile": "double-column",
        "page_text_engine": "markitdown"
      },
      "ScannedBook": {
        "page_text_engine": "ocr"
      }
    }
  }
}
```

規則：
- `document_format.layout_profile` 是全域預設。
- `document_format.documents.<pdf_stem>` 會覆蓋特定文件。
- `page_text_engine` 可不填；留空時由 `layout_profile` 自動決定。
- 掃描 PDF 可將 `page_text_engine` 設成 `ocr`。

### style-decisions 管理

`style-decisions.json` 之後應該只透過腳本建立、修改、補充，並搭配 schema 驗證：

```bash
# 初始化或檢查既有檔案
uv run python scripts/style_decisions.py init

# 設定 repo 資訊
uv run python scripts/style_decisions.py set-repository \
  --slug your-game-docs \
  --visibility private \
  --url https://github.com/you/your-game-docs \
  --show-on-homepage false

# 設定文件格式（可全域，也可指定 document key）
uv run python scripts/style_decisions.py set-document-format \
  --layout-profile auto \
  --cards-usage "僅在比較內容時使用" \
  --tabs-usage "只在同頁替代內容時使用"

uv run python scripts/style_decisions.py set-document-format \
  --document-key Household_1.2 \
  --layout-profile double-column \
  --page-text-engine markitdown

uv run python scripts/style_decisions.py set-document-format \
  --document-key ScannedBook \
  --page-text-engine ocr

# 加入翻譯備註
uv run python scripts/style_decisions.py add-translation-note \
  --key tone \
  --topic 語氣 \
  --note "保持正式、克制，不要擅自增加戲謔感。"

# 驗證
uv run python scripts/validate_style_decisions.py
```

`translation_notes` 會集中存放翻譯備註，讓 `translate` / `super-translate` 一次讀完整份 `style-decisions.json` 就能拿到所有全域約束；若是特定文件備註，可用 `--document-key <pdf_stem_or_doc_id>`。

### 2. 設定章節結構

```bash
# 產生範例設定檔
uv run python scripts/split_chapters.py --init
```

編輯 `chapters.json`，設定章節結構與頁碼範圍：

```json
{
    "source": "data/markdown/your-rulebook_pages.md",
    "output_dir": "docs/src/content/docs",
    "chapters": {
        "rules": {
            "title": "核心規則",
            "files": {
                "index": {
                    "title": "規則總覽",
                    "description": "遊戲規則概述",
                    "pages": [1, 20]
                },
                "combat/damage": {
                    "title": "傷害規則",
                    "description": "戰鬥章節中的傷害處理",
                    "pages": [21, 28]
                }
            }
        }
    }
}
```

切分原則：
- 優先依來源目錄或明確子標題切分。
- 若單一章節過長，可在 `files` 使用巢狀路徑（例如 `combat/damage`）輸出到子目錄。
- 不要為了平均字數，把同一章硬拆成 `1`、`2`、`3`、`part-1` 或「一、二、三」這類沒有語意的檔名；若來源沒有可靠子標題，寧可維持單檔。

### 3. 拆分章節

```bash
uv run python scripts/split_chapters.py
```

這會根據 `chapters.json` 的設定，將內容拆分到 `docs/src/content/docs/` 目錄。

## 設定檔說明

### chapters.json

| 欄位 | 說明 |
|------|------|
| `source` | 來源 Markdown 檔案（使用 `_pages.md` 版本） |
| `output_dir` | 輸出目錄 |
| `clean_patterns` | 要移除的正規表達式陣列 |
| `chapters` | 章節定義 |
| `images.repeat_file_size_threshold` | 以檔案大小重複次數略過疑似背景圖 |
| `images.repeat_visual_threshold` | 以視覺指紋重複次數略過疑似背景圖 |
| `images.background_min_coverage_ratio` | 只有覆蓋頁面達一定比例才視為背景候選 |
| `images.background_min_text_tokens` | 只有該頁文字量夠多才把大面積圖片視為背景候選 |
| `images.background_edge_margin_ratio` | 判定貼齊頁邊的大區塊背景時使用的邊界容差 |
| `images.background_edge_min_area_ratio` | 貼邊大區塊至少需達到的面積比例 |
| `images.background_edge_min_span_ratio` | 貼邊大區塊至少需達到的長邊比例 |
| `images.background_dominant_color_ratio_threshold` | 單色占比達門檻時視為大面積背景候選 |

### 章節定義

```json
{
    "section-slug": {
        "title": "章節標題",
        "order": 1,
        "files": {
            "filename": {
                "title": "頁面標題",
                "description": "SEO 描述",
                "pages": [起始頁, 結束頁],
                "order": 0
            }
        }
    }
}
```

`files` 的 key 可使用巢狀路徑，例如 `equipment/weapons`，輸出會是 `docs/src/content/docs/<section>/equipment/weapons.md`。

圖片背景過濾說明：
- 目前不只看 `file_size`，也會讀取 manifest 內的 `visual_hash`、`coverage_ratio`、`dominant_color_ratio`。
- 只有在「覆蓋頁面面積大」且「該頁文字量夠多」時，才會把圖片視為背景候選。
- 另外也會抓「貼齊頁邊、長邊很長、而且該頁文字量夠多」的半頁或側欄背景。
- 若同一種視覺樣態在多頁反覆出現，而且符合上述背景候選條件，會被略過。
- 若圖片大部分幾乎都是同一個顏色，而且符合上述背景候選條件，也會被略過。
- 建議先維持預設值；若書籍有大量滿版插畫被誤判，再微調 `repeat_visual_threshold` 與 `background_min_coverage_ratio`。

## 提示

1. **先預覽 PDF 頁碼**：在設定 `chapters.json` 前，先打開 PDF 確認各章節的頁碼範圍

2. **清理模式**：使用 `clean_patterns` 移除不需要的內容（如頁首、頁尾、浮水印）

3. **手動調整**：自動提取的內容可能需要手動修正格式

## 術語腳本

以下腳本在專案根目錄執行：

### 1) 生成候選術語

```bash
uv run python scripts/term_generate.py --min-frequency 3
```

用途：
- 掃描 Markdown 內容
- 產生高頻候選詞
- 自動排除 `glossary.json` 已存在詞彙

### 2) 編輯術語（自動執行 `--cal`）

```bash
# 直接標記成術語（未管理詞彙會自動先執行 --cal）
uv run python scripts/term_edit.py --term "Stress" --mark-term --set-zh "壓力" --status approved

# 若只想查看證據而不編輯，可單獨執行 --cal
uv run python scripts/term_edit.py --term "Stress" --cal
```

規則：
- 編輯未管理詞彙時會自動執行 `--cal`，無需手動分兩步
- 一旦標記為術語（`is_term=true` 或 `status=approved`），後續 `--cal` 會跳過全文搜尋
- 寫入 `glossary.json` 時，術語 key 會自動正規化為單數（例如輸入 `Aspects` 會儲存為 `Aspect`）

### 3) 讀取術語並做一致性檢查

```bash
uv run python scripts/term_read.py
```

用途：
- 載入 `glossary.json`
- 輸出術語使用次數、缺失項、禁用詞命中
- 提供未知高頻詞作為下一輪候選

比對策略（單複數/同型詞）：
- 若環境有安裝 `spaCy`，優先使用 lemma 比對（較準確）
- 若未安裝 `spaCy`，自動回退 `inflect` 做單複數變體比對
- 不需要額外參數，腳本會自動選擇後端

### 4) 驗證術語結構（Schema）

```bash
uv run python scripts/validate_glossary.py
```

用途：
- 以 `glossary.schema.json` 驗證 `glossary.json`
- 在 CI 中作為格式守門

### 5) CI 守門模式

```bash
uv run python scripts/term_read.py --fail-on-forbidden
```

用途：
- 若命中 `forbidden` 用語則以非 0 結束
- 可直接用於 GitHub Actions / pre-merge 檢查
