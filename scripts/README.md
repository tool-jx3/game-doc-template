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
```

輸出：
- `data/markdown/your-rulebook.md` — 純文字版本
- `data/markdown/your-rulebook_pages.md` — 含頁碼標記（用於章節拆分）
- `data/markdown/images/your-rulebook/` — 提取的圖片

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
