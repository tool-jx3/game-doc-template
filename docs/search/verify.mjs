// 端對端驗收：對建置產物跑查詢集，比對門檻。
// 通用檢查（斷詞健康、術語成詞率）永遠執行；語料相關查詢集由各專案在
// docs/search/verify-cases.json 維護（格式見 verify-cases.example.json 與 README.md），
// 設定不存在時僅執行通用檢查並提示。
// 用法：cd docs && npm run build && npm run verify-search
import http from 'node:http';
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { loadTerms } from './build/load-terms.mjs';
import { parseCases, healthTerms } from './verify-lib.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DOCS = path.resolve(HERE, '..');
const BUNDLE = path.join(DOCS, 'dist/pagefind');
const GLOSSARY = path.resolve(DOCS, '../glossary.json');
const CASES_FILE = path.join(HERE, 'verify-cases.json');

// 一段刻意與 glossary 詞條無關的日常敘事句。語料查詢集全是 glossary 完整詞條，
// 走字典最長匹配、完全不會進入 ICU 分支，對「ICU 缺失、斷詞退化成逐字切分」
// 這個主要故障模式沒有防護力；這裡逼迫斷詞器只能靠 ICU 判斷詞界。
// 只斷言「多字詞數量」這個粗粒度性質，不斷言確切切法——不同環境的 ICU 版本
// 切法可能略有差異，但「有沒有退化成逐字」是穩定可測的訊號。
// 句中若恰有詞條與各專案的 glossary 重疊，會於執行期剔除（healthTerms），
// 不需人工核對術語表。
const HEALTH_SENTENCE = '今天早上他去市場買了新鮮的蔬菜和水果，然後回家煮了一頓豐盛的晚餐';
const HEALTH_MIN_MULTI_CHAR = 5; // 實測健康值 11 個多字詞，退化成逐字切分時為 0；門檻取中間偏保守值。
const TERM_RATE_MIN = 85; // 術語成詞率門檻（%）

// min/max 皆為實測健康值的合理容許範圍（約六至七成下限，兩三成上限餘裕），
// 用意是同時防範「回傳過多雜訊」與「召回率下降」兩種故障模式——
// 只設上限的版本曾被審查抓到：召回率腰斬時只要首筆仍對，全部檢查照樣通過。
let config = { cases: [], expansion: null, icu: null };
let rawCases = null;
try {
	rawCases = await fs.readFile(CASES_FILE, 'utf8');
} catch {
	console.warn(`[verify] 找不到 ${CASES_FILE}，僅執行通用檢查；翻譯完成後請依 README.md 建立語料查詢集`);
}
// 設定檔存在但內容不合法時直接拋錯——手寫設定靜默略過會讓驗收假通過。
if (rawCases !== null) config = parseCases(JSON.parse(rawCases));

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

for (const testCase of config.cases) {
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
	if (testCase.first && count > 0) {
		const top = (await result.results[0].data()).url;
		if (!testCase.first.test(top)) {
			failures.push(`「${testCase.query}」首筆為 ${top}，未符合 ${testCase.first}`);
			continue;
		}
	}
	console.log(`  ${testCase.query}：${count} 筆`);
}

// 斷詞器健康檢查：確認 ICU 分支沒有退化成逐字切分（見上方 HEALTH_SENTENCE 註解）。
const terms = await loadTerms(GLOSSARY);
const healthTokens = createSegmenter(healthTerms(terms, HEALTH_SENTENCE)).segment(HEALTH_SENTENCE);
const multiChar = healthTokens.filter((t) => t.length >= 2).length;
console.log(`  斷詞健康檢查：${multiChar} 個多字詞`);
if (multiChar < HEALTH_MIN_MULTI_CHAR) {
	failures.push(
		`斷詞健康檢查僅產生 ${multiChar} 個多字詞，低於下限 ${HEALTH_MIN_MULTI_CHAR}，疑似 ICU 退化成逐字切分`
	);
}

// ICU 語料查詢：驗證查詢端真的靠 ICU 分辨詞界。查詢須是「未被 vocab.json 收為
// 原子詞條」的敘事片語——glossary 詞條或 vocab 既有詞都會走字典最長匹配、繞過
// ICU 分支；ICU 健康時這類片語切成少數多字詞、命中數低，退化成逐字時
// 單字在索引裡到處撞見、筆數暴增，藉此攔住查詢端的 ICU 故障。
if (config.icu) {
	const icuResult = await shim.search(config.icu.query);
	const icuCount = icuResult.results.length;
	if (icuCount < config.icu.min) {
		failures.push(`「${config.icu.query}」回傳 ${icuCount} 筆，低於下限 ${config.icu.min}`);
	} else if (icuCount > config.icu.max) {
		failures.push(
			`「${config.icu.query}」回傳 ${icuCount} 筆，超過上限 ${config.icu.max}，疑似 ICU 退化成逐字切分導致雜訊暴增`
		);
	} else {
		console.log(`  ${config.icu.query}：${icuCount} 筆`);
	}
}

// 子字串展開必須實際撈回額外結果——展開詞應選「是更長術語之子字串」的短詞
// （例：術語表有「燦軍軍團」時選「軍團」）。
if (config.expansion) {
	const direct = await core.search(config.expansion);
	const expanded = await shim.search(config.expansion);
	if (expanded.results.length <= direct.results.length) {
		failures.push(
			`「${config.expansion}」展開後 ${expanded.results.length} 筆，未多於直接查詢的 ${direct.results.length} 筆`
		);
	} else {
		console.log(
			`  ${config.expansion}：直接 ${direct.results.length} 筆 → 展開後 ${expanded.results.length} 筆`
		);
	}
}

// 術語成詞率：glossary 尚無已核准術語時（新專案）沒有分母，略過並提示。
if (terms.length) {
	const vocab = new Set(JSON.parse(await fs.readFile(path.join(BUNDLE, 'vocab.json'), 'utf8')));
	const hit = terms.filter((t) => vocab.has(t)).length;
	const rate = (hit / terms.length) * 100;
	console.log(`  術語成詞率：${hit}/${terms.length}（${rate.toFixed(1)}%）`);
	if (rate < TERM_RATE_MIN) failures.push(`術語成詞率 ${rate.toFixed(1)}% 低於門檻 ${TERM_RATE_MIN}%`);
} else {
	console.warn('  glossary 尚無已核准術語，略過成詞率檢查');
}

server.close();
if (failures.length) {
	console.error('\n驗收失敗：');
	for (const line of failures) console.error(`  ✗ ${line}`);
	process.exit(1);
}
console.log('\n驗收通過');
process.exit(0);
