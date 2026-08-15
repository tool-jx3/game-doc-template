import test from 'node:test';
import assert from 'node:assert/strict';
import { parseCases, healthTerms } from './verify-lib.mjs';

test('parseCases：完整設定解析成查詢集，first 編譯為 RegExp', () => {
	const parsed = parseCases({
		cases: [{ query: '無可逃避的衰敗', min: 1, max: 5, first: '/(dustbringer|skybreaker)/' }],
		expansion: '軍團',
		icu: { query: '轉過身來', min: 1, max: 10 },
	});
	assert.equal(parsed.cases.length, 1);
	assert.equal(parsed.cases[0].query, '無可逃避的衰敗');
	assert.equal(parsed.cases[0].min, 1);
	assert.equal(parsed.cases[0].max, 5);
	assert.ok(parsed.cases[0].first instanceof RegExp);
	assert.ok(parsed.cases[0].first.test('/rules/dustbringer/'));
	assert.equal(parsed.expansion, '軍團');
	assert.deepEqual(parsed.icu, { query: '轉過身來', min: 1, max: 10 });
});

test('parseCases：cases/expansion/icu 皆可省略，回傳空集合', () => {
	const parsed = parseCases({});
	assert.deepEqual(parsed.cases, []);
	assert.equal(parsed.expansion, null);
	assert.equal(parsed.icu, null);
});

test('parseCases：first 可省略（只驗筆數區間）', () => {
	const parsed = parseCases({ cases: [{ query: '颶光', min: 1, max: 20 }] });
	assert.equal(parsed.cases[0].first, null);
});

test('parseCases：非物件、query 缺失、min > max、壞 regex 都要明確拋錯', () => {
	assert.throws(() => parseCases(null), /設定/);
	assert.throws(() => parseCases({ cases: [{ min: 1, max: 5 }] }), /query/);
	assert.throws(() => parseCases({ cases: [{ query: '颶光', min: 9, max: 5 }] }), /min/);
	assert.throws(() => parseCases({ cases: [{ query: '颶光', min: 1, max: 5, first: '(' }] }), /first/);
	assert.throws(() => parseCases({ icu: { query: '', min: 1, max: 10 } }), /query/);
});

test('parseCases：min 與 max 必須是非負整數', () => {
	assert.throws(() => parseCases({ cases: [{ query: '颶光', min: -1, max: 5 }] }), /min/);
	assert.throws(() => parseCases({ cases: [{ query: '颶光', min: 1, max: '5' }] }), /max/);
});

test('healthTerms：剔除出現在健康句中的術語，其餘保留', () => {
	const sentence = '今天早上他去市場買了新鮮的蔬菜和水果';
	const terms = ['市場', '蔬菜', '逐風師', '颶光'];
	assert.deepEqual(healthTerms(terms, sentence), ['逐風師', '颶光']);
});

test('healthTerms：無重疊時原樣保留', () => {
	assert.deepEqual(healthTerms(['逐風師'], '完全無關的句子'), ['逐風師']);
});
