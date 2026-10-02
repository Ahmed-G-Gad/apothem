// SPDX-License-Identifier: MIT

// Report and record which English text each locale page was translated from.
//
// Every page under content/docs/<locale>/ records `sourceHash` in its
// frontmatter (see lib/translation-source.mjs). The docs route shows a
// staleness marker on a locale page whose recorded hash no longer matches its
// English page. This script is the maintainer side:
//
//   node scripts/translation-sources.mjs
//       Report, per locale, how many pages are current, stale, or unrecorded,
//       and list the stale ones. Exits 1 when a locale page has no (or a
//       malformed) sourceHash or no English page, 0 otherwise: a stale
//       translation is reported and marked on the page, never a build failure.
//
//   node scripts/translation-sources.mjs --stamp ja/install/index.mdx [...]
//       Record the current English hash on the named locale pages, after their
//       translation has been brought up to date.
//
//   node scripts/translation-sources.mjs --seed
//       For each locale page with no sourceHash, recover the English text it
//       was translated from out of git history and record that hash. The
//       translation's commit is the oldest commit in the unbroken run, newest
//       first, whose translatable text equals the page's current text, so a
//       later change confined to a generated block does not count as a
//       re-translation. Needs the repository history; run it from a full clone.

import { spawnSync } from 'node:child_process';
import { readFileSync, readdirSync, statSync, writeFileSync } from 'node:fs';
import { dirname, join, relative, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { sourceHash, translatableText } from '../lib/translation-source.mjs';

const SCRIPT_DIR = dirname(fileURLToPath(import.meta.url));
const SITE_ROOT = join(SCRIPT_DIR, '..');
const REPO_ROOT = join(SITE_ROOT, '..');
const DOCS_ROOT = join(SITE_ROOT, 'content', 'docs');
const HASH_LINE = /^sourceHash:.*$/m;
const HASH_VALUE = /^sourceHash: "?([0-9a-f]{16})"?$/m;

// Locale content roots, re-derived from lib/i18n.ts like the sibling scripts so
// a newly routed locale is covered without editing this file.
function routedLocales() {
	const src = readFileSync(join(SITE_ROOT, 'lib', 'i18n.ts'), 'utf8');
	const match = src.match(/ROUTED_LOCALES[^=]*=\s*\[([^\]]*)\]/);
	if (!match) throw new Error('translation-sources: could not parse ROUTED_LOCALES from lib/i18n.ts');
	return [...match[1].matchAll(/'([^']+)'/g)].map((m) => m[1]).filter((code) => code !== 'en');
}

function walk(dir) {
	const out = [];
	for (const entry of readdirSync(dir)) {
		const full = join(dir, entry);
		if (statSync(full).isDirectory()) out.push(...walk(full));
		else if (/\.mdx?$/.test(entry)) out.push(full);
	}
	return out.sort();
}

/** `{ locale, rel, path, english }` for every locale page; `rel` is locale-relative. */
function localePages() {
	const pages = [];
	for (const locale of routedLocales()) {
		const root = join(DOCS_ROOT, locale);
		let files = [];
		try {
			files = walk(root);
		} catch {
			continue;
		}
		for (const path of files) {
			const rel = relative(root, path).split(sep).join('/');
			pages.push({ locale, rel, path, english: join(DOCS_ROOT, ...rel.split('/')) });
		}
	}
	return pages;
}

function readOrNull(path) {
	try {
		return readFileSync(path, 'utf8');
	} catch {
		return null;
	}
}

function recordedHash(text) {
	const frontmatter = text.match(/^---\n([\s\S]*?)\n---\n/);
	if (!frontmatter) return null;
	const value = frontmatter[1].match(HASH_VALUE);
	return value ? value[1] : null;
}

function writeHash(path, hash) {
	const text = readFileSync(path, 'utf8');
	const frontmatter = text.match(/^---\n([\s\S]*?)\n---\n/);
	if (!frontmatter) throw new Error(`translation-sources: ${path} has no frontmatter`);
	const line = `sourceHash: "${hash}"`;
	const body = HASH_LINE.test(frontmatter[1])
		? frontmatter[1].replace(HASH_LINE, line)
		: `${frontmatter[1]}\n${line}`;
	writeFileSync(path, `---\n${body}\n---\n${text.slice(frontmatter[0].length)}`, 'utf8');
}

function withoutHash(text) {
	return translatableText(text.replace(/^sourceHash:.*\n/m, ''));
}

function git(args) {
	const result = spawnSync('git', args, { cwd: REPO_ROOT, encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 });
	return result.status === 0 ? result.stdout : null;
}

function repoPath(path) {
	return relative(REPO_ROOT, path).split(sep).join('/');
}

// The English text a locale page was translated from, recovered from history.
function englishAtTranslation(page) {
	const localeRepoPath = repoPath(page.path);
	const commits = (git(['log', '--format=%H', '--', localeRepoPath]) || '').split('\n').filter(Boolean);
	if (commits.length === 0) return null;
	const current = withoutHash(readFileSync(page.path, 'utf8'));
	let translated = commits[0];
	for (const commit of commits.slice(1)) {
		const then = git(['show', `${commit}:${localeRepoPath}`]);
		if (then === null || withoutHash(then) !== current) break;
		translated = commit;
	}
	return git(['show', `${translated}:${repoPath(page.english)}`]) ?? '';
}

function report() {
	const counts = new Map();
	const stale = [];
	const problems = [];
	for (const page of localePages()) {
		const tally = counts.get(page.locale) ?? { current: 0, stale: 0, unrecorded: 0 };
		counts.set(page.locale, tally);
		const english = readOrNull(page.english);
		const recorded = recordedHash(readFileSync(page.path, 'utf8'));
		if (english === null) {
			problems.push(`${page.locale}/${page.rel}: no English page`);
		} else if (recorded === null) {
			tally.unrecorded += 1;
			problems.push(`${page.locale}/${page.rel}: no sourceHash`);
		} else if (recorded === sourceHash(english)) {
			tally.current += 1;
		} else {
			tally.stale += 1;
			stale.push(`${page.locale}/${page.rel}`);
		}
	}
	for (const [locale, tally] of counts) {
		console.log(`${locale}: ${tally.current} current, ${tally.stale} stale, ${tally.unrecorded} unrecorded`);
	}
	const totalStale = stale.length;
	console.log(`stale locale pages: ${totalStale}`);
	for (const entry of stale) console.log(`  stale ${entry}`);
	for (const entry of problems) console.error(`  error ${entry}`);
	return problems.length > 0 ? 1 : 0;
}

function stamp(targets) {
	for (const target of targets) {
		const [locale, ...rest] = target.split('/');
		const path = join(DOCS_ROOT, locale, ...rest);
		const english = readFileSync(join(DOCS_ROOT, ...rest), 'utf8');
		writeHash(path, sourceHash(english));
		console.log(`stamped ${target}`);
	}
	return 0;
}

function seed() {
	let seeded = 0;
	let unknown = 0;
	for (const page of localePages()) {
		if (recordedHash(readFileSync(page.path, 'utf8')) !== null) continue;
		const english = englishAtTranslation(page);
		if (english === null) {
			unknown += 1;
			console.error(`  no history for ${page.locale}/${page.rel}; left unrecorded`);
			continue;
		}
		writeHash(page.path, sourceHash(english));
		seeded += 1;
	}
	console.log(`seeded ${seeded} locale pages from git history; ${unknown} without history`);
	return unknown > 0 ? 1 : 0;
}

const args = process.argv.slice(2);
let code;
if (args[0] === '--stamp') code = stamp(args.slice(1));
else if (args[0] === '--seed') code = seed();
else code = report();
process.exit(code);
