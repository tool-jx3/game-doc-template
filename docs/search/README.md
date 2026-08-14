# 中文搜尋強化層

## 問題與根因

Starlight 以 Pagefind 建立站內搜尋。Pagefind 的中文斷詞使用 jieba，但其詞庫為**簡體中文**：正體字形與簡體不同的詞一律匹配失敗，退化為逐字切分，領域術語幾乎不成詞。表面症狀是「搜不到」，實際是單字比對造成**回傳過多**——查詢術語會命中站上大多數頁面，正確結果被雜訊淹沒。（於來源專案 144 頁語料實測：glossary 術語僅 9% 以完整詞形式存在於索引。）

已排除的方向：`--force-language zh` 無效果；Pagefind 無自訂詞庫選項；Starlight 的 `pagefind` 設定觸及不到斷詞層；以 ZWSP 或 `<span>` 注入詞邊界會被 jieba 剝除後重切。

## 方案

關閉 Pagefind 的 CJK 斷詞（`forceLanguage: 'en'`，改以空白切詞），由本專案自行斷詞後注入索引。斷詞採兩層：

1. **glossary 最長匹配** —— 已核准（`status: "approved"`）術語優先成詞，解決領域詞彙
2. **`Intl.Segmenter('zh-Hant')` 回退** —— 處理其餘一般詞彙；Node 與瀏覽器皆內建，建置端與查詢端共用同一實作，零傳輸成本

成效（來源專案實測）：術語成詞率 9% → 90%，高雜訊查詢從 135 筆降至 2 筆，索引縮小 0.5 MB。

## 架構

```
astro build
  └─ Starlight 產出 dist/**/*.html 與內建 Pagefind 索引（會被整個取代）

node search/build/index.mjs（build script 的第二步）
  1. 讀 glossary.json 取已核准術語（load-terms.mjs）
  2. 改寫 dist/**/*.html：把可見內容轉成已斷詞的隱藏鏡像（rewrite-html.mjs），
     data-pagefind-body 移到鏡像上，鏡像掛在 <body> 尾端
  3. 刪除 dist/pagefind/ 後以 forceLanguage:'en' 重建索引
  4. 產出 dist/pagefind/vocab.json（索引實際詞元的詞彙表）
  5. pagefind.js 改名 pagefind-core.js，寫入 shim 取代 pagefind.js
```

| 檔案 | 執行環境 | 角色 |
| --- | --- | --- |
| `build/index.mjs` | Node（建置期） | 後處理進入點：改寫、重建索引、換上 shim |
| `build/rewrite-html.mjs` | Node（建置期） | 單頁 HTML → 已斷詞隱藏鏡像 |
| `build/load-terms.mjs` | Node（建置期） | glossary 術語載入與過濾 |
| `client/segment.mjs` | 兩端共用 | 斷詞器：術語最長匹配 + ICU 回退（零相依，禁用 Node API） |
| `client/shim.mjs` | 瀏覽器 | 取代 `pagefind.js`：查詢斷詞、子字串展開、摘要清理、basePath 轉交 |
| `client/expand.mjs` | 瀏覽器 | 展開候選與結果合併的純邏輯 |
| `client/excerpt.mjs` | 瀏覽器 | 摘要中注入空格的清理 |
| `verify.mjs` | Node（建置後） | 端對端驗收（`bun run verify-search`） |
| `verify-lib.mjs` | Node | 驗收設定解析與健康檢查輔助 |

查詢端行為（shim 包裝 `search()`）：以 `vocab.json` 做查詢斷詞（保證切出的詞存在於索引）；對詞彙表做子字串展開（上限 12 詞，撈回「燦軍軍團」之於「軍團」這類長詞命中，展開命中分數乘 0.5 相對降權）；顯示前清理摘要中的注入空格（`<mark>` 與英數旁空格保留）。

## glossary 整合

- 只有 `status: "approved"` 且**純漢字、長度 ≥ 2** 的 `zh` 譯名會進入斷詞字典。
- glossary 缺失或 JSON 損壞：建置失敗（搜尋品質直接取決於術語表，靜默降級會產出看似正常但品質低落的索引）。
- glossary 合法但尚無已核准術語（新專案初始狀態）：警告後以純 `Intl.Segmenter` 模式繼續，仍優於簡體 jieba。核准術語後重新建置即可納入。

## 建置與部署

`docs/package.json` 的 `build` 已含後處理（`astro build && node search/build/index.mjs`），Vercel 的 `buildCommand` 走同一入口，`vercel.json` 無須修改。`astro dev` 不受影響（開發模式本就停用搜尋）。相依 `node-html-parser` 與 `pagefind` 為建置期使用，不進瀏覽器產物。

## 驗收（verify-search）

```bash
cd docs && bun run build && bun run verify-search
```

通用檢查永遠執行：

- **斷詞健康檢查**：以不含字典詞條的日常句逼迫 ICU 分支切詞，多字詞數低於門檻即失敗（防「ICU 缺失退化成逐字」）。與 glossary 重疊的詞條會於執行期自動剔除。
- **術語成詞率**：已核准術語出現在 `vocab.json` 的比率須 ≥ 85%（零術語時略過）。

語料相關查詢集由各專案在 `docs/search/verify-cases.json` 維護（格式見 `verify-cases.example.json`），翻譯完成後建立。挑選原則：

- `cases[]`：選 glossary 完整術語，`min`/`max` 取實測健康值的容許區間（約六至七成下限、兩三成上限餘裕）——只設上限攔不住召回率下降，只設下限攔不住雜訊暴增。`first` 為首筆 URL 的正則（可省略）。
- `expansion`：選「是更長術語之子字串」的短詞（術語表有「燦軍軍團」時選「軍團」），驗證展開確實撈回額外結果。
- `icu`：選**未被 `vocab.json` 收為原子詞條**的敘事片語（如「轉過身來」）。ICU 健康時命中數低；退化成逐字時筆數暴增。glossary 詞條與 vocab 既有詞都走字典匹配、驗不到 ICU 分支，不可選用。

## 測試

```bash
cd docs && bun run test   # node --test search/**/*.test.mjs
```

## 已知限制

- 各瀏覽器 `Intl.Segmenter` 的 ICU 版本不同，一般詞彙的查詢端切法可能與建置端略有出入；術語層由 glossary 保證一致。
- `vocab.json` 於首次開啟搜尋時載入（gzip 後數十 KB），載入失敗時 shim 退回未強化的原始搜尋。
- 摘要來源為隱藏鏡像，不含表格與清單結構，排版線索較原文弱。
- 子字串展開上限 12 詞，極高頻子字串並非完整召回。

## 範圍外

中英互查（搜英文原文命中中文譯名頁）、搜尋 UI 視覺調整、外部通用詞庫。若日後 `Intl.Segmenter` 品質不足，候選詞庫為 jieba `dict.txt.big`（MIT）、CC-CEDICT；教育部辭典為 BY-ND 授權（禁止改作），不可用於衍生詞表。
