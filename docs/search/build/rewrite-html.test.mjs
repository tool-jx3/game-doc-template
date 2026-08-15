import test from 'node:test';
import assert from 'node:assert/strict';
import { parse } from 'node-html-parser';
import { rewritePage } from './rewrite-html.mjs';
import { createSegmenter } from '../client/segment.mjs';

const seg = createSegmenter(['逐風師', '燦軍軍團', '碎刃']);

const PAGE = `<!doctype html><html lang="zh-TW"><body>
<main data-pagefind-body>
  <nav data-pagefind-ignore><a href="/">首頁</a>不該被索引</nav>
  <h1 id="title">逐風師</h1>
  <p>逐風師屬於燦軍軍團。</p>
  <h2 id="weapon">碎刃</h2>
  <p>碎刃是武器。</p>
</main>
</body></html>`;

test('產生帶 data-pagefind-body 的隱藏鏡像', () => {
	const out = rewritePage(PAGE, seg);
	assert.ok(out.html.includes('data-pagefind-body'));
	assert.ok(out.html.includes('aria-hidden="true"'));
});

test('原 main 上的 data-pagefind-body 被移除', () => {
	const out = rewritePage(PAGE, seg);
	assert.ok(!/<main[^>]*data-pagefind-body/.test(out.html));
});

test('可見文字節點未被改動', () => {
	const out = rewritePage(PAGE, seg);
	assert.ok(out.html.includes('<p>逐風師屬於燦軍軍團。</p>'));
});

test('鏡像內容以空格分隔詞元', () => {
	// 不斷言 ICU 對「屬於」的切法，只確認術語兩側確實被空格隔開。
	const mirror = rewritePage(PAGE, seg).html.split('aria-hidden')[1];
	assert.ok(/逐風師\s/.test(mirror), mirror);
	assert.ok(/\s燦軍軍團/.test(mirror), mirror);
});

test('鏡像掛在 <body> 尾端，不留在 <main> 內', () => {
	const root = parse(rewritePage(PAGE, seg).html);
	const mirror = root.querySelector('[data-pagefind-body]');
	assert.equal(root.querySelector('main [data-pagefind-body]'), null, '鏡像不得留在 main 內');
	assert.equal(mirror.parentNode.rawTagName, 'body');
	const elementChildren = root.querySelector('body').childNodes.filter((n) => n.nodeType === 1);
	assert.equal(elementChildren.at(-1), mirror, '鏡像應為 body 的最後一個元素');
});

test('鏡像標題不落在 Starlight 目錄觀察的 main 選擇器範圍內', () => {
	// starlight-toc.ts 觀察 `main :where(h1#_top,:where(h2,h3)[id])`。
	// 鏡像若留在 main 裡，這些選擇器會同時撈到可見標題與鏡像標題（鏡像整段位於頁尾且僅 1px 高，
	// 讀者捲到底時會一次全部回報 intersecting，目錄高亮因而跳回頁面前段）。
	const root = parse(rewritePage(PAGE, seg).html);
	assert.equal(root.querySelectorAll('main h1').length, 1);
	assert.equal(root.querySelectorAll('main h2[id]').length, 1);
	assert.equal(root.querySelectorAll('main h2[id]')[0].getAttribute('id'), 'weapon');
	// 鏡像本身仍保有標題與 id，供 Pagefind 產生 sub-results 錨點。
	assert.equal(root.querySelectorAll('[data-search-mirror] h2[id]').length, 1);
});

test('頁面沒有 <body> 時退回掛在原容器內', () => {
	const page = '<main data-pagefind-body><p>碎刃</p></main>';
	const root = parse(rewritePage(page, seg).html);
	assert.ok(root.querySelector('main [data-pagefind-body]'), '無 body 可掛時鏡像仍須存在於原容器內');
});

test('內嵌 script 內容不被破壞', () => {
	const page = `<html><body><main data-pagefind-body><p>碎刃</p></main>
<script>if (a < b && c > d) { x("</p>") }</script></body></html>`;
	const out = rewritePage(page, seg);
	assert.ok(out.html.includes('if (a < b && c > d) { x("</p>") }'), out.html);
});

test('標題保留 tag 與 id 供 sub-results 錨點使用', () => {
	const out = rewritePage(PAGE, seg);
	assert.ok(/<h2 id="weapon">[^<]*碎刃/.test(out.html), out.html);
});

test('data-pagefind-ignore 子樹不進鏡像', () => {
	const out = rewritePage(PAGE, seg);
	const mirror = out.html.slice(out.html.indexOf('aria-hidden'));
	assert.ok(!mirror.includes('不該被索引'));
});

test('回傳詞彙供詞彙表彙整', () => {
	const out = rewritePage(PAGE, seg);
	assert.ok(out.words.includes('逐風師'));
	assert.ok(out.words.includes('燦軍軍團'));
});

test('沒有 data-pagefind-body 的頁面回傳 null', () => {
	assert.equal(rewritePage('<html><body><p>無</p></body></html>', seg), null);
});

test('首次處理回傳 alreadyProcessed: false', () => {
	const out = rewritePage(PAGE, seg);
	assert.equal(out.alreadyProcessed, false);
});

test('對已處理過的頁面重跑不會巢狀累積鏡像', () => {
	const first = rewritePage(PAGE, seg);
	const second = rewritePage(first.html, seg);
	assert.equal(second.alreadyProcessed, true);
	assert.equal(second.html, first.html);
	assert.deepEqual(second.words, []);
	// 只有一層鏡像：第二次不得在既有鏡像內再嵌一層新鏡像。
	assert.equal((second.html.match(/data-pagefind-body/g) || []).length, 1);
});
