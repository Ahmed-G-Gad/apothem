// SPDX-License-Identifier: MIT

// Move the Next.js static export from `out/` to `dist/`, then bake the correct
// per-locale `lang`/`dir` into each emitted `<html>` tag.
//
// `next build` with `output: 'export'` writes the rendered static bundle to
// `out/`. The Pages publish pipeline (and the repo's generated-state
// conventions) serve `dist/`, so this postbuild step renames the export into
// place. Idempotent: a stale `dist/` is removed first, and a missing `out/`
// (for example after `next dev`, which does not export) is a no-op.
//
// The site is a single-root-layout static export, so Next renders `<html>` once
// (in `app/layout.tsx`) with the source-locale default `lang="en" dir="ltr"`
// for every page. A per-locale `lang`/`dir` cannot be expressed from that
// shared root layout at render time. This step closes that gap at the static
// surface: it walks the emitted HTML, maps each file's leading path segment to
// a cohort locale, and rewrites the `<html>` tag's `lang`/`dir` attributes to
// the locale's BCP-47 code and text direction — so `dist/ar/...` files carry
// `lang="ar" dir="rtl"` and every LTR locale (and English at the root) keeps
// `dir="ltr"`. The locale → (code, dir) table is projected from the single
// i18n source of truth so this step never diverges from `lib/i18n.ts`.
//
// Last, it writes a redirect stub at `<page>/index.html` for every exported
// `<page>.html`, so a URL with a trailing slash reaches the page rather than a
// 404 (see `trailing-slash-redirects.mjs`).

import {
  existsSync,
  readdirSync,
  readFileSync,
  renameSync,
  rmSync,
  statSync,
  writeFileSync,
} from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { writeTrailingSlashRedirects } from './trailing-slash-redirects.mjs';

// Anchor the build directories to the site root (the script's parent-of-parent),
// not the caller's cwd, so the rename resolves the same `out/` and `dist/`
// regardless of where the postbuild step is invoked from — matching the
// SCRIPT_DIR anchoring the sibling site scripts use.
const SCRIPT_DIR = dirname(fileURLToPath(import.meta.url));
const SITE_ROOT = join(SCRIPT_DIR, '..');
const EXPORT_NAME = 'out';
const SERVE_NAME = 'dist';
const EXPORT_DIR = join(SITE_ROOT, EXPORT_NAME);
const SERVE_DIR = join(SITE_ROOT, SERVE_NAME);

if (!existsSync(EXPORT_DIR)) {
  console.log(`No ${EXPORT_NAME}/ directory; nothing to move.`);
  process.exit(0);
}

rmSync(SERVE_DIR, { recursive: true, force: true });
renameSync(EXPORT_DIR, SERVE_DIR);
console.log(`Moved static export ${EXPORT_NAME}/ -> ${SERVE_NAME}/.`);

// Load the cohort table from the i18n source of truth. A plain Node script
// cannot import the TS module directly (no TS loader on the build path), so the
// locale → direction map is derived by reading `lib/i18n.ts` and extracting each
// cohort entry's code/path/dir fields from the source text. The parse is
// property-order-independent and asserts completeness against ROUTED_LOCALES, so
// a partial or reordered source can never ship a wrong or missing lang/dir.
const PATH_TO_LOCALE = loadLocaleDirMap();

let rewritten = 0;
for (const file of walkHtml(SERVE_DIR)) {
  // The path segment immediately under dist/ identifies the locale subtree.
  // With no `trailingSlash`, Next emits a localized landing as a top-level
  // sibling file (`dist/es.html`) rather than `dist/es/index.html`, so the
  // first path segment is `es.html` for the landing and `es` for its docs
  // pages. Strip a trailing `.html` so both forms resolve to the locale key
  // (`es.html` -> `es`; `es/docs.html` -> `es` is unaffected). Without this,
  // every localized landing kept the root layout's default `lang="en"
  // dir="ltr"` — rendering the Arabic landing LTR for crawlers and no-JS.
  const rel = file.slice(SERVE_DIR.length + 1).replace(/\\/g, '/');
  const seg = rel.split('/')[0].replace(/\.html$/, '');
  const locale = PATH_TO_LOCALE.get(seg);
  // Files outside a routed-locale subtree are English (served at the root) and
  // keep the default `lang="en" dir="ltr"` already baked by the root layout.
  if (!locale) continue;

  const html = readFileSync(file, 'utf8');
  const patched = html.replace(
    /<html\b([^>]*)>/i,
    (_match, attrs) =>
      `<html${setAttr(setAttr(attrs, 'lang', locale.code), 'dir', locale.dir)}>`,
  );
  if (patched !== html) {
    writeFileSync(file, patched);
    rewritten += 1;
  }
}
console.log(`Baked per-locale lang/dir into ${rewritten} localized HTML file(s).`);

// A static host answers `/docs/install/` from `docs/install/index.html`, which
// the export does not write; add a redirect stub per page so URLs with a
// trailing slash reach the page instead of a 404 (see trailing-slash-redirects.mjs).
const stubs = writeTrailingSlashRedirects(SERVE_DIR, {
  siteUrl: loadSiteUrl(),
  localeFor: (segment) => PATH_TO_LOCALE.get(segment) ?? null,
});
console.log(`Wrote ${stubs.length} trailing-slash redirect stub(s).`);

/** Read the canonical site URL from `lib/i18n.ts`, the single source for it. */
function loadSiteUrl() {
  const src = readFileSync(new URL('../lib/i18n.ts', import.meta.url), 'utf8');
  const match = src.match(/export const SITE_URL = '([^']+)'/);
  if (!match) {
    throw new Error('export-to-dist: could not parse SITE_URL from lib/i18n.ts');
  }
  return match[1];
}

/** Replace (or insert) a single attribute inside an `<html ...>` attribute run. */
function setAttr(attrs, name, value) {
  const re = new RegExp(`\\s${name}="[^"]*"`, 'i');
  const next = ` ${name}="${value}"`;
  return re.test(attrs) ? attrs.replace(re, next) : `${attrs}${next}`;
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
 * Build a `path-segment -> { code, dir }` map for every non-default cohort
 * locale. Reads the cohort declaration from `lib/i18n.ts` so the map stays in
 * lock-step with the single i18n source of truth.
 *
 * The per-entry parse is property-order-independent: each cohort object is
 * isolated by its brace span, then `code`, `path`, and `dir` are extracted from
 * that span in any order. A reordered source (`dir` before `code`, say) can no
 * longer drop a locale or ship a wrong direction. After parsing, the map is
 * asserted complete against ROUTED_LOCALES — every routed non-default locale
 * MUST have produced an entry — so a partial parse fails loudly at build time
 * instead of silently baking `lang="en" dir="ltr"` onto an unmatched locale.
 */
function loadLocaleDirMap() {
  const map = new Map();
  const src = readFileSync(new URL('../lib/i18n.ts', import.meta.url), 'utf8');
  // Isolate each cohort object literal `{ … }`, then pull code/path/dir from the
  // span independent of the property order within it.
  for (const [objBody] of src.matchAll(/\{([^{}]*)\}/g)) {
    const code = objBody.match(/\bcode:\s*'([^']*)'/);
    const path = objBody.match(/\bpath:\s*'([^']*)'/);
    const dir = objBody.match(/\bdir:\s*'(ltr|rtl)'/);
    if (!code || !path || !dir) continue;
    // The default locale carries an empty path (served at the root); it needs no
    // rewrite, so only non-default cohort entries are mapped.
    if (path[1]) map.set(path[1], { code: code[1], dir: dir[1] });
  }
  if (map.size === 0) {
    throw new Error('export-to-dist: no cohort locales parsed from lib/i18n.ts');
  }
  assertRoutedLocalesComplete(map, src);
  return map;
}

/**
 * Assert every routed non-default locale produced a `{ code, dir }` entry.
 * ROUTED_LOCALES is the site's live-routing source of truth; a routed locale
 * whose cohort object failed to parse would otherwise fall through to the
 * root layout's default `lang="en" dir="ltr"`, silently mis-rendering that
 * locale's static pages. Parsing both sets from the same file keeps the check
 * bound to the single i18n source.
 */
function assertRoutedLocalesComplete(map, src) {
  const routedMatch = src.match(/ROUTED_LOCALES[^=]*=\s*\[([^\]]*)\]/);
  if (!routedMatch) {
    throw new Error(
      'export-to-dist: could not parse ROUTED_LOCALES from lib/i18n.ts',
    );
  }
  const routed = [...routedMatch[1].matchAll(/'([^']+)'/g)].map((m) => m[1]);
  // `en` is the default locale served at the root with no path prefix, so it is
  // never a map key; every other routed locale must be present.
  const missing = routed.filter((locale) => locale !== 'en' && !map.has(locale));
  if (missing.length > 0) {
    throw new Error(
      'export-to-dist: routed locales missing from the parsed cohort table ' +
        `(partial i18n.ts parse): [${missing.join(', ')}]. Every ROUTED_LOCALE ` +
        'must resolve to a { code, dir } entry before the static export ships.',
    );
  }
}
