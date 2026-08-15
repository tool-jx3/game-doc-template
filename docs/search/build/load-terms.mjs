// 從 glossary.json 取出可進斷詞字典的術語。
// 只收 status === 'approved' 的詞條：工作流程要求核准後才用於正文（Law 7），
// pending 或 rejected 的譯名進入字典只會讓搜尋字典與正文用詞不一致。
import fs from 'node:fs/promises';
import { HAN_ONLY } from '../client/segment.mjs';

/**
 * @param {object} glossary 解析後的 glossary.json 內容
 * @returns {string[]} 純漢字且長度 > 1 的已核准譯名；沒有任何可用詞條時為空陣列
 *   ——新專案的 glossary 只有 _meta，這是合法狀態，由呼叫端決定是否降級為純 ICU 斷詞。
 */
export function extractTerms(glossary) {
	const terms = [];
	for (const value of Object.values(glossary)) {
		if (!value || typeof value !== 'object') continue;
		if (value.status !== 'approved') continue;
		const zh = typeof value.zh === 'string' ? value.zh.trim() : '';
		if (zh.length > 1 && HAN_ONLY.test(zh)) terms.push(zh);
	}
	return terms;
}

/**
 * @param {string} glossaryPath glossary.json 的絕對路徑
 * @returns {Promise<string[]>}
 * @throws 檔案缺失或 JSON 損壞時——搜尋品質直接取決於術語表，
 *   靜默降級會產出看似正常但品質低落的索引。
 */
export async function loadTerms(glossaryPath) {
	let raw;
	try {
		raw = JSON.parse(await fs.readFile(glossaryPath, 'utf8'));
	} catch (err) {
		throw new Error(`無法讀取 glossary.json（${glossaryPath}）：${err.message}`);
	}
	return extractTerms(raw);
}
