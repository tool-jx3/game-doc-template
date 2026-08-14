// 端對端驗收：對建置產物跑固定查詢集，比對設計文件的門檻。
// 用法：cd docs && npm run build && npm run verify-search
import http from 'node:http';
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DOCS = path.resolve(HERE, '..');
const BUNDLE = path.join(DOCS, 'dist/pagefind');
const GLOSSARY = path.resolve(DOCS, '../glossary.json');
const HAN_ONLY = /^[一-鿿㐀-䶿]+$/;

// min/max 皆為實測健康值的合理容許範圍（約六至七成下限，兩三成上限餘裕），
// 用意是同時防範「回傳過多雜訊」與「召回率下降」兩種故障模式——
// 只設上限的版本曾被審查抓到：召回率腰斬時只要首筆仍對，全部檢查照樣通過。
const CASES = [
	{ query: '無可逃避的衰敗', min: 1, max: 5, first: /\/(dustbringer|skybreaker)\// },
	{ query: '緊迫形體', min: 7, max: 15, first: /direform-regal/ },
	{ query: '橋九小隊', min: 4, max: 10, first: /\/bridge-nine\// },
];

// 一段刻意不含任何 glossary 詞條的句子（已核對過 1277 個術語，逐一比對確認無重疊）。
// CASES 的三個查詢全是 glossary 完整詞條，走字典最長匹配，完全不會進入 ICU 分支，
// 對「ICU 缺失、斷詞退化成逐字切分」這個主要故障模式沒有任何防護力。這裡逼迫
// 斷詞器只能靠 ICU 判斷詞界，藉此單獨驗證 ICU 分支本身是健康的。
// 只斷言「多字詞數量」這個粗粒度性質，不斷言確切切法——不同環境的 ICU 版本
// 切法可能略有差異，但「有沒有退化成逐字」是穩定可測的訊號。
const HEALTH_SENTENCE = '今天早上他去市場買了新鮮的蔬菜和水果，然後回家煮了一頓豐盛的晚餐';
const HEALTH_MIN_MULTI_CHAR = 5; // 實測健康值 11 個多字詞，退化成逐字切分時為 0；門檻取中間偏保守值。

// 「說服」「描述」等單一詞彙雖不在 glossary 中，但已是 vocab.json 的既有原子詞條，
// 查詢時字典最長匹配會直接命中，同樣繞過 ICU 分支（已實測驗證：query 時刪除
// Intl.Segmenter 後查詢「描述」筆數完全不變，因為 vocab.json 早就把它當成一個詞收著）。
// 改用「轉過身來」這種未被收錄為 vocab 原子詞條的敘事片語：ICU 健康時會切成
// 「轉過／身／來」，退化時逐字切成「轉／過／身／來」，四個單字在索引裡到處撞見，
// 回傳筆數暴增（實測：健康 2 筆 → 退化 52 筆），藉此驗證查詢端真的走了 ICU。
const ICU_QUERY = '轉過身來';
const ICU_MIN = 1;
const ICU_MAX = 10; // 健康值 2、退化值 52，上限取兩者之間但貼近健康值一側，確保能攔住暴增。

const server = http.createServer(async (req, res) => {
	const rel = decodeURIComponent(req.url.split('?')[0]).replace(/^\/pagefind\//, '');
	try {
		const data = await fs.readFile(path.join(BUNDLE, rel));
		res.writeHead(200, { 'Content-Type': 'application/octet-stream' });
		res.end(data);
	} catch {
		res.writeHead(404);
		res.end();
	}
});
await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
const basePath = `http://127.0.0.1:${server.address().port}/pagefind/`;

let shim, core, createSegmenter;
try {
	shim = await import(pathToFileURL(path.join(BUNDLE, 'pagefind.js')).href);
	core = await import(pathToFileURL(path.join(BUNDLE, 'pagefind-core.js')).href);
	({ createSegmenter } = await import(pathToFileURL(path.join(BUNDLE, 'segment.mjs')).href));
} catch (err) {
	console.error(`找不到建置產物（${BUNDLE}），請先執行「npm run build」。`);
	console.error(`原始錯誤：${err.message}`);
	server.close();
	process.exit(1);
}
// 只對 shim 設定 basePath——生產環境也只有 shim 會被 UI 呼叫，core 的 basePath 一律由 shim 轉交。
// 這裡若同時對 core 顯式設定，就會把「shim 沒把 basePath 交給 core」這個生產故障遮蔽掉
// （core 自行從 import.meta.url 推導的正則配的是 pagefind.js，對改名後的 pagefind-core.js 永遠失效）。
// core 與 shim 內部 import 的是同一個模組實例，因此下方直接用 core 查詢時同樣吃得到這份設定。
await shim.options({ basePath });
await shim.init();

const failures = [];

for (const testCase of CASES) {
	const result = await shim.search(testCase.query);
	const count = result.results.length;
	if (count > testCase.max) {
		failures.push(`「${testCase.query}」回傳 ${count} 筆，超過上限 ${testCase.max}`);
		continue;
	}
	if (count < testCase.min) {
		failures.push(`「${testCase.query}」回傳 ${count} 筆，低於下限 ${testCase.min}`);
		continue;
	}
	const top = (await result.results[0].data()).url;
	if (!testCase.first.test(top)) {
		failures.push(`「${testCase.query}」首筆為 ${top}，未符合 ${testCase.first}`);
	}
	console.log(`  ${testCase.query}：${count} 筆`);
}

// 斷詞器健康檢查：確認 ICU 分支沒有退化成逐字切分（見上方 HEALTH_SENTENCE 註解）。
const glossary = JSON.parse(await fs.readFile(GLOSSARY, 'utf8'));
const terms = Object.values(glossary)
	.filter((v) => v && typeof v === 'object' && typeof v.zh === 'string')
	.map((v) => v.zh.trim())
	.filter((zh) => zh.length > 1 && HAN_ONLY.test(zh));
const healthTokens = createSegmenter(terms).segment(HEALTH_SENTENCE);
const multiChar = healthTokens.filter((t) => t.length >= 2).length;
console.log(`  斷詞健康檢查：${multiChar} 個多字詞`);
if (multiChar < HEALTH_MIN_MULTI_CHAR) {
	failures.push(`斷詞健康檢查僅產生 ${multiChar} 個多字詞，低於下限 ${HEALTH_MIN_MULTI_CHAR}，疑似 ICU 退化成逐字切分`);
}

// ICU 語料查詢：驗證查詢端真的靠 ICU 分辨詞界（見上方 ICU_QUERY 註解）。
const icuResult = await shim.search(ICU_QUERY);
const icuCount = icuResult.results.length;
if (icuCount < ICU_MIN) {
	failures.push(`「${ICU_QUERY}」回傳 ${icuCount} 筆，低於下限 ${ICU_MIN}`);
} else if (icuCount > ICU_MAX) {
	failures.push(`「${ICU_QUERY}」回傳 ${icuCount} 筆，超過上限 ${ICU_MAX}，疑似 ICU 退化成逐字切分導致雜訊暴增`);
} else {
	console.log(`  ${ICU_QUERY}：${icuCount} 筆`);
}

// 子字串展開必須實際撈回額外結果
const direct = await core.search('軍團');
const expanded = await shim.search('軍團');
if (expanded.results.length <= direct.results.length) {
	failures.push(`「軍團」展開後 ${expanded.results.length} 筆，未多於直接查詢的 ${direct.results.length} 筆`);
} else {
	console.log(`  軍團：直接 ${direct.results.length} 筆 → 展開後 ${expanded.results.length} 筆`);
}

// 術語成詞率
const vocab = new Set(JSON.parse(await fs.readFile(path.join(BUNDLE, 'vocab.json'), 'utf8')));
const hit = terms.filter((t) => vocab.has(t)).length;
const rate = (hit / terms.length) * 100;
console.log(`  術語成詞率：${hit}/${terms.length}（${rate.toFixed(1)}%）`);
if (rate < 85) failures.push(`術語成詞率 ${rate.toFixed(1)}% 低於門檻 85%`);

server.close();
if (failures.length) {
	console.error('\n驗收失敗：');
	for (const line of failures) console.error(`  ✗ ${line}`);
	process.exit(1);
}
console.log('\n驗收通過');
process.exit(0);
