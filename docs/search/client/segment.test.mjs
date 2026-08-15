import test from 'node:test';
import assert from 'node:assert/strict';
import { createSegmenter } from './segment.mjs';

const TERMS = ['逐風師', '燦軍軍團', '意識界', '碎刃', '橋九小隊'];

test('術語優先於 ICU 斷詞', () => {
  const { segment } = createSegmenter(TERMS);
  assert.deepEqual(segment('逐風師'), ['逐風師']);
});

test('最長匹配：不得切成較短的術語組合', () => {
  const { segment } = createSegmenter([...TERMS, '燦軍', '軍團']);
  assert.deepEqual(segment('燦軍軍團'), ['燦軍軍團']);
});

test('術語出現在句中時邊界正確', () => {
  const { segment } = createSegmenter(TERMS);
  const words = segment('他是逐風師');
  assert.ok(words.includes('逐風師'), `實際切分：${words.join('|')}`);
});

test('非漢字區段原樣保留', () => {
  const { segment } = createSegmenter(TERMS);
  assert.deepEqual(segment('1d6 + 6'), ['1d6 + 6']);
});

test('中英數混排時英數不被拆散', () => {
  const { segment } = createSegmenter(TERMS);
  const words = segment('碎刃 GM 判定 +2');
  assert.ok(words.includes('碎刃'), `實際切分：${words.join('|')}`);
  assert.ok(words.some((w) => w.includes('GM')), `實際切分：${words.join('|')}`);
  assert.ok(words.some((w) => w.includes('+2')), `實際切分：${words.join('|')}`);
});

test('切分結果串接後可還原原文的非空白內容', () => {
  const { segment } = createSegmenter(TERMS);
  const input = '逐風師與燦軍軍團的關係，以及碎刃的來歷。';
  const rejoined = segment(input).join('').replace(/\s+/g, '');
  assert.equal(rejoined, input.replace(/\s+/g, ''));
});

test('單字術語不參與匹配（避免過度切分）', () => {
  const { segment } = createSegmenter(['光']);
  assert.deepEqual(segment('光'), ['光']);
});

test('空字串回傳空陣列', () => {
  const { segment } = createSegmenter(TERMS);
  assert.deepEqual(segment(''), []);
});
