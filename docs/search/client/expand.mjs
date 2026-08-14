// 查詢展開與結果合併的純邏輯。與 shim 分開是為了可測試——
// shim 靜態 import 只存在於建置產物中的 pagefind-core.js。
// 禁止使用 Node API 或 npm 相依。
import { cleanExcerpt } from './excerpt.mjs';

export const EXPANSION_LIMIT = 12;
export const EXPANSION_PENALTY = 0.5;

/** 找出「包含查詢字串但不以其開頭」的詞；開頭的情況 Pagefind 前綴比對已涵蓋。 */
export function expansionCandidates(query, vocab, limit = EXPANSION_LIMIT) {
	if (!query || query.length < 2) return [];
	const out = [];
	for (const word of vocab) {
		if (word.length > query.length && !word.startsWith(query) && word.includes(query)) {
			out.push(word);
			if (out.length >= limit) break;
		}
	}
	return out;
}

/**
 * 依 id 去重；展開撈回者的分數乘上 penalty 做相對降權，非絕對排序保證——
 * 分數夠高的展開命中仍可能排在低分的直接命中之前（例：整頁圍繞展開詞的頁面
 * 理應優先於只是順帶提到查詢字串的頁面）。
 */
export function mergeResults(direct, expandedList, penalty = EXPANSION_PENALTY) {
	const byId = new Map();
	for (const result of direct.results) byId.set(result.id, result);
	for (const set of expandedList) {
		for (const result of set.results) {
			if (byId.has(result.id)) continue;
			byId.set(result.id, Object.assign({}, result, { score: (result.score ?? 0) * penalty }));
		}
	}
	return [...byId.values()].sort((a, b) => (b.score ?? 0) - (a.score ?? 0));
}

/**
 * 包裝 data()，顯示前清掉注入的詞邊界空格。
 * `sub_results[].title` 同樣要清：它來自 fragment 的 anchors[].text，而 anchors 取自鏡像裡
 * 已斷詞的標題，官方 UI 直接拿它當子項連結文字渲染（showSubResults）。
 */
export function withCleanExcerpt(result) {
	const original = result.data;
	return Object.assign({}, result, {
		data: async () => {
			const data = await original();
			const out = Object.assign({}, data, { excerpt: cleanExcerpt(data.excerpt) });
			if (Array.isArray(data.sub_results)) {
				out.sub_results = data.sub_results.map((sub) =>
					Object.assign({}, sub, {
						excerpt: cleanExcerpt(sub.excerpt),
						title: cleanExcerpt(sub.title),
					})
				);
			}
			return out;
		},
	});
}
