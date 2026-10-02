// SPDX-License-Identifier: MIT

// Unit tests for the translation source hash that drives the staleness marker
// on locale pages. Run:
//
//   cd site && node --test lib/translation-source.test.mjs
//
// A locale page records, in its `sourceHash` frontmatter, the hash of the
// English page it was translated from. The hash must change when the English
// prose changes and must not change when only a generated block changes,
// because the reference generator rewrites those blocks in every locale copy
// at once.

import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { sourceHash, translatableText } from './translation-source.mjs';

const START = '{/* apothem:generated-reference:start */}';
const END = '{/* apothem:generated-reference:end */}';

function page(prose, table) {
	return `---\ntitle: "Install"\n---\n${prose}\n\n${START}\n\n${table}\n\n${END}\n`;
}

describe('sourceHash', () => {
	it('is 16 lower-case hex characters', () => {
		assert.match(sourceHash(page('Run the installer.', '| a |')), /^[0-9a-f]{16}$/);
	});

	it('changes when the English prose changes', () => {
		assert.notEqual(
			sourceHash(page('Run the installer.', '| a |')),
			sourceHash(page('Run the installer twice.', '| a |')),
		);
	});

	it('changes when the English title changes', () => {
		const a = page('Same prose.', '| a |');
		assert.notEqual(sourceHash(a), sourceHash(a.replace('"Install"', '"Installing"')));
	});

	it('ignores a change confined to a generated block', () => {
		assert.equal(
			sourceHash(page('Run the installer.', '| a |')),
			sourceHash(page('Run the installer.', '| a |\n| b |')),
		);
	});

	it('ignores line-ending and trailing-space differences', () => {
		const unix = page('Run the installer.', '| a |');
		const windows = unix.replace(/\n/g, '  \r\n');
		assert.equal(sourceHash(unix), sourceHash(windows));
	});
});

describe('translatableText', () => {
	it('keeps the markers and drops only what sits between them', () => {
		const text = translatableText(page('Prose.', '| generated |'));
		assert.ok(text.includes(START));
		assert.ok(text.includes(END));
		assert.ok(!text.includes('| generated |'));
		assert.ok(text.includes('Prose.'));
	});

	it('drops the changelog block too', () => {
		const text = translatableText(
			'Intro.\n{/* apothem:changelog:start */}\n## 1.0.0\n{/* apothem:changelog:end */}\n',
		);
		assert.ok(!text.includes('## 1.0.0'));
	});
});
