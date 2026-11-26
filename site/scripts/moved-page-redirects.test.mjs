// SPDX-License-Identifier: MIT

// Unit tests for the redirect stubs written at the URLs of removed docs pages.
//
//   cd site && node --test scripts/moved-page-redirects.test.mjs

import assert from 'node:assert/strict';
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { after, describe, it } from 'node:test';
import { MOVED_PAGES, writeMovedPageRedirects } from './moved-page-redirects.mjs';

const SITE_URL = 'https://example.test';
const LOCALES = new Map([['ar', { code: 'ar', dir: 'rtl' }]]);
const MOVES = { 'docs/blog/posts/old': 'docs/blog' };

const roots = [];
after(() => {
	for (const root of roots) rmSync(root, { recursive: true, force: true });
});

function emptyExport() {
	const root = mkdtempSync(join(tmpdir(), 'moved-pages-'));
	roots.push(root);
	return root;
}

describe('writeMovedPageRedirects', () => {
	it('writes both URL forms in English and in each locale', () => {
		const root = emptyExport();
		const written = writeMovedPageRedirects(root, {
			siteUrl: SITE_URL,
			locales: LOCALES,
			moves: MOVES,
		});
		assert.deepEqual(written.sort(), [
			'ar/docs/blog/posts/old.html',
			'ar/docs/blog/posts/old/index.html',
			'docs/blog/posts/old.html',
			'docs/blog/posts/old/index.html',
		]);
		const english = readFileSync(join(root, 'docs/blog/posts/old.html'), 'utf8');
		assert.match(english, /<meta http-equiv="refresh" content="0; url=\/docs\/blog">/);
		assert.match(english, /<html lang="en" dir="ltr">/);
		const arabic = readFileSync(join(root, 'ar/docs/blog/posts/old/index.html'), 'utf8');
		assert.match(arabic, /url=\/ar\/docs\/blog"/);
		assert.match(arabic, /<html lang="ar" dir="rtl">/);
	});

	it('never overwrites a page the export built', () => {
		const root = emptyExport();
		mkdirSync(join(root, 'docs/blog/posts'), { recursive: true });
		writeFileSync(join(root, 'docs/blog/posts/old.html'), 'built');
		writeMovedPageRedirects(root, { siteUrl: SITE_URL, locales: new Map(), moves: MOVES });
		assert.equal(readFileSync(join(root, 'docs/blog/posts/old.html'), 'utf8'), 'built');
	});

	it('sends every moved page to a docs route', () => {
		for (const [from, to] of Object.entries(MOVED_PAGES)) {
			assert.match(from, /^docs\//);
			assert.match(to, /^docs(\/|$)/);
		}
	});
});
