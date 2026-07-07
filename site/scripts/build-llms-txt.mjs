// SPDX-License-Identifier: MIT

// Build llms.txt and llms-full.txt for the apothem documentation site.
//
// Walks site/content/docs/**/*.{md,mdx}, then emits two artifacts into
// site/public/:
//   - llms.txt      — a compact, sectioned index of primary pages.
//   - llms-full.txt — the concatenated plain-text bodies of every doc page.
//
// Uses only Node built-ins (no new npm dependencies). Idempotent: each run
// overwrites the outputs from a fresh walk of the content tree.
//
// Run from the site/ directory:
//   node scripts/build-llms-txt.mjs

import { readdirSync, readFileSync, writeFileSync, mkdirSync, statSync } from 'node:fs';
import { join, dirname, relative, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

const SCRIPT_DIR = dirname(fileURLToPath(import.meta.url));
const SITE_ROOT = join(SCRIPT_DIR, '..');
const DOCS_ROOT = join(SITE_ROOT, 'content', 'docs');
const PUBLIC_DIR = join(SITE_ROOT, 'public');
const SITE_URL = 'https://apothem.ahmedgad.com';

// Primary top-level directories surfaced in the compact index, with a
// human-readable section heading for each. Pages outside these directories
// (and root-level singletons) are excluded from the compact index to keep
// llms.txt small; they remain in llms-full.txt.
const PRIMARY_SECTIONS = [
	['install', 'Getting started'],
	['concepts', 'Concepts'],
	['architecture', 'Architecture'],
	['reference', 'Reference'],
	['cli-reference', 'CLI reference'],
	['harnesses', 'Harnesses'],
];

// Per-locale content directories (one per non-default cohort locale, e.g.
// `es`) hold translated copies of the English pages. The llms.txt /
// llms-full.txt artifacts are an English-only index, so the locale subtrees
// are skipped at the docs root — including them would duplicate every page in
// the target language. Mirrors the kebab-cased `path` values declared for the
// cohort in `lib/i18n.ts`; assertLocaleParity() below fails the build if this
// literal drifts from that source of truth, so a newly-routed locale cannot
// silently leak its translated pages into the English-only artifacts.
const LOCALE_CONTENT_DIRS = new Set([
	'zh-cn',
	'es',
	'pt-br',
	'fr',
	'de',
	'ja',
	'ko',
	'ru',
	'id',
	'ar',
	'hi',
]);

// The default (source) locale, served at the site root with no path prefix —
// its content lives at the docs root, not in a locale subtree, so it is never
// a LOCALE_CONTENT_DIRS entry. Kept in sync with DEFAULT_LOCALE in lib/i18n.ts.
const DEFAULT_LOCALE = 'en';

/**
 * Re-derive the routed-locale set from `lib/i18n.ts` and assert its non-default
 * members equal LOCALE_CONTENT_DIRS. This binds the script to the single i18n
 * source of truth (the same pattern check-search-index-sizes.mjs and
 * export-to-dist.mjs use): adding or removing a routed locale in `lib/i18n.ts`
 * without updating this literal fails fast here rather than silently walking the
 * new locale's translated tree into the English-only llms.txt / llms-full.txt.
 */
function assertLocaleParity() {
	const src = readFileSync(join(SITE_ROOT, 'lib', 'i18n.ts'), 'utf8');
	const match = src.match(/export const ROUTED_LOCALES[^=]*=\s*\[([^\]]*)\]/);
	if (!match) {
		throw new Error(
			'build-llms-txt: could not parse ROUTED_LOCALES from lib/i18n.ts',
		);
	}
	const routedNonDefault = [...match[1].matchAll(/'([^']+)'/g)]
		.map((m) => m[1])
		.filter((code) => code !== DEFAULT_LOCALE);
	const declaredSet = LOCALE_CONTENT_DIRS;
	const routedSet = new Set(routedNonDefault);
	const missing = routedNonDefault.filter((l) => !declaredSet.has(l));
	const extra = [...declaredSet].filter((l) => !routedSet.has(l));
	if (missing.length || extra.length) {
		throw new Error(
			'build-llms-txt: LOCALE_CONTENT_DIRS drifted from lib/i18n.ts. ' +
				`In i18n but not in this script: [${missing.join(', ')}]. ` +
				`In this script but not in i18n: [${extra.join(', ')}].`,
		);
	}
}

/** Recursively collect every .md / .mdx file under a directory. */
function walk(dir, depth = 0) {
	const out = [];
	for (const entry of readdirSync(dir, { withFileTypes: true })) {
		// Skip locale content directories at the docs root (depth 0): the llms
		// artifacts index the English source only.
		if (depth === 0 && entry.isDirectory() && LOCALE_CONTENT_DIRS.has(entry.name)) {
			continue;
		}
		// Skip the 404 page at the docs root — a render-time fallback, not an
		// indexable content page.
		if (depth === 0 && entry.isFile() && /^404\.(md|mdx)$/i.test(entry.name)) {
			continue;
		}
		const full = join(dir, entry.name);
		if (entry.isDirectory()) {
			out.push(...walk(full, depth + 1));
		} else if (entry.isFile() && /\.(md|mdx)$/i.test(entry.name)) {
			out.push(full);
		}
	}
	return out.sort();
}

/** Split a doc file into { frontmatter: {title, description}, body }. */
function parseDoc(raw) {
	let text = raw.replace(/^﻿/, '');
	const fm = { title: '', description: '' };
	const fmMatch = text.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n?/);
	if (fmMatch) {
		for (const line of fmMatch[1].split(/\r?\n/)) {
			const kv = line.match(/^(\w[\w-]*):\s*(.*)$/);
			if (!kv) continue;
			const key = kv[1].toLowerCase();
			if (['title', 'description'].includes(key)) {
				fm[key] = unquote(kv[2].trim());
			}
		}
		text = text.slice(fmMatch[0].length);
	}
	// Strip a leading SPDX banner if present, in either the Markdown HTML-comment
	// form (`<!-- ... -->`) or the MDX expression-comment form (`{/* ... */}`)
	// that MDX content pages carry.
	text = text.replace(/^\s*<!--[\s\S]*?-->\s*/, '');
	text = text.replace(/^\s*\{\/\*[\s\S]*?\*\/\}\s*/, '');
	return { frontmatter: fm, body: text.trim() };
}

function unquote(v) {
	if (
		(v.startsWith('"') && v.endsWith('"')) ||
		(v.startsWith("'") && v.endsWith("'"))
	) {
		return v.slice(1, -1);
	}
	return v;
}

/** Map an absolute doc path to its public Fumadocs docs URL (under /docs/). */
function toUrl(absPath) {
	let rel = relative(DOCS_ROOT, absPath).split(sep).join('/');
	rel = rel.replace(/\.(md|mdx)$/i, '');
	if (rel.endsWith('/index')) rel = rel.slice(0, -'/index'.length);
	if (rel === 'index') rel = '';
	return rel ? `${SITE_URL}/docs/${rel}/` : `${SITE_URL}/docs/`;
}

/** Top-level directory segment of a doc path, or '' for root singletons. */
function topSegment(absPath) {
	const rel = relative(DOCS_ROOT, absPath).split(sep);
	return rel.length > 1 ? rel[0] : '';
}

function plainTextBody(body) {
	// Remove fenced code blocks and reduce remaining lines to plain prose.
	return body
		.replace(/```[\s\S]*?```/g, '')
		.replace(/^import\s.*$/gm, '')
		.replace(/[ \t]+$/gm, '')
		.replace(/\n{3,}/g, '\n\n')
		.trim();
}

function main() {
	assertLocaleParity();
	const files = walk(DOCS_ROOT);
	const docs = files.map((f) => {
		const { frontmatter, body } = parseDoc(readFileSync(f, 'utf8'));
		return {
			path: f,
			url: toUrl(f),
			top: topSegment(f),
			title: frontmatter.title || frontmatter.description || basenameTitle(f),
			description: frontmatter.description || '',
			body,
		};
	});

	mkdirSync(PUBLIC_DIR, { recursive: true });

	// --- llms.txt (compact, sectioned index of primary pages) ---
	const compact = [];
	compact.push('# apothem');
	compact.push('');
	// The llmstxt.org format expects the summary as a blockquote immediately
	// after the H1.
	compact.push(
		'> apothem is a host-agnostic AI-harness configuration manager. It reads ' +
			'one shared profile and materializes harness-native configuration for ' +
			'Claude Code, Cursor, Gemini CLI, GitHub Copilot, and every other ' +
			'registered adapter. This file indexes the primary documentation pages.',
	);
	compact.push('');
	for (const [dir, heading] of PRIMARY_SECTIONS) {
		const pages = docs.filter((d) => d.top === dir);
		if (pages.length === 0) continue;
		compact.push(`## ${heading}`);
		compact.push('');
		for (const d of pages) {
			const desc = d.description ? `: ${d.description}` : '';
			compact.push(`- [${d.title}](${d.url})${desc}`);
		}
		compact.push('');
	}
	writeFileSync(join(PUBLIC_DIR, 'llms.txt'), `${compact.join('\n').trim()}\n`, 'utf8');

	// --- llms-full.txt (deep, concatenated plain-text bodies) ---
	const full = [];
	for (const d of docs) {
		const text = plainTextBody(d.body);
		if (!text) continue;
		full.push(`# ${d.title}`);
		full.push(`URL: ${d.url}`);
		if (d.description) full.push(d.description);
		full.push('');
		full.push(text);
		full.push('');
	}
	writeFileSync(
		join(PUBLIC_DIR, 'llms-full.txt'),
		`${full.join('\n').trim()}\n`,
		'utf8',
	);

	const sizeOf = (name) => statSync(join(PUBLIC_DIR, name)).size;
	process.stdout.write(
		`Wrote public/llms.txt (${sizeOf('llms.txt')} bytes) and ` +
			`public/llms-full.txt (${sizeOf('llms-full.txt')} bytes) ` +
			`from ${docs.length} pages.\n`,
	);
}

function basenameTitle(absPath) {
	const base = absPath.split(sep).pop().replace(/\.(md|mdx)$/i, '');
	return base.replace(/[-_]/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

main();
