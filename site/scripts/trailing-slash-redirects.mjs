// SPDX-License-Identifier: MIT

// Trailing-slash redirect stubs for the static export.
//
// Next's static export (without `trailingSlash`) writes `/docs/install` as
// `docs/install.html`. A static host such as GitHub Pages serves that file for
// `/docs/install`, but answers `/docs/install/` from `docs/install/index.html`,
// which the export never writes, so every URL with a trailing slash returned
// 404. Turning `trailingSlash` on would move every page and every canonical,
// hreflang, sitemap and search URL, and the per-locale search route handlers
// along with them. This step leaves the export as built and adds one small stub
// per page instead: `docs/install/index.html` redirects to the canonical
// `/docs/install`, keeping the query string and fragment when script runs and
// falling back to a meta refresh without it. The stub names the canonical URL
// and is marked noindex, so search engines index only the real page.
//
// `export-to-dist.mjs` calls `writeTrailingSlashRedirects` after it bakes the
// per-locale `lang`/`dir` into the export; the stub carries the same values.

import { existsSync, mkdirSync, readdirSync, statSync, writeFileSync } from 'node:fs';
import { join, relative, sep } from 'node:path';

/** Escape a value for an HTML attribute or text node. */
function escapeHtml(value) {
	return value
		.replace(/&/g, '&amp;')
		.replace(/"/g, '&quot;')
		.replace(/</g, '&lt;')
		.replace(/>/g, '&gt;');
}

/**
 * The redirect page for one canonical path. `JSON.stringify` makes the script
 * literal safe, and `<` is escaped so the path can never close the script.
 */
export function redirectStubHtml(target, { siteUrl, lang, dir }) {
	const href = escapeHtml(target);
	const literal = JSON.stringify(target).replace(/</g, '\\u003c');
	return [
		'<!doctype html>',
		`<html lang="${escapeHtml(lang)}" dir="${escapeHtml(dir)}">`,
		'<head>',
		'<meta charset="utf-8">',
		`<title>${href}</title>`,
		'<meta name="robots" content="noindex">',
		`<link rel="canonical" href="${escapeHtml(siteUrl)}${href}">`,
		`<script>location.replace(${literal} + location.search + location.hash)</script>`,
		`<meta http-equiv="refresh" content="0; url=${href}">`,
		'</head>',
		`<body><p><a href="${href}">${href}</a></p></body>`,
		'</html>',
		'',
	].join('\n');
}

/** Recursively yield every `.html` file under `dir`. */
function* walkHtml(dir) {
	for (const entry of readdirSync(dir)) {
		const full = join(dir, entry);
		if (statSync(full).isDirectory()) {
			yield* walkHtml(full);
		} else if (entry.endsWith('.html')) {
			yield full;
		}
	}
}

/**
 * Write a `<page>/index.html` redirect stub for every exported `<page>.html`
 * that has none. Skips the root `index.html`, every nested `index.html`, the
 * error pages (`404.html` and Next's `_`-prefixed internals), and never
 * overwrites an existing file. `localeFor(firstSegment)` returns the locale's
 * `{ code, dir }`, or null for English at the site root.
 *
 * Returns the export-relative paths of the stubs written.
 */
export function writeTrailingSlashRedirects(serveDir, { siteUrl, localeFor }) {
	const written = [];
	const pages = [...walkHtml(serveDir)];
	for (const file of pages) {
		const rel = relative(serveDir, file).split(sep).join('/');
		const name = rel.split('/').pop();
		if (name === 'index.html' || name === '404.html' || name.startsWith('_')) continue;
		const route = rel.replace(/\.html$/, '');
		const stubRel = `${route}/index.html`;
		const stubPath = join(serveDir, ...stubRel.split('/'));
		if (existsSync(stubPath)) continue;
		const locale = localeFor(route.split('/')[0]);
		mkdirSync(join(serveDir, ...route.split('/')), { recursive: true });
		writeFileSync(
			stubPath,
			redirectStubHtml(`/${route}`, {
				siteUrl,
				lang: locale ? locale.code : 'en',
				dir: locale ? locale.dir : 'ltr',
			}),
		);
		written.push(stubRel);
	}
	return written;
}
