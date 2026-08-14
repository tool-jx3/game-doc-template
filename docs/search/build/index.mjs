// 建置後處理：改寫 HTML、以 forceLanguage:'en' 重建索引、換上 shim。
// 由 package.json 的 build script 在 astro build 之後執行。
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import * as pagefind from 'pagefind';
import { createSegmenter, HAN_ONLY } from '../client/segment.mjs';
import { rewritePage } from './rewrite-html.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DOCS = path.resolve(HERE, '../..');
const DIST = path.join(DOCS, 'dist');
const BUNDLE = path.join(DIST, 'pagefind');
const CLIENT = path.join(DOCS, 'search/client');
const GLOSSARY = path.resolve(DOCS, '../glossary.json');

async function loadTerms() {
	let raw;
	try {
		raw = JSON.parse(await fs.readFile(GLOSSARY, 'utf8'));
	} catch (err) {
		// 搜尋品質直接取決於術語表，靜默降級會產出看似正常但品質低落的索引。
		throw new Error(`無法讀取 glossary.json（${GLOSSARY}）：${err.message}`);
	}
	const terms = [];
	for (const value of Object.values(raw)) {
		if (!value || typeof value !== 'object') continue;
		const zh = typeof value.zh === 'string' ? value.zh.trim() : '';
		if (zh.length > 1 && HAN_ONLY.test(zh)) terms.push(zh);
	}
	if (!terms.length) throw new Error('glossary.json 未取得任何可用術語');
	return terms;
}

async function* htmlFiles(dir) {
	for (const entry of await fs.readdir(dir, { withFileTypes: true })) {
		const full = path.join(dir, entry.name);
		if (entry.isDirectory()) {
			if (full === BUNDLE) continue;
			yield* htmlFiles(full);
		} else if (entry.name.endsWith('.html')) {
			yield full;
		}
	}
}

/**
 * Pagefind 的 createIndex / addDirectory / writeFiles 即使部分失敗也可能正常回傳，
 * 錯誤只會出現在 response.errors 裡——不檢查就會產出「看似成功、實則殘缺」的索引。
 * 作法比照 @astrojs/starlight/integrations/pagefind.ts 的 assertPagefindResponse。
 */
function assertPagefind(response, label) {
	if (response.errors && response.errors.length) {
		for (const err of response.errors) console.error(`[search] Pagefind 錯誤（${label}）：${err}`);
		throw new Error(`Pagefind ${label} 回傳錯誤，索引可能不完整`);
	}
	return response;
}

async function main() {
	const terms = await loadTerms();
	const segmenter = createSegmenter(terms);
	console.log(`[search] 術語表 ${terms.length} 詞`);

	const vocab = new Set();
	let rewritten = 0;
	const skipped = [];
	for await (const file of htmlFiles(DIST)) {
		const rel = path.relative(DIST, file);
		const result = rewritePage(await fs.readFile(file, 'utf8'), segmenter);
		if (!result) {
			skipped.push(rel);
			continue;
		}
		if (result.alreadyProcessed) {
			// dist/ 已經跑過一次本腳本（例如未重跑 astro build 就手動重跑後處理）。
			// 此時內容已斷詞，再處理只會巢狀累積鏡像，因此比照 glossary 錯誤：明確中止而非靜默繼續。
			throw new Error(
				`${rel} 已完成過搜尋後處理（偵測到重複鏡像），dist/ 狀態不明確。請重新執行「astro build」產生乾淨的頁面後再重跑本腳本。`
			);
		}
		await fs.writeFile(file, result.html, 'utf8');
		for (const word of result.words) vocab.add(word);
		rewritten++;
	}
	console.log(`[search] 改寫 ${rewritten} 頁，相異詞 ${vocab.size}`);
	if (skipped.length) {
		// Starlight 每頁都會產生 data-pagefind-body，缺失代表版面結構變動。
		console.warn(`[search] ${skipped.length} 頁無 data-pagefind-body：${skipped.join('、')}`);
	}

	// Starlight 已寫入一份 zh-tw 索引，不清除會殘留陳舊分塊。
	await fs.rm(BUNDLE, { recursive: true, force: true });

	const createResult = assertPagefind(await pagefind.createIndex({ forceLanguage: 'en' }), 'createIndex');
	const { index } = createResult;
	if (!index) throw new Error('Pagefind createIndex 未回傳 index');

	const addResult = assertPagefind(await index.addDirectory({ path: DIST }), 'addDirectory');
	if (rewritten + skipped.length !== addResult.page_count) {
		// page_count 是 Pagefind 在 dist 掃到的 HTML 檔案數，對應到我方走訪的同一批檔案，
		// 因此應等於「改寫頁數 ＋ 因無 data-pagefind-body 而跳過的頁數」（404.html 等天生沒有的頁面
		// 都落在 skipped 裡）。不一致代表兩邊看到的檔案集合有落差，值得留意但不視為致命錯誤。
		console.warn(
			`[search] addDirectory 回報 ${addResult.page_count} 頁，實際改寫 ${rewritten} ＋ 跳過 ${skipped.length} 頁，數字不一致`
		);
	}

	assertPagefind(await index.writeFiles({ outputPath: BUNDLE }), 'writeFiles');
	await pagefind.close();

	// 查詢端只採用「純漢字且長度 > 1」的詞條（prepare() 用同一條件過濾），含空格的英數片段與
	// 純標點傳過去也只是被丟掉，因此在寫出前就濾掉，省下的是實打實的下載量。
	const vocabOut = [...vocab].filter((word) => word.length > 1 && HAN_ONLY.test(word));
	console.log(`[search] 詞彙表寫出 ${vocabOut.length} 詞（自 ${vocab.size} 個詞元過濾而來）`);
	await fs.writeFile(path.join(BUNDLE, 'vocab.json'), JSON.stringify(vocabOut), 'utf8');
	await fs.rename(path.join(BUNDLE, 'pagefind.js'), path.join(BUNDLE, 'pagefind-core.js'));
	for (const name of ['segment.mjs', 'excerpt.mjs', 'expand.mjs']) {
		await fs.copyFile(path.join(CLIENT, name), path.join(BUNDLE, name));
	}
	await fs.copyFile(path.join(CLIENT, 'shim.mjs'), path.join(BUNDLE, 'pagefind.js'));

	console.log('[search] 索引重建完成');
}

main().catch((err) => {
	console.error('[search] 建置失敗：', err);
	process.exit(1);
});
