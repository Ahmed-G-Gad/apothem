// SPDX-License-Identifier: MIT

// Unit tests for cutAtWord, which shortens the excerpts in the generated
// reference tables. Run by `npm test`:
//
//   cd site && node --test scripts/cut-at-word.test.mjs

import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { cutAtWord } from './cut-at-word.mjs';

describe('cutAtWord', () => {
	it('returns text within the limit unchanged', () => {
		assert.equal(cutAtWord('short text', 20), 'short text');
	});

	it('cuts on a word boundary and marks the cut', () => {
		assert.equal(cutAtWord('one two three four', 12), 'one two …');
	});

	it('drops an unclosed code span', () => {
		assert.equal(cutAtWord('Run the `apothem install --dry-run` command', 20), 'Run the …');
	});

	it('keeps a closed code span', () => {
		assert.equal(cutAtWord('Run `apothem` then read the rest', 20), 'Run `apothem` then …');
	});

	it('drops an unclosed bold run', () => {
		assert.equal(cutAtWord('Keep this **bold phrase that runs on** here', 26), 'Keep this …');
	});

	it('keeps a closed bold run', () => {
		assert.equal(cutAtWord('Keep **bold** and more words', 20), 'Keep **bold** and …');
	});

	it('ignores asterisks inside code', () => {
		assert.equal(cutAtWord('Use `**` for bold text in pages', 20), 'Use `**` for bold …');
	});

	it('drops an unclosed link label', () => {
		assert.equal(cutAtWord('See [the install guide page](/docs/install) now', 24), 'See …');
	});

	it('drops a link cut inside its target, label included', () => {
		assert.equal(cutAtWord('See [guide](/docs/install and more) words', 30), 'See …');
	});

	it('drops an unclosed parenthesis', () => {
		assert.equal(cutAtWord('Some words (an aside that goes on) end', 24), 'Some words …');
	});

	it('repeats until no unclosed fragment is left', () => {
		assert.equal(cutAtWord('Start **bold [link label](/x y z) and', 30), 'Start …');
	});

	it('falls back to a hard cut that closes a long opening code span', () => {
		const text = '`apothem conformity gate --all --strict .` checks the tree';
		assert.equal(cutAtWord(text, 20), '`apothem conformity` …');
	});

	it('falls back to a hard cut without unclosed markers', () => {
		assert.equal(cutAtWord('**averyveryverylongboldword** rest', 12), 'averyveryv …');
	});

	it('keeps only the label of a link whose target the hard cut splits', () => {
		assert.equal(cutAtWord('[label](/very/long/url/path)', 15), 'label …');
		assert.equal(cutAtWord('**[label](/very/long/url/path)** x', 15), 'label …');
	});

	it('keeps the target text of an empty-label link the hard cut splits', () => {
		assert.equal(cutAtWord('[](/very/long/url/path)', 10), '/very/l …');
	});

	it('drops an unclosed single-asterisk emphasis run', () => {
		assert.equal(cutAtWord('a *italic phrase that runs long* end', 20), 'a …');
	});

	it('drops unclosed underscore emphasis and bold runs', () => {
		assert.equal(cutAtWord('a _italic phrase that runs long_ end', 20), 'a …');
		assert.equal(cutAtWord('a __bold phrase that runs long__ end', 20), 'a …');
	});

	it('keeps closed emphasis runs', () => {
		assert.equal(cutAtWord('a *b* c _d_ e and more words', 14), 'a *b* c _d_ e …');
	});

	it('removes unclosed emphasis markers from a hard cut', () => {
		assert.equal(cutAtWord('*averyveryverylongitalicword* rest', 12), 'averyveryve …');
		assert.equal(cutAtWord('_averyveryverylongitalicword_ rest', 12), 'averyveryve …');
		assert.equal(cutAtWord('__averyveryverylongboldword__ rest', 12), 'averyveryv …');
	});

	it('leaves underscores inside words and spaced asterisks alone', () => {
		assert.equal(cutAtWord('use snake_case_name and more words here', 20), 'use snake_case_name …');
		assert.equal(cutAtWord('5 * 3 is fifteen and more words', 18), '5 * 3 is fifteen …');
	});

	it('never returns only the cut mark', () => {
		for (const text of ['`aaaaaaaaaaaaaaaaaaaaaaaa`', '[bbbbbbbbbbbbbbbbbbbbbbbbbb](c)', '(dddddddddddddddddddddd)']) {
			assert.notEqual(cutAtWord(text, 10).trim(), '…');
		}
	});
});
