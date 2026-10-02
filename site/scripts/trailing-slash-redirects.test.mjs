// SPDX-License-Identifier: MIT

// Unit tests for the trailing-slash redirect stubs written into the static
// export. Runs on Node's built-in test runner, like lib/search-index-core.test.mjs:
//
//   cd site && node --test scripts/trailing-slash-redirects.test.mjs
//
// The export serves `/docs/install` from `docs/install.html`; a static host
// answers `/docs/install/` from `docs/install/index.html`, which Next does not
// emit without `trailingSlash`. The stubs fill that gap with a redirect to the
// canonical URL, so a link or a hand-typed URL that ends in a slash still lands
// on the page.

import assert from 'node:assert/strict';
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { after, describe, it } from 'node:test';
import { redirectStubHtml, writeTrailingSlashRedirects } from './trailing-slash-redirects.mjs';

const SITE_URL = 'https://example.test';

function exportTree() {
	const root = mkdtempSync(join(tmpdir(), 'trailing-slash-'));
	const files = [
		'index.html',
		'404.html',
		'_not-found.html',
		'docs.html',
		'docs/install.html',
		'docs/install/quickstart.html',
		'ar.html',
		'ar/docs/install.html',
		'api/search/en',
	];
	for (const rel of files) {
		mkdirSync(join(root, rel, '..'), { recursive: true });
		writeFileSync(join(root, rel), `<html><body>${rel}</body></html>`);
	}
	return root;
}

const roots = [];
after(() => {
	for (const root of roots) rmSync(root, { recursive: true, force: true });
});

describe('writeTrailingSlashRedirects', () => {
	it('writes a stub for every page that has no directory index', () => {
		const root = exportTree();
		roots.push(root);
		const written = writeTrailingSlashRedirects(root, {
			siteUrl: SITE_URL,
			localeFor: (segment) => (segment === 'ar' ? { code: 'ar', dir: 'rtl' } : null),
		});
		assert.deepEqual(written.sort(), [
			'ar/docs/install/index.html',
			'ar/index.html',
			'docs/index.html',
			'docs/install/index.html',
			'docs/install/quickstart/index.html',
		]);
		const stub = readFileSync(join(root, 'docs/install/index.html'), 'utf8');
		assert.match(stub, /<link rel="canonical" href="https:\/\/example\.test\/docs\/install">/);
		assert.match(stub, /<meta http-equiv="refresh" content="0; url=\/docs\/install">/);
		assert.match(stub, /<meta name="robots" content="noindex">/);
	});

	it('leaves the root index, the 404 pages and non-HTML files alone', () => {
		const root = exportTree();
		roots.push(root);
		writeTrailingSlashRedirects(root, { siteUrl: SITE_URL, localeFor: () => null });
		assert.equal(readFileSync(join(root, 'index.html'), 'utf8'), '<html><body>index.html</body></html>');
		assert.equal(existsSync(join(root, '404/index.html')), false);
		assert.equal(existsSync(join(root, '_not-found/index.html')), false);
		assert.equal(existsSync(join(root, 'api/search/en/index.html')), false);
	});

	it('never overwrites an existing directory index', () => {
		const root = exportTree();
		roots.push(root);
		mkdirSync(join(root, 'docs'), { recursive: true });
		writeFileSync(join(root, 'docs/index.html'), 'authored');
		writeTrailingSlashRedirects(root, { siteUrl: SITE_URL, localeFor: () => null });
		assert.equal(readFileSync(join(root, 'docs/index.html'), 'utf8'), 'authored');
	});

	it('marks a locale stub with that locale', () => {
		const root = exportTree();
		roots.push(root);
		writeTrailingSlashRedirects(root, {
			siteUrl: SITE_URL,
			localeFor: (segment) => (segment === 'ar' ? { code: 'ar', dir: 'rtl' } : null),
		});
		const stub = readFileSync(join(root, 'ar/docs/install/index.html'), 'utf8');
		assert.match(stub, /<html lang="ar" dir="rtl">/);
		assert.match(stub, /url=\/ar\/docs\/install"/);
	});
});

describe('redirectStubHtml', () => {
	it('keeps the query and fragment when script runs, and escapes the target', () => {
		const html = redirectStubHtml('/docs/a"b', { siteUrl: SITE_URL, lang: 'en', dir: 'ltr' });
		assert.match(html, /location\.replace\("\/docs\/a\\"b" \+ location\.search \+ location\.hash\)/);
		assert.doesNotMatch(html, /href="\/docs\/a"b"/);
	});
});
