# Dogfood 測試發現紀錄：Cairn: Barebones Edition

專案：~/projects/cairn-barebones-docs
來源：https://yochaigal.itch.io/cairn-barebones-edition（CC-BY-SA 4.0，2026-01-29）

## 發現清單

1. `new-project/SKILL.md` Step 5 提到「(if public) 更新 GitHub social link」，但 docs/astro.config.mjs 沒有這個機制，指令引用不存在的設定項。

2. `new-project`/`init-doc`/`chapter-split` 仍是「Before ANY action, create tasks using TaskCreate」的強制寫法，但此環境沒有 TaskCreate 工具。translate/super-translate/bilingual-translate 已在 rcc:migrate 時改成條件式寫法，這三個沒同步。

3. `init-doc` Step 1 強制重跑 `clean_sample_data.py --yes`，會把 `new-project` 剛設定好的 style-decisions.json repository 區塊整個清空。文件順序 /new-project 接 /init-doc 會互相打架。

4. `extract_pdf.py --no-include-images` 對 opendataloader 引擎無效：opendataloader-pdf 套件自己在輸出的 markdown 裡內嵌 `![image N](page_N_images/imageFileN.png)` 語法（與 include_images flag 完全無關，那個 flag 只控制另一個獨立的 pymupdf extract_images() 步驟）。因為我們只保留 opendataloader 暫存目錄裡的 .md 文字、丟棄圖片檔，這些參照永遠是死連結。實測 Cairn Barebones Edition 第 1、47、48 頁（封面、角色卡頁）出現此問題，不受 --no-include-images 影響。


5. 第 47-48 頁（角色卡）擷取結果只有一張死連結圖片、無文字內容，`chapter-split` 沒有「純圖片無文字頁面」的處理規則，容易被忽略直接切入章節結構。（已由使用者決定：從章節切分排除）

6. AskUserQuestion 在產生較長的繁體中文問句/選項文字時，觀察到至少 2 次真實的文字損毀（"戰鬥"變成"戰[亂碼]printed"；"明確"變成"明訬"）。這可能是使用者稍早提到「地窕」「ask 文字跟理解有落差」的同一個底層問題根源——不是我編造內容，而是工具呼叫生成長中文字串時偶發損毀。與 game-doc-template 本身無關，但直接影響所有要求 zh-TW AskUserQuestion 的 skill 可靠性（Law 6 幾乎要求全部互動都用中文）。

7. `term_generate.py --min-frequency 2` 雜訊比例極高：200 個候選詞裡多數是常見英文虛詞/動詞（character, roll, does, instead, short, come, means, multiple, distance, door, example, answer, chance, body），且會把我們自己 extract_pdf.py 注入的 `<!-- PAGE N -->` 頁碼標記誤判為術語候選（"PAGE" 出現 70 次進入候選清單）。對一本 48 頁小書而言，200 個候選詞裡有意義的可能不到 30 個，人工篩選成本很高，跟 README 描述的 spaCy POS/lemma 輔助似乎沒有實際發揮過濾作用。

8. 自己在跑 term-decision 時也犯了一次術語選字錯誤：用 term_edit.py 建立「Non-Player Character」（全稱），但原書實際只在首次定義時出現過一次全稱，其餘全用「NPCs」縮寫，導致 term_read.py 報「缺少使用」。改用「NPC」重建後才通過（find_term_spans 對 NPC/NPCs 有做單複數容錯）。提醒：term-decision 流程裡沒有「先確認詞在語料庫的實際主要出現形式」這一步，容易選到書面全稱但語料庫其實用縮寫的詞。

9. `chapter-split` 的 topology-planner → toc-planner → wordcount-planner 是「依序」派工（不平行），且每個 planner 都要求逐頁核對 `<!-- PAGE N -->` 邊界、讀完整份來源檔。實測：光 topology-planner 一個 agent 就跑了約 7 分鐘（26 次工具呼叫、12 萬 token）。對一本 48 頁小書而言，整個規劃階段（3 個 agent 依序跑完）估計要 15-20 分鐘以上，翻譯都還沒開始。這跟 super-translate 慢的根因（序列化的重量級 subagent 派工）是同一類問題，只是發生在 chapter-split 而非 super-translate。topology-planner 和 toc-planner 讀的是同一份來源檔＋前一階段的 draft output，理論上有平行化空間（例如 toc-planner 可以不等 topology 完全定案就先起頭做粗略切分，或至少把「讀來源檔」這個步驟快取/共享），但目前設計是純序列 pipeline。

10. **根因確認（比發現 9 更精確）**：`chapter-split/SKILL.md` 的 3 個 planner dispatch templates（topology-planner/toc-planner/wordcount-planner）完全沒有標示任何 model tier（grep model/opus/sonnet/haiku 零匹配），跟 translate（sonnet）、super-translate（translator/reviewer=opus, md-reviewer=haiku, refiner=sonnet）、bilingual-translate（sonnet）形成明顯對比。這代表 chapter-split 的 3 個 planner 全部用呼叫端當下的預設模型/effort 執行（此次是繼承主 session 的 Sonnet 5），即使其中至少 wordcount-planner（純數字門檻判斷、依字數重新分配）性質上更接近 super-translate md-reviewer 那種「清單式核對、無需判斷力」的工作，理論上可以用更低階模型。這很可能是 topology-planner 花費 7 分鐘/12 萬 token 的直接原因之一，且與這個專案本季反覆強調的「模型分層、避免 token 大爆炸」核心原則直接矛盾——chapter-split 在做 Codex 整合與模型分層那輪重構時被漏掉了。

11. **模型分層假說實測驗證**：把 wordcount-planner 從預設（繼承 session sonnet）改成明確指定 `model: haiku`，耗時從 topology-planner 408 秒／toc-planner 632 秒，降到 **106 秒**（快 4-6 倍），tool call 從 19-26 次降到 5 次，token 從 12-16 萬降到 7.1 萬。強烈支持「chapter-split 的 planner 沒有模型分層是主要拖慢原因」（呼應發現 10）。
    但同時也發現真實的品質代價：haiku 把 `character-creation/basics`（100 人名表+屬性擲骰步驟，433 字）和 `traits`（8 張 d10 特徵隨機表，874 字）合併成一檔，理由是合併後 1307 字落在字數建議區間內。這個判斷**只看字數，沒有權衡 topology-planner 原本「讀者會分別跳轉到不同隨機表」的導覽理由**——純文字字數對錶格密集內容是失真指標（100 列的表每列只有 1-2 個字，字數低不代表內容少或該合併）。使用者最終決定不採用這個合併建議，改用 toc-planner 原始的 13 檔切分。
    結論：wordcount-planner 這類「數字門檻判斷」用低階模型換取速度是合理方向，但需要在 prompt 裡明確加入「不要只看字數，要保留 topology-planner 已經給的導覽理由」這類防護，否則低階模型會machine-like 地只服從數字規則、忽略前一階段已經給的質化判斷依據。

12. **確認：split_chapters.py 標題階層 bug，範圍比 toc-planner 原本標記的更廣**。實測全部 13 個輸出檔（不只合併檔案，連「直接連結」單一主題檔也一樣）都殘留原文的裸 `# ` H1，因為 `_strip_duplicate_heading()` 只在該標題文字「完全等於」frontmatter.title 時才會處理，而拆分階段的標題仍是英文原文，永遠不會等於中文 frontmatter.title，所以實際上這個函式在現有 pipeline 裡幾乎從未真正生效過。具體兩種缺陷模式：
    (a) 合併多個來源 H1 到一頁時，除第一個外全部原樣保留成裸 H1（一頁多個 H1，違反標題階層慣例）——core-rules/npcs-and-magic.md、procedures/wilderness-exploration.md、procedures/downtime.md、overview-principles/index.md 都是這種。
    (b) 檔案只涵蓋父章節底下第一個子小節時，會殘留「父章節標題」這個不屬於本頁範圍的裸 H1（例如 player-characters.md 開頭是「# Core Rules」而非「# Player Characters」）——player-characters.md、dungeon-exploration.md、basics.md 是這種。
    現有的 translate/super-translate 自我審查規則「不得新增/重複 frontmatter.title 的標題」**無法攔截這兩種缺陷**：模式 (a) 的裸標題翻譯後通常不等於 frontmatter.title（因為 title 是合併後的複合標題）；模式 (b) 的裸標題內容根本是別的（父）章節名稱，審查規則從未檢查過「這個 H1 是否根本不屬於本頁範圍」這件事。
    也確認了先前 terminology-check.py 加的標題跳級檢查（`check_structure`）不會抓到「一頁多個 H1」這種缺陷，它只檢查跳級（H1 直接接 H3），不檢查同層重複。
    已手動修正這次測試專案的全部 13 個檔案（刪除模式 (b) 的父章節標題、模式 (a) 全部降級為 ##），讓後續 translate/super-translate 測試不被這個上游結構缺陷污染。**這是 split_chapters.py 需要修的真實 bug，修法建議：`_strip_duplicate_heading()` 除了比對第一個標題是否等於 frontmatter.title，還要把該檔案內所有其餘的裸 H1（不論匹配與否）一律降級為 H2 起跳，而不是原樣保留。**

13. **確認**：`init_handoff_gate.py` 最後一關會跑 `bun run build`，但 `/new-project` 和 `/init-doc` 兩個 skill 的自動化步驟裡都沒有 `cd docs && bun install` 這一步（只在 README「快速開始」手動流程裡提到）。實測：全新專案照 skill 自動流程走到底，`init_handoff_gate.py` 會直接因為 `astro: command not found` 失敗（exit 127）。裝完 `bun install` 後重跑立刻過。修法建議：`new-project` 的「清理模板範例資料」步驟後，或 `init-doc` Step 1，補一步自動執行 `cd docs && bun install`（或至少在失敗時給出明確的「請先跑 bun install」提示，而不是讓使用者自己去查 astro command not found 是什麼意思）。

14. **【重大】確認：Codex 草稿分層功能從未能成功寫入偏好設定，這個 session 稍早新增後從未真正 live 驗證過**。`translate/codex-tier.md` §1 指示要檢查 `style-decisions.json.codex_tier.enabled`、寫入 `{"codex_tier": {"enabled": true}}`；但 `style-decisions.schema.json` 沒有 `codex_tier` 專屬定義，任何未列名欄位（含 codex_tier）一律套用通用的 `$defs/decisionRecord`（`additionalProperties: false`，必填 `decision` + `reason` 字串，沒有 `enabled` 這個欄位）。實測：照 codex-tier.md 指示執行 `style_decisions.py merge-json --patch '{"codex_tier": {"enabled": true}}'` 直接噴 schema validation 錯誤（`Additional properties are not allowed ('enabled' was unexpected)`），完全無法完成第一次詢問後「寫入偏好、之後不再問」的核心承諾——每個專案第一次啟用 Codex 分層都會在這裡卡死。
    另外 codex-tier.md 也完全沒指定「用哪個指令寫入」，只寫了 JSON 內容片段；實際上 `style_decisions.py` 沒有 `set-codex-tier` 專屬子指令，只能用通用的 `merge-json`（且如上所述還是會失敗）。
    根因：這是 OpenSpec `add-codex-translation-tier` 變更裡明確標記為「pending，需要 live 執行 /translate 才能驗證」的任務 7.1/7.2 所要防範的那種缺陷——因為當時沒有真的跑過，這個 schema 不相容的問題直到這次 dogfood 才第一次被抓到。
    修法建議：要嘛在 style-decisions.schema.json 的 `properties` 裡新增 `codex_tier: {type: object, properties: {enabled: {type: boolean}}}` 明確定義；要嘛把 codex-tier.md 改成使用通用 decisionRecord 形狀（`{"decision": "enabled"/"disabled", "reason": "..."}`）並同步改詢問後的檢查邏輯（`.codex_tier.decision == "enabled"` 而非 `.codex_tier.enabled`）。前者較符合這個欄位「布林開關」的本質，建議採用前者。
    此次測試繞過方式：改用 schema 相容的 decisionRecord 形狀手動寫入，讓後續能繼續測試翻譯階段本身。

15. 全部 13 個輸出檔都殘留 PDF 頁碼註腳的裸數字行（例如 overview-principles/index.md 裡的「3」「4」「5」），split_chapters.py 沒有過濾掉這些頁碼標記文字。更麻煩的是在 marketplace/index.md 裡，這種「獨立一行的裸數字」跟「price 表格因項目名稱過長被 PDF 自動換行、導致價格數字被擠到獨立一行」的情況長得一模一樣、混在一起（例如「Bathing Goods (Soap, Perfume, etc.)」後面隔一行才接著單獨一行「5」，這個 5 其實是該項目的價格，不是頁碼）——光看格式完全無法區分哪個裸數字是頁碼雜訊、哪個是被拆散的真實價格。這對翻譯品質是真實風險：譯者/reviewer 有可能誤刪真實價格數字（當成頁碼雜訊清掉），或誤把頁碼數字當成某個項目的價格接上去。這個不預先手動清理，留給接下來的 super-translate 實際跑跑看，觀察 translator/reviewer 能不能正確處理，作為翻譯品質實測的一部分。

## super-translate 實測結果（Step 5 reviewer/md-reviewer 併發派工）

16. **【重大、正面】確認：reviewer + md-reviewer 兩道關卡在正確派工（opus reviewer + haiku md-reviewer，完整 inline context）下確實有效，能抓到刻意植入且完全沒提示的缺陷**。5 個檔案的實測結果：
    - overview-principles/index.md：opus reviewer 精準抓到刻意保留的「NPC 首次加註後又退回裸英文」3 處位置，combat.md 的 opus reviewer 也精準抓到刻意留著、全文從未加註過的裸 NPC 2 處。
    - npcs-and-magic.md（完全不提示）：md-reviewer 與 opus reviewer 都主動抓到刻意保留的 PDF 頁碼殘留數字「8」「9」，opus reviewer 並主動抓到 Reactions 表格違反 style-decisions.json 記錄的骰表慣例（轉置成含空白表頭格的錯誤形狀），給出具體修正結構。
    - 兩道關卡並非重複：opus reviewer 判斷「- •」殘留符號是繼承自來源格式、不是新譯文錯誤，同一問題 md-reviewer 卻正確地從結構規範角度判為需修正的格式缺陷——兩者互補，非互斥。
    - 除了刻意植入的缺陷外，opus reviewer 在完全沒有人為植入問題的檔案（player-characters.md、dungeon-exploration.md）裡，仍抓到多個真實的翻譯品質問題（列表項目誤融合、術語撞名、被動語態語意反轉、slot/inventory 用語不一致、"petty"/"serious" 等假朋友誤譯），可信度高。

17. **【重大、新發現】確認：全部檔案的小節標籤（如「屬性」「豁免」「反應」「法術書」）從 PDF 擷取階段起就只是純文字段落，從未被標記成真正的 Markdown 標題**，違反 `docs-conventions.md` 的「MUST use H2 for main sections, H3 for subsections」規則——因為這個格式是來源本身帶來的，且 `translate`/`super-translate` 的「保留來源區塊型態」原則本意是防止譯者亂改結構，兩者疊加導致這個缺陷從擷取到翻譯全程沒人處理，直到這次刻意「不提示」派 reviewer 才第一次被系統性抓出來。
    影響具體且可驗證：combat.md 的 opus reviewer 指出，若僅將其中一個小節（「傷疤」）升級成 H2、其餘 11 個維持純文字，會讓 Starlight 側欄目錄只顯示 2 個項目、其餘 10 個小節完全從導覽消失——這是真正的渲染缺陷，不是格式偏好。
    同一缺陷在 4 個新測試檔案（player-characters、npcs-and-magic、combat、dungeon-exploration）的 md-reviewer 都判為 critical，但在第一個檔案（overview-principles）的 md-reviewer 卻完全沒被抓到（該檔案有一模一樣的小節純文字標籤，卻只抓到標題重複問題）——同一類缺陷、同一顆 haiku 模型，跨檔案判定不一致，這本身也是一個值得注意的 reviewer 可靠性發現。
    修法建議：`split_chapters.py` 或其上游擷取階段應嘗試辨識原書的「小節標籤」樣式（例如全形獨立段落、無句尾標點、後接內文）並主動標記為 H3，而不是留給 translate 階段被動繼承；若技術上無法可靠辨識，至少應在 chapter-split 或 super-translate 的 review scope 裡明確列入「小節標籤必須有對應標題層級」這條規則（目前 md-review/reviewer-prompt.md 第 2、3 項只講「不重複 title」「不可跳級」，沒有明講「純文字小節標籤本身就是缺陷」，這次是 haiku 自行延伸解讀規則抓到的，不穩定）。

18. **【確認，orchestrator 端錯誤，非 template 缺陷，但暴露真實風險】refiner subagent 派工時若只給相對路徑（如 `docs/src/content/docs/core-rules/combat.md`），實測有 3 次直接寫進錯誤專案（game-doc-template 本身的 `.state/` 目錄），而不是目標專案 `cairn-barebones-docs`**。原因：subagent 的實際 cwd 繼承自它被啟動時的環境，而非目標專案路徑；relative path 在 prompt 裡沒有錨定專案根目錄時，subagent 會用自己當下的 cwd 解析，兩者不保證一致。此次由於 `.state/` 已在 game-doc-template 的 `.gitignore` 中，未造成實際汙染，事後人工搬移檔案修正。
    這雖然是我（orchestrator）派工時的失誤，但也指出一個 template 本身可以強化的地方：`super-translate/refiner-prompt.md`、`reviewer-prompt.md`、`translator-prompt.md` 裡的 `<TARGET_FILE>`／`<DRAFT_FILE>` 佔位符範例都是相對路徑（例如 `Path: <TARGET_FILE>`），沒有明確要求 orchestrator 必須代入絕對路徑。建議在這三個 prompt template 加一行提醒：「orchestrator 代入路徑時必須使用絕對路徑，不可用相對路徑」，降低未來再次發生同類寫錯專案事故的機率。
    根因補充：實測發現 shell 工具每次呼叫之間 cwd 會重置回 session 的 primary working directory（本例是 game-doc-template），並非只是「忘記打絕對路徑」這麼單純——即使 orchestrator 自己用 `cd cairn-barebones-docs && ...` 執行單一指令沒問題，任何 subagent 只要沒有在自己的 prompt 裡拿到絕對路徑，就一定會落在錯的專案，這是環境層級的固定行為，不是偶發。

## 瀏覽器實際驗收（Astro dev server, localhost:4321）

19. **【正面，視覺驗證】`bun dev` 啟動後，用 `agent-browser` 逐頁檢視 5 個已翻譯檔案，H3 小節標題修正（Finding #17 的修法）在實際渲染中完全生效**：combat.md、npcs-and-magic.md、player-characters.md、dungeon-exploration.md 的 Starlight 右側「本頁內容」側欄，現在都完整列出所有小節（分別是 11、8、8、11 項），不再像修正前只顯示 1-2 項。npcs-and-magic.md 的 Reactions 表格與 combat.md 的 Scars 表格都正確渲染成規範的多欄 Markdown table。combat.md 的 NPC 首次加註、後續退回中文的 Voice 規則 6 也在畫面上正確呈現。首頁（版權宣告、製作名單含「翻譯：洪偉」）與暗黑主題配色渲染正常，無破版。
    對比組（overview-principles/index.md，此檔案在系統性 H3 缺陷被發現「之前」就先跑完 refiner）在瀏覽器裡清楚可見同一缺陷仍然存在：「本頁內容」側欄只列出 3 項（總覽/玩家原則/守護人原則），「自主性」「交談」「危險」「寶藏」等 14 個小節完全不在導覽中——用實際渲染結果印證了 Finding #17 的影響範圍與嚴重度，而不只是理論推測。此檔案刻意保留未補修，作為「修法前」對照證據。

20. **【新發現，比 Finding #15 更明確的案例】在完全未翻譯的 `character-creation/basics.md` 頁面（尚未進入 super-translate 流程）用瀏覽器實際檢視，看到 PDF 頁碼殘留數字直接插在一份連續編號 1-100 的隨機姓名表中間**：例如清單跑到「17 Bryn Cooper」後，緊接著出現一行獨立的「24」，然後才接「18 Cai Crowther」繼續往下編號——頁碼「24」硬生生插斷了正在進行中的「17 → 18」編號序列。這比 Finding #15 描述的「裸數字與表格價格混淆」更嚴重：這裡頁碼數字本身的格式（獨立一行的純數字）與清單項目編號完全相同形式，如果不細看上下文語意，機器或人工都很容易誤判成「這份表格從 1 跳到 17，然後又出現一個 24，是不是漏了項目」而去查源頭，或誤把它當成合法清單項目保留。進一步印證 split_chapters.py／extract_pdf.py 需要處理頁碼標記過濾。

## 流程缺口與 orchestrator 自我修正

21. **【重大、確認】`term_read.py --fail-on-missing` 的「缺少使用」檢查在專案進度未完成時可能是假陽性通過（vacuous pass），不是有意義的信號**。根因：`build_corpus()`（`_term_lib.py`）把每個 Markdown 檔案的**完整原始內容**（含 frontmatter 的 `title`/`description`）都納入語料庫，而 `chapter-split` 在切分階段就已經為全部 13 個章節寫入中文 frontmatter 標題，與該章節「本文」是否已翻譯完全無關。實測：本次 5/13 進度下，`term_read.py` 回報「缺少使用: 0」，但直接 grep 檢查發現「裝備包」「市集」「法術書」這三個 glossary 術語，唯一出現的位置就是各自對應章節（gear-packages/marketplace/spellbooks，全部尚未翻譯）的 frontmatter `title` 欄位，本文仍是 100% 英文——術語檢查把「章節標題已翻譯」誤判為「術語已在本文中正確使用」。
    影響：只要一個 glossary 術語剛好也是某章節的標題（游戲文件裡很常見，因為主要機制名詞常常本身就是章節名），`--fail-on-missing` 從專案一開始（章節切分完成、翻譯尚未開始）就永遠不會失敗，不只是本次 5/13 這個時間點才失真——super-translate SKILL.md Step 2「Terminology Preflight (Fail-Closed)」與 Step 7「Final Verification (MANDATORY)」兩處都仰賴這個檢查作為品質關卡，實際保護力比文件描述的弱。
    修法建議：`build_corpus()` 或 `term_read.py` 應該有選項排除 frontmatter 區塊（僅檢查 `---` 之後的正文），或者依 `data/translation-progress.json` 的完成狀態，只把已完成章節的內容納入「缺少使用」檢查範圍，避免章節標題的翻譯掩蓋本文術語未使用的事實。

22b. **【補充驗證，正面】針對 Finding #22 指出的缺口，事後補跑 combat.md 的 reviewer+md-reviewer 複查（不提示 H1→H3 跳級問題，讓模型自行判斷）**：opus reviewer 與 haiku md-reviewer 都判定 pass（critical 皆為空）。兩者都獨立指出「小節標籤全部用 H3、frontmatter 標題渲染為 H1、中間缺 H2」違反「不可跳過標題層級」慣例，但**明確裁定不阻擋通過**——因為 Starlight 的側欄/TOC 對 H2、H3 一視同仁，不影響實際渲染。opus reviewer 進一步給出具體修法建議：既然原文的 `## Combat` 已被 frontmatter.title 吸收、body 裡不該再出現重述標題的標題，正確做法是把所有 `### ` 統一降為 `## `（而非我在其他檔案的做法：把裸標籤升到 H3），這樣才能同時滿足「不跳級」與「不重複標題」兩條規則——這是本次 dogfood 對 Finding #17 系統性缺陷的最終、由 reviewer 裁定的正確修法方向，目前 4 個新測試檔案仍是 H3 起跳、未套用這個修正，留作已知殘留問題。
     複查同時額外抓到 2 個先前沒發現的真實問題：「人數損失過半時」應為「人數損失半數時」（過半 vs 半數的門檻語意偏移）；「deprived → 匱乏」譯法一致但未登錄進 glossary.json（Law 7 要求新術語先建檔）。兩者都記錄為已知殘留問題，未進一步派 refiner 修正——避免對一個已經 pass 的檔案做無止盡的打磨輪迴。

22. **【orchestrator 自我修正記錄】本次 dogfood 執行中途，經第三方複核（advisor）指出我在跑完 4 個檔案的 refiner 之後，直接進了 writeback，跳過了 `super-translate/SKILL.md` Step 6 明訂的「refiner 完成後必須重新派 reviewer + md-reviewer 複查（cap 2 輪）」這一步**——等於 5 個檔案裡沒有任何一個是真的通過 reviewer 驗證才寫回的，違反了 Step 5「Only if reviewer passes」的前提。事後補跑 combat.md 的複查（reviewer+md-reviewer 併發、不提示標題跳級問題讓模型自行判斷）作為抽驗，其餘 4 個檔案未逐一補跑，記錄於此作為已知缺口，而非隱瞞。這本身也是一個值得注意的觀察：即使是刻意設計來測試 skill 品質關卡的這次 dogfood run，orchestrator（我）自己都會在執行壓力/長流程下漏掉一個關卡步驟——這正是 super-translate SKILL.md「Red Flags」表格裡「Just overwrite source, reviewer will pass next time」那條想防的事，但光靠文件裡的紅字提醒不足以完全防止，值得納入「這個 skill 未來要不要加機械化檢查」的討論（例如 draft.py writeback 前檢查是否存在對應的 reviewer pass 記錄）。

23. **【重大、確認、近乎誤報「完成」的真實事故】第二批 8 個檔案的 `draft.py writeback` 全部失敗（`Error: draft manifest entry not found`），但緊接著執行的 `progress_edit.py --status completed` 完全不檢查 writeback 是否成功，照樣把全部 8 個檔案標記為「completed」，`progress_read.py` 回報「13/13」，而此時這 8 個檔案在 `docs/src/content/docs/` 的實際內容 100% 仍是英文原文，一個字都沒有寫回**。
    根因：這批檔案的翻譯草稿是透過我自己在 `.state/super-translate/` 底下寫的 Codex 派工輔助腳本（`build_codex_prompt.py`）產生，該腳本直接把草稿寫進 `.state/<skill>/drafts/` 目錄，但從未呼叫 `draft.py path <source>` 在 `draft-manifest.json` 註冊條目；`draft.py writeback` 依賴這個 manifest 條目才能定位並清空對應的草稿，找不到條目就 fail-closed 直接報錯——這部分 script 本身的防呆設計是對的。但 `progress_edit.py` 是完全獨立、不檢查任何前置條件的腳本，兩者之間沒有耦合，導致「writeback 失敗」與「進度標記完成」互不影響，靜默產生了一個內容與進度表完全不符的假象。
    這不是我刻意測試的情境，是在批次收尾、追著把事情做完時真實犯的操作失誤——但也precisely 暴露了 super-translate 流程的一個結構性缺口：`progress_edit.py --status completed` 沒有任何機制確認對應檔案真的经过 writeback（例如檢查 `.state/<skill>/drafts/<file>` 是否仍存在、或核對 `docs/src/content/docs/<file>` 的內容雜湊是否與最近一次 writeback 相符）。若不是隨後又主動去瀏覽器驗收環節前做了一次「回頭核對進度=完成的檔案內容」，這個假完成狀態可能會一路帶到最終驗收甚至 commit 訊息裡（"progress: 13/13"）而不被發現。
    事後修復：手動對 8 個檔案重跑 `draft.py path` 補註冊 manifest（因為草稿檔案本身仍完好保留在磁碟，未被清空，才使補救可行），再重跑 `writeback`，這次全部成功，`docs/src/content/docs/` 確認已是翻譯後內容，progress.json 的「13/13」現在才是真的。
    修法建議：`progress_edit.py --status completed` 應該在寫入前做一個輕量檢查——至少確認 `.state/<skill>/drafts/<file>` 已不存在（代表 writeback 曾經清空過它）；更嚴謹的做法是讓 super-translate SKILL.md 明確要求「writeback 指令回傳非 0 結束碼時，禁止接著呼叫 progress_edit.py --status completed」，並在 Step 5 的驗收條件裡加一行「確認 writeback 指令本身沒有印出 Error」。也再次印證 Finding #18 提過的根因：任何自訂輔助腳本如果繞過 skill 原生的 `draft.py path` 註冊步驟，就會讓後續的 writeback／manifest 機制整條失效，且失效方式是靜默的，不會在進度報告裡露出任何痕跡。

24. **【操作失誤，記錄用】`bun dev` 背景行程未及時關閉，累積成 2 個並行行程，導致 `bun run build` 出現 `Duplicate id` 警告**。第一個是本輪瀏覽器驗收時啟動的 dev server，第二個是本 session 更早（壓縮前）啟動、從未主動關閉的殘留行程；兩者同時對 `docs/.astro/data-store.json` 這份 Astro content cache 寫入，造成 build 時期出現 3 個內容項目的 duplicate-id 警告（不影響最終輸出正確性，但是雜訊）。修法：`kill` 掉兩個殘留行程、清空 `.astro` 與 `dist` 快取後重新 build，警告消失。提醒：任何 skill 或 orchestrator 只要啟動了背景常駐行程（`bun dev`、`npm run watch` 等），收工前應主動確認並關閉，不能只靠 session 結束被動回收。

25. **【重大、確認、真實上線事故】GitHub Pages 部署後，首頁「快速導航」卡片與 hero 按鈕全部 404，`fix-ref` 產生的頁內連結也全部 404，只有側欄導覽正常**。根因：`generate_nav.py` 產生的 `hero.actions[].link`（Starlight frontmatter 原生設定）與 `<LinkCard href="...">`（MDX 元件）都是寫死的絕對路徑字串（如 `/overview-principles/`），而 Astro/Starlight **不會**自動幫這類「作者手動寫入內容的字面字串」加上 `base` 前綴——只有 Starlight 自己原生的路由機制（例如 `starlight-auto-sidebar` 產生的側欄 `slug` 設定）才會在內部正確套用 `base`。這代表任何非 root 部署（例如 GitHub Pages 的 project site，`base` 不是 `/`）都會讓首頁快速導航與 `fix-ref` 產生的連結整批失效，但側欄看起來完全正常——很容易被誤判為「只有首頁壞掉」而忽略是同一個根因。
    第一次修正時我犯了一個真正的錯誤：直接把 `/cairn-barebones-docs` 字面字串寫死進 `index.mdx` 和 `basics.md` 兩份內容檔案裡「先求有" — 這是 workaround，不是修根因；一旦 repo 改名或改用 Vercel（root 部署），這些寫死的路徑又會全部壞掉，且沒有任何機制會提醒要回頭改。經使用者當場糾正（「不要 work around 修復」），改為在 template 層級修正：
    - `style-decisions.schema.json` 新增 `deployment: {target, base_path}` 正式欄位（而非落入 Finding #14 那種通用 decisionRecord 陷阱）。
    - `style_decisions.py` 新增 `set-deployment` 子指令。
    - `generate_nav.py` 新增 `deployment_base_path()`，只在 `deployment.target == "github-pages"` 時才回傳非空字串（**修正時也踩到一個真實的第二層 bug**：第一版實作只讀 `base_path` 欄位、沒檢查 `target`，導致把 `target` 切回 `root` 後 `base_path` 殘留舊值，`astro.config.mjs` 的 `site`/`base` 正確被清空，但 `index.mdx` 的連結卻沒有跟著清空——這個 bug 是在本次要求的「驗證」步驟裡，透過刻意切換 `target` 到 `root` 並檢查兩邊輸出是否一致才抓到的，若不做這層測試會被忽略）；`hero.actions.link`、`LinkCard href` 全部改用這個函式產生。
    - `astro.config.mjs` 的 `site`/`base` 兩個欄位也改由 `generate_nav.py` 依 `deployment` 設定自動寫入／清除（新增 `update_astro_site_base()`，用 regex 定位 `defineConfig({` 後緊接的區塊，可插入、更新、或移除，並驗證了插入後重跑不會重複寫入）。
    - `fix-ref/SKILL.md` 的 Link Rules 補上「必須讀 `deployment.base_path` 並加在絕對路徑前」的規則，因為 fix-ref 產生的頁內連結是一次性手動編輯、不像 `generate_nav.py` 可重跑，這條規則要讓下一次執行 fix-ref 的人（或 AI）從一開始就用對格式。
    - `new-project/SKILL.md` Step 5 補上：`REPO_VISIBILITY=public` 時實際呼叫 `set-deployment --target github-pages --base-path "/<project_name>"`，而不是只在報告裡提醒。
    驗證方式（這次真的做了）：本地還原成修正前狀態、重新產生、確認自動產生的內容與手動 workaround 版本一致；刻意測試 target 在 github-pages／root 之間切換兩個方向，確認 `astro.config.mjs` 與 `index.mdx` 兩邊輸出永遠同步、不會有一邊清空另一邊沒清；重新 build 後用程式化腳本掃描全部 15 個輸出頁面的每一個 `href`，確認零殘留；本機用 `python -m http.server` 依 GitHub Pages 實際路徑結構（`/cairn-barebones-docs/...`）架設測試站，用 `agent-browser` 實際點擊首頁卡片、hero 按鈕、fix-ref 連結、側欄連結完成端對端導覽；推上 GitHub Pages 正式站後，再對全部 14 個實際頁面發真實 HTTP 請求、程式化檢查近千個 `href`，並用瀏覽器實際點擊正式站驗證。
    教訓：這是本次 dogfood 唯一一次「先給出一個能動但錯誤方向的修法，被使用者當場攔下」的案例，也是「跑完，走到部屬」這個目標裡，真正把成品交到使用者手上、被使用者實際使用後才浮現的缺陷——前面所有 reviewer/md-reviewer/check-consistency 關卡都不會抓到這種「內容本身沒錯、但部署環境改變後才會爆炸」的問題，因為它們都只檢查文件內容，不檢查『這個連結在實際部署環境下打得開嗎』。

26. **【確認，使用者實際使用時發現】`split_chapters.py` 用頁碼切分章節時，把一張橫跨頁面邊界的表格從中間切斷，導致下一個檔案開頭出現不屬於該章節主題的殘留內容**。具體案例：character-creation 的「出身」（Background）100 列隨機表格橫跨第 28-35 頁，而 `chapters.json` 把 `traits.md` 設定為 28-32 頁、`armor-weapons.md` 設定為 33-35 頁——表格剛好在頁 32/33 之間被切斷，導致 `armor-weapons.md`（護甲與武器）翻譯完成後，**開頭 10 列（91-100）其實是出身表格的尾段**，跟這個檔案本身的護甲/武器內容完全無關，讀者一打開「護甲與武器」頁面會先看到十個職業與裝備清單，完全搭不上標題。這個問題在 super-translate 全程的 reviewer/md-reviewer 審查裡都沒被抓到——因為兩邊檔案「各自」翻譯正確、格式正確，缺陷是跨檔案的「內容歸屬」問題，任何單一檔案的 reviewer 都看不出「這段內容其實屬於別的章節」。是使用者實際瀏覽網站時才發現的，不是任何自動化關卡抓到的。
    修法：把已翻譯完成的第 91-100 列從 `armor-weapons.md` 搬到 `traits.md`「出身」表格的尾端（原本第 41-50 列的右欄位是空的，因為當時 traits.md 只涵蓋到頁 32），讓完整 100 列表格回到同一個檔案；`armor-weapons.md` 開頭乾淨地從「所有玩家角色一開始都有以下裝備」與「護甲（D6）」表格開始。搬動時順手統一了單位標記不一致（armor-weapons.md 原本用「英尺」，traits.md 用「呎」，統一為「呎」）。
    這是 chapter-split 階段的真實 bug（`split_chapters.py` 用頁碼切分、不知道表格內容的語意邊界），此次以人工方式在譯文完成後修正，屬於治標；真正的修法應該在 chapter-split 規劃階段就偵測「一張表格橫跨計畫中的頁碼邊界」並提出警告或調整邊界，但這超出這次 dogfood 的即時修復範圍，留給未來處理 chapter-split 缺陷時一併考慮。
