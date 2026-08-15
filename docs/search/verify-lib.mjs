// 驗收設定的解析與健康檢查輔助。與 verify.mjs 分開是為了可測試。
// 查詢集因語料而異，各專案在 docs/search/verify-cases.json 維護自己的門檻；
// 設定是手寫檔案，格式錯誤要明確拋錯，靜默略過會讓驗收假通過。

function assertCount(value, name, label) {
	if (!Number.isInteger(value) || value < 0) {
		throw new Error(`${label} 的 ${name} 必須是非負整數，得到：${JSON.stringify(value)}`);
	}
}

function parseRange(entry, label) {
	if (typeof entry.query !== 'string' || !entry.query.trim()) {
		throw new Error(`${label} 缺少 query 或不是非空字串`);
	}
	assertCount(entry.min, 'min', label);
	assertCount(entry.max, 'max', label);
	if (entry.min > entry.max) {
		throw new Error(`${label} 的 min（${entry.min}）不得大於 max（${entry.max}）`);
	}
	return { query: entry.query.trim(), min: entry.min, max: entry.max };
}

/**
 * @param {unknown} raw verify-cases.json 解析後的內容
 * @returns {{
 *   cases: { query: string, min: number, max: number, first: RegExp | null }[],
 *   expansion: string | null,
 *   icu: { query: string, min: number, max: number } | null,
 * }}
 */
export function parseCases(raw) {
	if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
		throw new Error('verify-cases 設定必須是 JSON 物件');
	}

	const cases = [];
	if (raw.cases !== undefined) {
		if (!Array.isArray(raw.cases)) throw new Error('cases 必須是陣列');
		for (const [i, entry] of raw.cases.entries()) {
			const label = `cases[${i}]`;
			const range = parseRange(entry, label);
			let first = null;
			if (entry.first !== undefined && entry.first !== null) {
				if (typeof entry.first !== 'string') throw new Error(`${label} 的 first 必須是字串`);
				try {
					first = new RegExp(entry.first);
				} catch (err) {
					throw new Error(`${label} 的 first 不是合法的正則表達式：${err.message}`);
				}
			}
			cases.push({ ...range, first });
		}
	}

	let expansion = null;
	if (raw.expansion !== undefined && raw.expansion !== null) {
		if (typeof raw.expansion !== 'string' || !raw.expansion.trim()) {
			throw new Error('expansion 必須是非空字串');
		}
		expansion = raw.expansion.trim();
	}

	const icu = raw.icu !== undefined && raw.icu !== null ? parseRange(raw.icu, 'icu') : null;

	return { cases, expansion, icu };
}

/**
 * 健康句檢查的前提是「句中不含任何字典詞條」，否則字典最長匹配會繞過 ICU 分支、
 * 使檢查失去意義。stormlight 版本靠人工核對術語表保證這點；模板中每個專案的
 * glossary 都不同，改為在執行期剔除與句子重疊的術語，讓檢查與語料無關。
 * @param {string[]} terms
 * @param {string} sentence
 * @returns {string[]} 不出現在 sentence 中的術語
 */
export function healthTerms(terms, sentence) {
	return terms.filter((term) => !sentence.includes(term));
}
