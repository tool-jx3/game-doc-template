// 摘要清理：索引內容含注入的詞邊界空格，顯示前需還原。
// 禁止使用 Node API 或 npm 相依——本檔會被複製到 dist/pagefind/ 送給瀏覽器。

// 漢字、CJK 標點、全形符號視為同一類：彼此之間的空格都是注入的。
// 末段的幾個字元落在一般標點區（U+2000–U+206F）與 Latin-1 補充區，不在上面的 CJK 區段裡，
// 但在本語料中一律作為中文標點使用，必須同樣視為 CJK：
// U+2014 破折號（——，本語料最常見的注入空格來源）、U+2015 橫線、U+2026 刪節號（……）、
// U+00B7 與 U+2027 間隔號（譯名分隔，如「丹‧威爾斯」）。
const CJK =
	'\\u3000-\\u303f\\u4e00-\\u9fff\\u3400-\\u4dbf\\uff00-\\uffef\\u2014\\u2015\\u2026\\u00b7\\u2027';

const BETWEEN_CJK = new RegExp(`([${CJK}])\\s+(?=[${CJK}])`, 'g');
// mark 前：只有當 mark 內第一個字也是 CJK 時才收掉空格
const BEFORE_MARK = new RegExp(`([${CJK}])\\s+(?=<mark>[${CJK}])`, 'g');
// mark 後：只有當 mark 內最後一個字也是 CJK 時才收掉空格
const AFTER_MARK = new RegExp(`([${CJK}])</mark>\\s+(?=[${CJK}])`, 'g');

/**
 * @param {string} html 含 <mark> 標籤的摘要片段
 * @returns {string}
 */
export function cleanExcerpt(html) {
	if (!html) return html;
	return html.replace(BETWEEN_CJK, '$1').replace(BEFORE_MARK, '$1').replace(AFTER_MARK, '$1</mark>');
}
