// 共用斷詞器：建置端（Node）與查詢端（瀏覽器）使用同一份實作。
// 禁止使用 Node API 或 npm 相依——本檔會被複製到 dist/pagefind/ 送給瀏覽器。

const HAN = /[一-鿿㐀-䶿]/;

/**
 * 整串皆為漢字。建置端（術語表過濾、詞彙表輸出）與查詢端（詞彙表過濾）共用同一判準，
 * 各處自行定義會在調整字元範圍時默默漂移，導致兩端字典不一致。
 */
export const HAN_ONLY = /^[一-鿿㐀-䶿]+$/;

/**
 * @param {Iterable<string>} terms 全為漢字、長度 ≥ 2 的術語
 * @returns {{ segment(text: string): string[] }}
 */
export function createSegmenter(terms) {
	const dict = terms instanceof Set ? terms : new Set(terms);
	let maxLen = 2;
	for (const t of dict) if (t.length > maxLen) maxLen = t.length;

	// Intl.Segmenter 不存在時退回逐字切分，等同現況而非崩潰。
	const icu =
		typeof Intl !== 'undefined' && typeof Intl.Segmenter === 'function'
			? new Intl.Segmenter('zh-Hant', { granularity: 'word' })
			: null;

	/** 從 i 起做最長匹配，未命中回傳 null。長度 1 不參與匹配。 */
	function matchAt(text, i) {
		const limit = Math.min(maxLen, text.length - i);
		for (let len = limit; len > 1; len--) {
			const candidate = text.slice(i, i + len);
			if (dict.has(candidate)) return candidate;
		}
		return null;
	}

	function segment(text) {
		const out = [];
		let i = 0;
		while (i < text.length) {
			// 非漢字：整段原樣輸出，數字、英文、標點與其內部空格都保留。
			if (!HAN.test(text[i])) {
				let j = i;
				while (j < text.length && !HAN.test(text[j])) j++;
				const chunk = text.slice(i, j).trim();
				if (chunk) out.push(chunk);
				i = j;
				continue;
			}

			const hit = matchAt(text, i);
			if (hit) {
				out.push(hit);
				i += hit.length;
				continue;
			}

			// 未命中術語：取出這段漢字，但只處理到下一個術語起點為止，
			// 避免 ICU 跨越術語邊界把它吞掉。
			let end = i;
			while (end < text.length && HAN.test(text[end])) end++;
			let cut = end;
			for (let k = i + 1; k < end; k++) {
				if (matchAt(text, k)) {
					cut = k;
					break;
				}
			}
			const run = text.slice(i, cut);
			if (icu) {
				for (const piece of icu.segment(run)) {
					const word = piece.segment.trim();
					if (word) out.push(word);
				}
			} else {
				for (const ch of run) out.push(ch);
			}
			i = cut;
		}
		return out;
	}

	return { segment };
}
