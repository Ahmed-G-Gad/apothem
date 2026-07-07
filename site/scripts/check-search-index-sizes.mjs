// SPDX-License-Identifier: MIT

// Post-build guard for the per-locale static search indices.
//
// Search was refactored from a single combined Orama index — which grew past
// GitHub Pages' hard 100 MB per-file limit, so the CDN silently refused to
// serve it and client-side search failed outright — to one single-locale index
// per routed locale, emitted at `dist/api/search/<locale>` by the route
// handler's `generateStaticParams` (see `app/api/search/[locale]/route.ts`).
//
// This script is the durable guarantee that the refactor stays correct across
// every future build. It scans the static export and asserts, for all twelve
// routed cohort locales:
//
//   1. PRESENCE  — the per-locale index file exists (a locale dropped from
//                  `generateStaticParams`, or a build that failed to emit one,
//                  is caught here rather than shipping a locale with no search).
//   2. NON-EMPTY — the index is larger than a small floor (a zero-byte or
//                  truncated emission is a silent search break).
//   3. UNDER CAP — the index is strictly below the GitHub Pages 100 MB
//                  per-file limit (the exact failure mode the refactor exists
//                  to prevent — regression-guarded here, not just in review).
//
// It is wired into the Static Site workflow after `npm run build`. Exit code 0
// means every locale's index is present, non-empty, and under the cap; any
// violation prints a per-locale report and exits non-zero, failing the deploy
// before a broken-search bundle reaches the CDN.
//
// Run standalone (after a local `npm run build`):
//   node scripts/check-search-index-sizes.mjs
// Override the scanned build directory (defaults to `dist`, the served tree;
// falls back to `out` when `dist` is absent, e.g. a build whose postbuild
// rename has not run):
//   SEARCH_INDEX_DIR=out node scripts/check-search-index-sizes.mjs

import { existsSync, readFileSync, statSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

// Anchor to the script's own location so the build directory resolves the same
// regardless of the caller's cwd, matching the sibling site scripts. The
// SEARCH_INDEX_DIR override is honored as-is (absolute or cwd-relative, the
// operator's choice); the default `dist`/`out` fallbacks resolve under the site
// root rather than the current directory.
const SCRIPT_DIR = dirname(fileURLToPath(import.meta.url));
const SITE_ROOT = join(SCRIPT_DIR, '..');

/**
 * GitHub Pages' hard per-file size limit. A file at or above this is rejected
 * by the CDN and served as a 404/error, silently breaking the feature that
 * depends on it. The search refactor exists to keep every emitted index below
 * this line; the check is strict (`>=` fails) so an index that exactly reaches
 * the cap is still treated as a violation.
 * Reference: GitHub Pages usage limits — 100 MB per file.
 */
const GITHUB_PAGES_MAX_BYTES = 100 * 1024 * 1024;

/**
 * A search index smaller than this almost certainly failed to build (a
 * zero-byte emission, or a stub with no documents). A real single-locale index
 * over the Apothem docs tree is multiple megabytes; 1 KB is a generous floor
 * that only an empty/truncated index falls below.
 */
const MIN_INDEX_BYTES = 1024;

/**
 * The twelve routed cohort locales, mirrored from `lib/i18n.ts`'s
 * `ROUTED_LOCALES`. Kept as a literal (rather than imported from the TS source)
 * so this plain-Node script runs without a TS loader; the parity check below
 * re-derives the set from `lib/i18n.ts` and fails on any drift, so the literal
 * cannot silently fall out of sync with the source of truth.
 */
const EXPECTED_LOCALES = [
  'en',
  'es',
  'zh-cn',
  'pt-br',
  'fr',
  'de',
  'ja',
  'ko',
  'ru',
  'id',
  'hi',
  'ar',
];

/**
 * Re-derive the routed-locale set from `lib/i18n.ts` and assert it equals
 * EXPECTED_LOCALES. This binds the script to the single i18n source of truth:
 * adding or removing a routed locale in `lib/i18n.ts` without updating this
 * script (or vice versa) fails fast here rather than letting the size check
 * silently skip a newly-routed locale.
 */
function assertLocaleParity() {
  const src = readFileSync(new URL('../lib/i18n.ts', import.meta.url), 'utf8');
  const match = src.match(
    /export const ROUTED_LOCALES[^=]*=\s*\[([^\]]*)\]/,
  );
  if (!match) {
    throw new Error(
      'check-search-index-sizes: could not parse ROUTED_LOCALES from lib/i18n.ts',
    );
  }
  const routed = [...match[1].matchAll(/'([^']+)'/g)].map((m) => m[1]);
  const expectedSet = new Set(EXPECTED_LOCALES);
  const routedSet = new Set(routed);
  const missing = routed.filter((l) => !expectedSet.has(l));
  const extra = EXPECTED_LOCALES.filter((l) => !routedSet.has(l));
  if (missing.length || extra.length) {
    throw new Error(
      'check-search-index-sizes: routed-locale set drifted from lib/i18n.ts. ' +
        `In i18n but not in this script: [${missing.join(', ')}]. ` +
        `In this script but not in i18n: [${extra.join(', ')}].`,
    );
  }
}

/** Resolve the build-output directory to scan (`dist` preferred, then `out`). */
function resolveBuildDir() {
  const override = process.env.SEARCH_INDEX_DIR;
  if (override) return override;
  const dist = join(SITE_ROOT, 'dist');
  const out = join(SITE_ROOT, 'out');
  if (existsSync(dist)) return dist;
  if (existsSync(out)) return out;
  return dist;
}

function formatMiB(bytes) {
  return `${(bytes / 1024 / 1024).toFixed(2)} MiB`;
}

function main() {
  assertLocaleParity();

  const buildDir = resolveBuildDir();
  const searchDir = join(buildDir, 'api', 'search');

  if (!existsSync(searchDir)) {
    console.error(
      `FAIL: search-index directory '${searchDir}' does not exist. ` +
        'Run `npm run build` first, or set SEARCH_INDEX_DIR to the build output.',
    );
    process.exit(1);
  }

  const failures = [];
  const report = [];

  for (const locale of EXPECTED_LOCALES) {
    // The route handler emits each index as an extensionless file named by the
    // locale path segment (`dist/api/search/en`, `.../zh-cn`, …).
    const file = join(searchDir, locale);
    if (!existsSync(file)) {
      failures.push(`MISSING  ${locale}: no index emitted at '${file}'`);
      report.push(`  ${locale.padEnd(6)}  MISSING`);
      continue;
    }
    const { size } = statSync(file);
    if (size < MIN_INDEX_BYTES) {
      failures.push(
        `EMPTY    ${locale}: index '${file}' is ${size} B ` +
          `(< ${MIN_INDEX_BYTES} B floor — build likely produced an empty index)`,
      );
      report.push(`  ${locale.padEnd(6)}  ${formatMiB(size)}  EMPTY`);
      continue;
    }
    if (size >= GITHUB_PAGES_MAX_BYTES) {
      failures.push(
        `OVERSIZE ${locale}: index '${file}' is ${formatMiB(size)} ` +
          `(>= GitHub Pages 100 MiB per-file limit — CDN will refuse to serve it)`,
      );
      report.push(`  ${locale.padEnd(6)}  ${formatMiB(size)}  OVERSIZE`);
      continue;
    }
    report.push(`  ${locale.padEnd(6)}  ${formatMiB(size)}  ok`);
  }

  console.log(`Per-locale search indices under '${searchDir}':`);
  console.log(report.join('\n'));

  if (failures.length) {
    console.error('\nFAIL: search-index check found violations:');
    for (const f of failures) console.error(`  - ${f}`);
    process.exit(1);
  }

  console.log(
    `\nPASS: all ${EXPECTED_LOCALES.length} per-locale search indices present, ` +
      'non-empty, and under the 100 MiB GitHub Pages limit.',
  );
}

main();
