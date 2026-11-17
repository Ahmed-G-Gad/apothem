// SPDX-License-Identifier: MIT

// Redirect stubs for docs pages the site no longer has.
//
// The site is a static export with no server-side redirects, so a removed
// page's URL would answer 404. For each entry in MOVED_PAGES this step writes a
// stub at the old URL, in English and in every locale, that sends the reader to
// the page that replaces it in the same language. It writes both
// `<old>.html` (for `/docs/old`) and `<old>/index.html` (for `/docs/old/`), and
// never overwrites a page the export built.
//
// `export-to-dist.mjs` calls `writeMovedPageRedirects` before the trailing-slash
// stubs, using the same stub page (see `trailing-slash-redirects.mjs`).

import { existsSync, mkdirSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { redirectStubHtml } from './trailing-slash-redirects.mjs';

/** Old route -> route of the page that replaces it, both without the locale. */
export const MOVED_PAGES = {
	'docs/blog/posts/v1-0-1-release': 'docs/blog',
};

/**
 * Write the stubs for `moves` under `serveDir`. `locales` maps each locale's
 * path segment to its `{ code, dir }`; English is written at the root.
 *
 * Returns the export-relative paths of the stubs written.
 */
export function writeMovedPageRedirects(serveDir, { siteUrl, locales, moves = MOVED_PAGES }) {
	const written = [];
	const prefixes = [['', { code: 'en', dir: 'ltr' }], ...locales];
	for (const [from, to] of Object.entries(moves)) {
		for (const [segment, locale] of prefixes) {
			const base = segment ? `${segment}/` : '';
			const target = `/${base}${to}`;
			const html = redirectStubHtml(target, { siteUrl, lang: locale.code, dir: locale.dir });
			for (const rel of [`${base}${from}.html`, `${base}${from}/index.html`]) {
				const file = join(serveDir, ...rel.split('/'));
				if (existsSync(file)) continue;
				mkdirSync(dirname(file), { recursive: true });
				writeFileSync(file, html);
				written.push(rel);
			}
		}
	}
	return written;
}
