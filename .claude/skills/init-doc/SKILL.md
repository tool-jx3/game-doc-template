---
name: init-doc
description: Initial summary - initialize the document translation project, build glossary and chapter structure
user-invocable: true
disable-model-invocation: true
---

# Initialize Document Translation

Use `pdf-translation` and `terminology-management` skills.

## Interaction Rules

- Always interact with the user in Traditional Chinese (繁體中文).
- All AskUserQuestion prompts and conversational text shown to the user must be in Traditional Chinese.
- Do not use Simplified Chinese.

## Process

### 0. Clean Sample Data (Required)

Before initialization, clear template/sample outputs:

```bash
uv run python scripts/clean_sample_data.py --yes
```

This cleanup removes:
- `data/markdown/*` (extracted markdown/images)
- `docs/src/content/docs/**/*.md|.mdx` (template docs content)
- resets `glossary.json` to an empty glossary skeleton (`_meta` only)

It does **not** remove `data/pdfs/*`.

### 1. Locate PDF

If no `$ARGUMENTS` provided, ask user for PDF location in `data/pdfs/`.

### 2. Extract Content

```bash
uv run python scripts/extract_pdf.py <pdf_path>
```

Review output in `data/markdown/`:
- `<name>.md` - clean version
- `<name>_pages.md` - with page markers

### 3. Review PDF Cropping and Split into Manageable Parts

After PDF cropping is completed, review the cropped result before continuing:

1. Inspect the cropped output for readability issues:
   - text clipped at margins
   - missing headers/footers needed for context
   - broken diagrams/tables
2. If the cropped PDF is too large, split it into suitable parts:
   - split by natural chapter boundaries when possible
   - keep each part at a manageable size (recommended: ~15-30 pages per part)
3. Save split PDF parts with clear names (for example `part-01-intro.pdf`, `part-02-core-rules.pdf`).
4. Re-run extraction for each split part if needed, and ensure resulting markdown files are complete.

### 4. Extract and Select Images

#### 4.1 Extract Images from PDF

Images are automatically extracted during step 2 (`extract_pdf.py`).

Images saved to `data/markdown/images/<pdf_name>/`.

#### 4.2 Present Images to User

List all extracted images with thumbnails or descriptions:

```
找到以下圖片：
1. image_001.jpg（封面，1200x800）
2. image_002.png（角色插圖，600x400）
3. image_003.jpg（地圖，1000x700）
...

請選擇用途：
```

#### 4.3 Ask Image Assignments

Use AskUserQuestion for each image type:

**Hero Image** (homepage main image, cropped into a circle):
- Recommendation: choose a key visual, character, or iconic image
- Location: `docs/src/assets/hero.jpg`

**Background Image**:
- Recommendation: choose an atmosphere image, scene image, or texture
- Location: `docs/public/bg.jpg`

**OG Image** (social sharing preview image):
- Recommendation: 1200x630 is ideal, choose an image that represents the game
- Location: `docs/public/og-image.jpg`

#### 4.4 Process Selected Images

Copy selected images to appropriate locations:

```bash
# Hero image (resize if needed)
cp data/markdown/images/<pdf_name>/<selected_hero>.jpg docs/src/assets/hero.jpg

# Background image
cp data/markdown/images/<pdf_name>/<selected_bg>.jpg docs/public/bg.jpg

# OG image (resize to 1200x630 if needed)
cp data/markdown/images/<pdf_name>/<selected_og>.jpg docs/public/og-image.jpg
```

### 5. Configure Visual Theme

#### 5.1 Background Mode

Use AskUserQuestion:

```
背景色調設定：

選項：
1. 深色模式（Dark）- 適合大多數遊戲，神祕且有沉浸感
2. 淺色模式（Light）- 清新、明亮風格

目前背景圖的主色調是什麼？
```

#### 5.2 Overlay Settings

Based on background image analysis, ask:

```
背景圖對比度設定：

觀察您選擇的背景圖，請確認：

1. 需要深色遮罩 - 背景太亮，文字可能不清楚
2. 需要淺色遮罩 - 背景太深但想要淺色主題
3. 不需要遮罩 - 背景對比度適中
4. 自訂遮罩透明度（0-1）

建議：通常 0.6-0.8 的遮罩效果最佳
```

Update `docs/src/styles/custom.css`:

```css
/* Overlay opacity */
--overlay-opacity: <user_choice>;
```

#### 5.3 Color Palette Design

Use AskUserQuestion to determine color style:

```
色票風格設定：

請選擇適合遊戲氛圍的色彩風格：

1. 🌊 冷色系（Cool）
   - 主色：藍色系
   - 適合：科幻、海洋、冬季、神祕

2. 🔥 暖色系（Warm）
   - 主色：橘紅色系
   - 適合：冒險、沙漠、戰鬥、熱情

3. 🌲 自然系（Nature）
   - 主色：綠色系
   - 適合：奇幻、森林、生態、療癒

4. 🌙 暗黑系（Dark）
   - 主色：紫黑色系
   - 適合：恐怖、哥德、死亡、邪惡

5. ⚔️ 史詩系（Epic）
   - 主色：金色系
   - 適合：中世紀、王國、戰爭、榮耀

6. 🎨 自訂（Custom）
   - 提供主色 HEX 或描述風格
```

#### 5.4 Generate Color Variables

Based on user choice, generate an HSL color scheme:

**Cool**:
```css
--color-primary-h: 217;   /* Blue */
--color-secondary-h: 180; /* Cyan */
--color-tertiary-h: 260;  /* Purple */
--color-quaternary-h: 200; /* Sky blue */
```

**Warm**:
```css
--color-primary-h: 25;    /* Orange */
--color-secondary-h: 45;  /* Gold */
--color-tertiary-h: 0;    /* Red */
--color-quaternary-h: 350; /* Rose */
```

**Nature**:
```css
--color-primary-h: 142;   /* Green */
--color-secondary-h: 80;  /* Yellow-green */
--color-tertiary-h: 30;   /* Brown */
--color-quaternary-h: 160; /* Teal */
```

**Dark**:
```css
--color-primary-h: 280;   /* Purple */
--color-secondary-h: 320; /* Magenta */
--color-tertiary-h: 0;    /* Blood red */
--color-quaternary-h: 260; /* Deep purple */
```

**Epic**:
```css
--color-primary-h: 45;    /* Gold */
--color-secondary-h: 30;  /* Bronze */
--color-tertiary-h: 0;    /* Red */
--color-quaternary-h: 15; /* Orange gold */
```

#### 5.5 Apply Theme Settings

Update `docs/src/styles/custom.css` with selected colors.

If user chose background image, uncomment background-image in CSS:

```css
body {
  background-color: var(--sl-color-black);
  background-image: url('/bg.jpg');
  background-size: cover;
  background-position: center;
  background-attachment: fixed;
  background-repeat: no-repeat;
}
```

### 6. Identify Key Terms (Interactive)

Invoke `terminology-management` skill and run candidate generation from extracted docs:

- Capitalized game terms (Move, Playbook, Harm)
- Quoted terms
- Repeated specialized vocabulary (frequency >= 2)

Use script flow:

```bash
uv run python scripts/term_generate.py --min-frequency 2
```

Present terms to user for translation confirmation.

### 7. Configure Proper Noun Translation Policy (Required)

Before building the glossary, ask user to choose proper noun handling policy:

1. Keep original names by default
2. Translate names when official/accepted Chinese forms exist
3. Prefer translated names, with original in parentheses on first mention

Record the decision in `style-decisions.json`:

```json
{
  "proper_nouns": {
    "mode": "keep_original | official_only | translate_with_original_first",
    "reason": "user preference"
  }
}
```

### 8. Build Glossary (Single Source of Truth)

Create `glossary.json` with confirmed terms:

```json
{
  "Term": {
    "zh": "translation",
    "notes": "usage context"
  }
}
```

Then run terminology read/check:

```bash
uv run python scripts/term_edit.py --term "<TERM>" --cal
uv run python scripts/term_edit.py --term "<TERM>" --set-zh "<ZH>" --status approved --mark-term
uv run python scripts/term_read.py
```

Rules:
- `glossary.json` is the only source of truth.
- For unmanaged terms, `term_edit.py` must run with `--cal` before editing.
- Terms marked as managed skip full-site search in later `--cal` runs.

Ask user about style preferences and record in `style-decisions.json`.

### 9. Split Content

```bash
uv run python scripts/split_chapters.py
```

### 10. Generate Homepage index.md from style-decisions.json

Before chapter splitting, create/update `docs/src/content/docs/index.md` using project metadata and style decisions.

1. Read repository settings from `style-decisions.json`:
   - `repository.visibility`
   - `repository.url`
   - `repository.show_on_homepage`
2. Write homepage frontmatter and intro content in Traditional Chinese.
3. Repo link rendering rule:
   - If `visibility=public` and `show_on_homepage=true`, include a visible `GitHub Repo` link in `index.md`.
   - If `visibility=private`, do not render repo link.
4. Keep this logic data-driven: homepage content must follow `style-decisions.json` as source of truth.

### 11. Analyze and Split index.md

After initial split, analyze the generated `index.md` to create proper chapter structure:

1. **Identify TOC Structure**
   - Find table of contents or major headings in index.md
   - Extract chapter/section titles and their order
   - Note heading hierarchy (H1, H2, H3)

2. **Propose Chapter Split**
   Present to user:
   ```
   找到以下章節結構：
   1. [章節名稱] - 約 XXX 字
   2. [章節名稱] - 約 XXX 字
   ...
   建議拆分為獨立檔案嗎？
   ```

3. **Execute Split**
   For each identified chapter:
   - Create new file with slug derived from title
   - Add frontmatter with `sidebar.order` to preserve TOC sequence
   - Move corresponding content from index.md
   - Update index.md to contain only overview/introduction

4. **Frontmatter Template**
   ```yaml
   ---
   title: Chapter Title
   description: Chapter Description
   sidebar:
     order: N  # Keep original table of contents order
   ---
   ```

### 12. Configure Chapters

Finalize `chapters.json` after all splits are done:
1. Show table of contents from PDF and actual generated files
2. Confirm chapter structure based on final split result
3. Map page ranges and file paths to output files
4. Ensure order matches `sidebar.order` and actual navigation

### 13. Verify

- Check generated files in `docs/src/content/docs/`
- Verify sidebar order matches original TOC
- Preview: `cd docs && bun dev`

### 14. Record Configuration

Save all visual settings to `style-decisions.json`:

```json
{
  "theme": {
    "mode": "dark",
    "palette": "cool",
    "overlay_opacity": 0.7
  },
  "images": {
    "hero": "image_001.jpg",
    "background": "image_003.jpg",
    "og": "image_001.jpg"
  },
  "colors": {
    "primary_h": 217,
    "secondary_h": 180,
    "tertiary_h": 260,
    "quaternary_h": 200
  },
  "proper_nouns": {
    "mode": "official_only",
    "reason": "使用者偏好官方或通行譯名"
  },
  "repository": {
    "visibility": "public",
    "url": "https://github.com/<username>/<project_name>",
    "show_on_homepage": true
  }
}
```

### 15. Final Cleanup and Sidebar Refresh

After cropping and split operations are complete:

1. Remove unnecessary example files and placeholders from `docs/src/content/docs/`.
2. Ensure only real, current documents remain in the content tree.
3. Reorganize sidebar configuration/order so it reflects the latest split structure.
4. Verify sidebar links do not point to deleted or renamed files.
5. Run a final docs preview and confirm navigation is correct.

## Completion Checklist (Must Follow in Order)

- [ ] Step 1: 已定位 PDF（`data/pdfs/`）並確認來源檔案
- [ ] Step 2: 已完成內容抽取（`extract_pdf.py`）並檢查 `data/markdown/` 輸出
- [ ] Step 3: 已完成 PDF 裁切結果檢查與必要拆分，並確認重新抽取完整
- [ ] Step 4: 已完成圖片挑選與資產複製（hero/background/og）
- [ ] Step 5: 已完成視覺主題設定（背景模式、遮罩、色票）
- [ ] Step 6: 已完成術語盤點，並以繁體中文與使用者確認
- [ ] Step 7: 已與使用者確認專有名詞翻譯策略並寫入 `style-decisions.json`
- [ ] Step 8: 已更新 `glossary.json` 與風格決策
- [ ] Step 9: 已完成初始章節拆分（`split_chapters.py`）
- [ ] Step 10: 已依 `style-decisions.json` 產生首頁 `index.md`（含 repo link 顯示規則）
- [ ] Step 11: 已完成 `index.md` 分析與章節拆分落檔
- [ ] Step 12: 已完成 `chapters.json` 最終配置，且順序與 sidebar 一致
- [ ] Step 13: 已完成文件預覽驗證（目錄、連結、顯示）
- [ ] Step 14: 已更新 `style-decisions.json` 設定紀錄
- [ ] Step 15: 已移除不必要範例文件並重整 sidebar
- [ ] Gate: 已確認全程與使用者互動皆為繁體中文

## Example Usage

```
/init-doc
/init-doc data/pdfs/rulebook.pdf
```
