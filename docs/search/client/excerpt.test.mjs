import test from 'node:test';
import assert from 'node:assert/strict';
import { cleanExcerpt } from './excerpt.mjs';

test('移除漢字之間的空格', () => {
	assert.equal(cleanExcerpt('一道 英姿 颯爽'), '一道英姿颯爽');
});

test('連續多組空格全部收掉', () => {
	assert.equal(cleanExcerpt('變 遷 中 的 世 界'), '變遷中的世界');
});

test('全形標點視同漢字，兩側空格收掉', () => {
	assert.equal(cleanExcerpt('銳利傷害 。 攻擊'), '銳利傷害。攻擊');
});

test('數字與運算子旁的空格保留', () => {
	assert.equal(cleanExcerpt('命中 ：9（1d6 + 6） 銳利傷害'), '命中：9（1d6 + 6）銳利傷害');
});

test('英文與漢字之間的空格保留', () => {
	assert.equal(cleanExcerpt('寰宇 RPG 及其 設定'), '寰宇 RPG 及其設定');
});

test('mark 標籤兩側的空格收掉，標籤本身不動', () => {
	assert.equal(
		cleanExcerpt('▶ <mark>無可逃避的衰敗</mark> （ 消耗 1 授予 ）'),
		'▶ <mark>無可逃避的衰敗</mark>（消耗 1 授予）'
	);
});

test('mark 內非 CJK 時兩側空格保留', () => {
	assert.equal(cleanExcerpt('傷害 <mark>6</mark> 點'), '傷害 <mark>6</mark> 點');
});

test('mark 內英文時兩側空格保留', () => {
	assert.equal(cleanExcerpt('寰宇 <mark>RPG</mark> 及其設定'), '寰宇 <mark>RPG</mark> 及其設定');
});

test('mark 內 CJK 時兩側空格仍要收掉', () => {
	assert.equal(cleanExcerpt('一道 <mark>英姿</mark> 颯爽'), '一道<mark>英姿</mark>颯爽');
});

test('mark 與漢字間距混合：標籤兩側保留，其餘漢字間收掉', () => {
	assert.equal(cleanExcerpt('攻擊 <mark>RPG</mark> 的 角色'), '攻擊 <mark>RPG</mark> 的角色');
});

// 以下四條的輸入都是真實語料經本專案斷詞器（glossary 最長匹配 ＋ ICU）實跑後的輸出，
// 不是手寫的近似值；斷言的是「清理後完全還原成原文」，任何一個標點漏收都會失敗。
test('破折號兩側的注入空格收掉（真實語料往返）', () => {
	// 來源：docs/src/content/docs/world-guide/adversaries/yu-nerig.md
	const segmented =
		'它們 與 靈 的 聯結 使 其 成長 到 巨大 的 體型 ， 儘管 它們 不如 裂谷魔 那般 令人 畏懼 —— 事實上 ， 由內利 被 視為 珍 饈 美味 。';
	assert.equal(
		cleanExcerpt(segmented),
		'它們與靈的聯結使其成長到巨大的體型，儘管它們不如裂谷魔那般令人畏懼——事實上，由內利被視為珍饈美味。'
	);
});

test('刪節號兩側的注入空格收掉（真實語料往返）', () => {
	// 來源：docs/src/content/docs/world-guide/the-world.md
	const segmented = '颶風牆 逼近 了 …… 那是 一道 由 水 、 泥土 和 岩石 組成 的 巨 牆 ， 高達 數百 尺';
	assert.equal(cleanExcerpt(segmented), '颶風牆逼近了……那是一道由水、泥土和岩石組成的巨牆，高達數百尺');
});

test('間隔號兩側的注入空格收掉（U+2027 與 U+00B7）', () => {
	assert.equal(cleanExcerpt('丹 ‧ 威爾斯 與 達利納 · 科林'), '丹‧威爾斯與達利納·科林');
});

test('破折號旁的 mark 標籤同樣收掉空格', () => {
	assert.equal(
		cleanExcerpt('令人畏懼 —— <mark>事實上</mark> ， 由內利'),
		'令人畏懼——<mark>事實上</mark>，由內利'
	);
});

test('純英文語境的破折號空格保留', () => {
	assert.equal(cleanExcerpt('Cosmere — RPG'), 'Cosmere — RPG');
	assert.equal(cleanExcerpt('1d6 …… 2d6'), '1d6 …… 2d6');
});

test('空值原樣回傳', () => {
	assert.equal(cleanExcerpt(''), '');
	assert.equal(cleanExcerpt(undefined), undefined);
});
