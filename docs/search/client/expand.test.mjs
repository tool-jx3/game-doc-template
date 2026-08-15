import test from 'node:test';
import assert from 'node:assert/strict';
import { expansionCandidates, mergeResults, withCleanExcerpt } from './expand.mjs';

const VOCAB = ['燦軍軍團', '最後軍團', '軍團', '逐風師', '橋九小隊', '風'];

test('展開找出包含查詢字串但不以其開頭的詞', () => {
	const out = expansionCandidates('軍團', VOCAB);
	assert.ok(out.includes('燦軍軍團'));
	assert.ok(out.includes('最後軍團'));
});

test('展開不重複收錄查詢字串本身', () => {
	assert.ok(!expansionCandidates('軍團', VOCAB).includes('軍團'));
});

test('以查詢字串開頭的詞不展開（前綴比對已涵蓋）', () => {
	assert.ok(!expansionCandidates('風', VOCAB).includes('風'));
	assert.deepEqual(expansionCandidates('逐風', VOCAB), []);
});

test('單字查詢不展開', () => {
	assert.deepEqual(expansionCandidates('軍', VOCAB), []);
});

test('展開數量受 limit 限制', () => {
	assert.equal(expansionCandidates('軍團', VOCAB, 1).length, 1);
});

test('合併時直接命中優先於展開命中', () => {
	const direct = { results: [{ id: 'a', score: 1 }] };
	const expanded = [{ results: [{ id: 'b', score: 10 }] }];
	const merged = mergeResults(direct, expanded, 0.05);
	assert.deepEqual(
		merged.map((r) => r.id),
		['a', 'b']
	);
});

test('合併時同一結果不重複，且保留直接命中的分數', () => {
	const direct = { results: [{ id: 'a', score: 1 }] };
	const expanded = [{ results: [{ id: 'a', score: 99 }] }];
	const merged = mergeResults(direct, expanded, 0.5);
	assert.equal(merged.length, 1);
	assert.equal(merged[0].score, 1);
});

test('降權是相對的，非絕對排序保證：高分展開命中仍可排在低分直接命中之前', () => {
	const direct = { results: [{ id: 'a', score: 1 }] };
	const expanded = [{ results: [{ id: 'b', score: 100 }] }];
	const merged = mergeResults(direct, expanded, 0.5);
	assert.deepEqual(
		merged.map((r) => r.id),
		['b', 'a']
	);
});

// sub_results 的 title 與 excerpt 都是 UI 直接顯示的文字（showSubResults 用 title 當連結文字），
// 兩者都取自已斷詞的鏡像，都必須清理。fixture 的 title 取自實際建置產物的 anchors[].text。
test('包裝後的結果會清掉摘要與子項標題的空格，且保留其他欄位', async () => {
	const raw = {
		id: 'a',
		score: 1,
		data: async () => ({
			url: '/x/',
			excerpt: '一道 英姿 颯爽',
			sub_results: [
				{ url: '/x/#h', title: '黎明 碎片 守護 者', excerpt: '碎刃 的 來歷' },
				{ url: '/x/#b', title: '附錄 A： 裝備', excerpt: '寰宇 RPG 及其 設定' },
			],
		}),
	};
	const data = await withCleanExcerpt(raw).data();
	assert.equal(data.excerpt, '一道英姿颯爽');
	assert.equal(data.sub_results[0].title, '黎明碎片守護者');
	assert.equal(data.sub_results[0].excerpt, '碎刃的來歷');
	assert.equal(data.sub_results[0].url, '/x/#h');
	// 合法的半形空格（英數與漢字之間）不得被誤收
	assert.equal(data.sub_results[1].title, '附錄 A：裝備');
	assert.equal(data.sub_results[1].excerpt, '寰宇 RPG 及其設定');
	assert.equal(data.url, '/x/');
});

test('子項缺 title 欄位時不拋錯', async () => {
	const raw = { id: 'a', data: async () => ({ excerpt: '', sub_results: [{ url: '/x/#h' }] }) };
	const data = await withCleanExcerpt(raw).data();
	assert.equal(data.sub_results[0].url, '/x/#h');
});
