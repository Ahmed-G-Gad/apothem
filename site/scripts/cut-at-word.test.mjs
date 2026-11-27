// SPDX-License-Identifier: MIT

// Unit tests for cutAtWord, which shortens the excerpts in the generated
// reference tables. Run by `npm test`:
//
//   cd site && node --test scripts/cut-at-word.test.mjs

import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { fromMarkdown } from 'mdast-util-from-markdown';
import { gfmFromMarkdown } from 'mdast-util-gfm';
import { gfm } from 'micromark-extension-gfm';
import { cutAtWord, plainCut } from './cut-at-word.mjs';
import { cutInputs } from './update-reference-inventory.mjs';

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
		assert.equal(cutAtWord('Keep **bold** and more words', 20), 'Keep **bold** and more …');
	});

	it('ignores asterisks inside code', () => {
		assert.equal(cutAtWord('Use `**` for bold text in pages', 20), 'Use `**` for bold …');
	});

	it('keeps the label text of a link the cut lands in', () => {
		assert.equal(cutAtWord('See [the install guide page](/docs/install) now', 24), 'See the install guide …');
	});

	it('counts a link label, not its target, toward the limit', () => {
		assert.equal(
			cutAtWord('See [guide](/docs/a/very/long/target/path) and more words', 20),
			'See [guide](/docs/a/very/long/target/path) and more …',
		);
	});

	it('leaves brackets that never formed a link as they are', () => {
		assert.equal(cutAtWord('See [guide](/docs/install and more) words', 40), 'See [guide](/docs/install and more) …');
	});

	it('steps back to a boundary before a parenthesis the cut would leave open', () => {
		assert.equal(cutAtWord('Some words (an aside that goes on) end', 24), 'Some words …');
	});

	it('keeps a closed parenthesis before the cut', () => {
		assert.equal(cutAtWord('Steps (one) then more words here and there', 30), 'Steps (one) then more words …');
	});

	it('cuts inside a parenthesis the source never closes', () => {
		assert.equal(cutAtWord('(an aside that never closes and goes on', 24), '(an aside that never …');
	});

	it('keeps markers that were literal text in the source', () => {
		assert.equal(cutAtWord('Start **bold [link label](/x) y z and', 30), 'Start **bold [link label](/x) y z …');
	});

	it('falls back to a hard cut that closes a long opening code span', () => {
		const text = '`apothem conformity gate --all --strict .` checks the tree';
		assert.equal(cutAtWord(text, 20), '`apothem conformity` …');
	});

	it('falls back to a hard cut without unclosed markers', () => {
		assert.equal(cutAtWord('**averyveryverylongboldword** rest', 12), 'averyveryver …');
	});

	it('keeps a link whose label fits, however long its target', () => {
		assert.equal(cutAtWord('[label](/very/long/url/path)', 15), '[label](/very/long/url/path)');
		assert.equal(cutAtWord('**[label](/very/long/url/path)** x', 15), '**[label](/very/long/url/path)** x');
		assert.equal(cutAtWord('[](/very/long/url/path)', 10), '[](/very/long/url/path)');
	});

	it('hard-cuts a long link label to plain text', () => {
		assert.equal(cutAtWord('[averyveryverylonglabel](/x) rest', 10), 'averyveryv …');
	});

	it('drops an unclosed single-asterisk emphasis run', () => {
		assert.equal(cutAtWord('a *italic phrase that runs long* end', 20), 'a …');
	});

	it('drops unclosed underscore emphasis and bold runs', () => {
		assert.equal(cutAtWord('a _italic phrase that runs long_ end', 20), 'a …');
		assert.equal(cutAtWord('a __bold phrase that runs long__ end', 20), 'a …');
	});

	it('keeps closed emphasis runs', () => {
		assert.equal(cutAtWord('a *b* c _d_ e and more words', 14), 'a *b* c _d_ e and …');
	});

	it('removes unclosed emphasis markers from a hard cut', () => {
		assert.equal(cutAtWord('*averyveryverylongitalicword* rest', 12), 'averyveryver …');
		assert.equal(cutAtWord('_averyveryverylongitalicword_ rest', 12), 'averyveryver …');
		assert.equal(cutAtWord('__averyveryverylongboldword__ rest', 12), 'averyveryver …');
	});

	it('leaves underscores inside words and spaced asterisks alone', () => {
		assert.equal(cutAtWord('use snake_case_name and more words here', 20), 'use snake_case_name …');
		assert.equal(cutAtWord('5 * 3 is fifteen and more words', 18), '5 * 3 is fifteen …');
	});

	it('keeps a link whose target holds an underscore', () => {
		assert.equal(
			cutAtWord('see [docs](https://x.com/_private) and more words here', 20),
			'see [docs](https://x.com/_private) and more …',
		);
		assert.equal(
			cutAtWord('see <https://x.com/_a> and https://y.com/_b_ then more words', 50),
			'see <https://x.com/_a> and https://y.com/_b_ then …',
		);
	});

	it('leaves an underscore that never closes in the full text alone', () => {
		assert.equal(cutAtWord('path ~/.cache/_tmp holds data and more words follow', 40), 'path ~/.cache/_tmp holds data and more …');
	});

	it('leaves an asterisk that never closes in the full text alone', () => {
		assert.equal(cutAtWord('(see *note) more words here please', 20), '(see *note) more …');
	});

	it('leaves snake_case path segments alone', () => {
		assert.equal(
			cutAtWord('state in ~/.apothem/_state_dir/run_log.json and _more text_ later', 46),
			'state in ~/.apothem/_state_dir/run_log.json …',
		);
	});

	it('drops emphasis only when its closer lies past the cut', () => {
		assert.equal(cutAtWord('a ~/_x then _italic phrase runs long_ end', 26), 'a ~/_x then …');
	});

	it('never returns only the cut mark', () => {
		for (const text of ['`aaaaaaaaaaaaaaaaaaaaaaaa`', '[bbbbbbbbbbbbbbbbbbbbbbbbbb](c)', '(dddddddddddddddddddddd)']) {
			assert.notEqual(cutAtWord(text, 10).trim(), '…');
		}
	});

	it('keeps a whole link whose target has a title and an underscore', () => {
		assert.equal(cutAtWord('See [a](/p/_x "t") and more words then y_ z', 20), 'See [a](/p/_x "t") and more …');
	});

	it('keeps a www autolink whose path holds an underscore', () => {
		assert.equal(cutAtWord('Go to www.x.com/_a and some words then b_ c', 36), 'Go to www.x.com/_a and some words …');
	});

	it('drops a strikethrough run the cut lands in', () => {
		assert.equal(cutAtWord('Tilde ~~strike text here~~ more', 18), 'Tilde …');
		assert.equal(cutAtWord('Tilde ~~strike~~ and more words', 20), 'Tilde ~~strike~~ and …');
	});

	it('keeps a literal "** " that never opens bold', () => {
		assert.equal(cutAtWord('** not bold and _x_ y z w', 12), '** not bold …');
	});

	it('never splits a backslash escape or a character reference', () => {
		const text = `a ${BACKSLASH}*b c &amp; d e f g h`;
		assert.equal(cutAtWord(text, 12), `a ${BACKSLASH}*b c &amp; d …`);
	});

	it('writes the plain-text fallback escaped, within the limit', () => {
		assert.equal(plainCut('a **b** c d e f g', 12), `a ${BACKSLASH}*${BACKSLASH}*b${BACKSLASH}*${BACKSLASH}* c …`);
		assert.equal(plainCut('averyveryverylongword', 10), 'averyver …');
		for (const limit of [3, 8, 12, 20]) assert.ok(plainCut('one two three four five six', limit).length <= Math.max(limit, 3));
	});

	it('drops a code span the cut lands in after other text', () => {
		assert.equal(cutAtWord('Run `a b c d e f g` now', 10), 'Run …');
	});

	it('leaves no markup literal that was not literal in the inventory excerpts', () => {
		const inputs = cutInputs();
		assert.ok(inputs.length > 100, `expected the inventory inputs, got ${inputs.length}`);
		const random = seeded(281);
		for (const { text, limit } of inputs) {
			const limits = [limit, ...Array.from({ length: 12 }, () => 4 + Math.floor(random() * 200))];
			for (const cut of limits) assertNoNewLiterals(text, cut);
		}
	});

	it('leaves no markup literal that was not literal in random Markdown', () => {
		const random = seeded(7);
		for (let i = 0; i < 3000; i += 1) {
			const text = randomMarkdown(random);
			assertNoNewLiterals(text, 1 + Math.floor(random() * text.length));
		}
	});
});

const BACKSLASH = String.fromCharCode(92);
const MARKUP = new Set(['*', '_', '~', '[', '`']);

// A small deterministic generator (mulberry32), so a failure reproduces.
function seeded(seed) {
	let state = seed >>> 0;
	return () => {
		state = (state + 0x6d2b79f5) >>> 0;
		let t = state;
		t = Math.imul(t ^ (t >>> 15), t | 1);
		t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
		return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
	};
}

const PIECES = [
	'word', 'snake_case', 'a', 'go', 'longerword', '*', '_', '**', '__', '~', '~~', '`', '``', '[', ']', '(', ')',
	'*em*', '_em_', '**bold**', '~~gone~~', '`code`', '`a b`', '[label](/x)', '[a b](/p/_x "t")', '<https://x.com/_a>',
	'www.x.com/_a', 'https://y.com/_b_', '&amp;', `${BACKSLASH}*`, `${BACKSLASH}_`, '![alt](/i.png)', '5 * 3', '** ',
];

function randomMarkdown(random) {
	const count = 2 + Math.floor(random() * 14);
	let out = '';
	for (let i = 0; i < count; i += 1) {
		out += PIECES[Math.floor(random() * PIECES.length)];
		if (random() < 0.7) out += ' ';
	}
	return out.trim() || 'word';
}

// The characters a page shows for `markdown`, each marked literal when it
// comes from a text node (outside code, links' targets and other markup).
function shownCharacters(markdown) {
	const tree = fromMarkdown(markdown, { extensions: [gfm()], mdastExtensions: [gfmFromMarkdown()] });
	const out = [];
	const phrasing = new Set(['paragraph', 'heading', 'tableCell', 'emphasis', 'strong', 'delete', 'link', 'linkReference']);
	const visit = (node) => {
		if (node.type === 'text') for (const ch of node.value) out.push({ ch, literal: true });
		else if (node.type === 'inlineCode' || node.type === 'html') for (const ch of node.value) out.push({ ch, literal: false });
		else if (node.type === 'image' || node.type === 'imageReference') for (const ch of node.alt || '') out.push({ ch, literal: false });
		else if (node.type === 'break') out.push({ ch: ' ', literal: false });
		else if (node.type === 'footnoteReference') for (const ch of node.label || '') out.push({ ch, literal: false });
		else if (node.children) {
			node.children.forEach((child, index) => {
				if (index > 0 && !phrasing.has(node.type)) out.push({ ch: ' ', literal: false });
				visit(child);
			});
		}
	};
	visit(tree);
	return out;
}

// Re-parse a cut and check that what it shows is the start of what the source
// shows, and that every literal *, _, ~, [ or backtick in it was a literal
// character at the same place in the source.
function assertNoNewLiterals(text, limit) {
	const result = cutAtWord(text, limit);
	if (result === text) return;
	const context = `cutAtWord(${JSON.stringify(text)}, ${limit}) = ${JSON.stringify(result)}`;
	assert.ok(result.endsWith(' …'), context);
	const body = result.slice(0, -2);
	assert.ok(body.trim(), `${context}: empty cut`);
	const shown = shownCharacters(body);
	const original = shownCharacters(text);
	shown.forEach(({ ch, literal }, index) => {
		const at = original[index];
		assert.ok(at && at.ch === ch, `${context}: shows ${JSON.stringify(ch)} at ${index}, not a prefix of the source`);
		if (literal && MARKUP.has(ch)) {
			assert.ok(at.literal, `${context}: ${JSON.stringify(ch)} at ${index} is literal only after the cut`);
		}
	});
}
