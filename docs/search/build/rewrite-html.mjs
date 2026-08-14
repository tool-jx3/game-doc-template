// 建置期：把可見內容轉成已斷詞的隱藏鏡像供 Pagefind 索引。
import { parse } from 'node-html-parser';

const HIDDEN_STYLE = 'position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)';
const HEADINGS = new Set(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']);
const SKIP_TAGS = new Set(['script', 'style', 'noscript', 'template']);
const ELEMENT_NODE = 1;
const TEXT_NODE = 3;
// 標記本檔產生的鏡像本身，讓重跑時可辨識「這個 data-pagefind-body 其實是上一輪的產物」，
// 避免對已斷詞的內容再次斷詞、無界巢狀累積。
const MIRROR_ATTR = 'data-search-mirror';

function escapeHtml(text) {
	return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function escapeAttr(value) {
	return escapeHtml(value).replace(/"/g, '&quot;');
}

/**
 * @param {string} html 單一頁面的完整 HTML
 * @param {{ segment(text: string): string[] }} segmenter
 * @returns {{ html: string, words: string[], alreadyProcessed: boolean } | null}
 *   `alreadyProcessed: true` 代表命中的 `[data-pagefind-body]` 其實是上一輪產生的鏡像本身
 *   （html 原樣傳回、words 為空陣列），呼叫端應視為 dist 狀態不明確而中止，不可當成一般頁面繼續寫回。
 */
export function rewritePage(html, segmenter) {
	const root = parse(html);
	// Starlight 把 data-pagefind-body 掛在 <main> 上；這裡指的是那個被索引的容器，不是 <body>。
	const pagefindBody = root.querySelector('[data-pagefind-body]');
	if (!pagefindBody) return null;
	if (pagefindBody.hasAttribute(MIRROR_ATTR)) {
		return { html, words: [], alreadyProcessed: true };
	}

	const blocks = [];
	let buffer = [];

	const flush = () => {
		const text = buffer.join(' ').replace(/\s+/g, ' ').trim();
		buffer = [];
		if (text) blocks.push({ tag: 'p', id: null, text });
	};

	const walk = (node) => {
		if (node.nodeType === TEXT_NODE) {
			buffer.push(node.text);
			return;
		}
		if (node.nodeType !== ELEMENT_NODE) return;
		if (node.hasAttribute('data-pagefind-ignore')) return;
		const tag = (node.rawTagName || '').toLowerCase();
		if (SKIP_TAGS.has(tag)) return;
		if (HEADINGS.has(tag)) {
			flush();
			const text = node.text.replace(/\s+/g, ' ').trim();
			if (text) blocks.push({ tag, id: node.getAttribute('id') || null, text });
			return;
		}
		for (const child of node.childNodes) walk(child);
	};

	for (const child of pagefindBody.childNodes) walk(child);
	flush();

	const words = [];
	const parts = [];
	for (const block of blocks) {
		const segmented = segmenter.segment(block.text);
		if (!segmented.length) continue;
		words.push(...segmented);
		const idAttr = block.id ? ` id="${escapeAttr(block.id)}"` : '';
		parts.push(`<${block.tag}${idAttr}>${escapeHtml(segmented.join(' '))}</${block.tag}>`);
	}

	pagefindBody.removeAttribute('data-pagefind-body');
	const mirror = parse(
		`<div data-pagefind-body ${MIRROR_ATTR} aria-hidden="true" style="${HIDDEN_STYLE}">${parts.join('')}</div>`
	).firstChild;
	// 掛在 <body> 尾端而非 <main> 內：Starlight 的目錄用 `main :where(h1#_top,:where(h2,h3)[id])`
	// 做 IntersectionObserver，鏡像的標題若留在 main 裡會被一併觀察，捲到頁尾時同時回報可見、
	// 使目錄高亮亂跳。Pagefind 只認 [data-pagefind-body] 屬性，元素位置不影響索引。
	(root.querySelector('body') || pagefindBody).appendChild(mirror);

	return { html: root.toString(), words, alreadyProcessed: false };
}
