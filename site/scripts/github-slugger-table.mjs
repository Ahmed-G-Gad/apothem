// SPDX-License-Identifier: MIT

// Writes `scripts/dev/github-slugger-removed.txt`, the set of code points that
// github-slugger drops from a heading before it joins the words with "-".
//
// Why this exists. Every heading id on the site comes from github-slugger
// (through Fumadocs' `remarkHeading`). `scripts/dev/github_slugger.py` ports it so
// the anchor guard can compute those ids in the required Python CI job, which has
// no `site/node_modules`. The one thing it cannot derive is github-slugger's
// removal table (its `regex.js`, generated from Unicode data), so this script
// records it as plain ranges that both languages read. `npm test` compares the
// committed table with the installed package, so a github-slugger upgrade that
// changes the table fails there instead of silently skewing the guard, and the
// Python test suite compares the table's recorded version with the lockfile.
//
// Usage (from `site/`):
//   node scripts/github-slugger-table.mjs           rewrite the table
//   node scripts/github-slugger-table.mjs --check   exit 1 when the table is stale
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const SCRIPT_DIR = dirname(fileURLToPath(import.meta.url));
export const TABLE_PATH = join(SCRIPT_DIR, '..', '..', 'scripts', 'dev', 'github-slugger-removed.txt');

const LAST_CODE_POINT = 0x10ffff;
const SURROGATES = [0xd800, 0xdfff];

/**
 * The inclusive `[first, last]` code-point ranges `regex` removes from a
 * single-character string. Lone surrogates are skipped: they are not scalar
 * values, and a well-formed page never holds one. The Python port deletes whole
 * code points, so an astral character the regex removes only in part (one
 * surrogate of its pair) is an error, not a range.
 */
export function removedRanges(regex) {
  const ranges = [];
  let first = -1;
  let last = -1;
  for (let codePoint = 0; codePoint <= LAST_CODE_POINT; codePoint += 1) {
    if (codePoint >= SURROGATES[0] && codePoint <= SURROGATES[1]) continue;
    const character = String.fromCodePoint(codePoint);
    const kept = character.replace(regex, '');
    if (kept !== '' && kept !== character) {
      throw new Error(`the regex removes part of U+${codePoint.toString(16).toUpperCase()}`);
    }
    if (kept === '') {
      if (first === -1) first = codePoint;
      last = codePoint;
    } else if (first !== -1) {
      ranges.push([first, last]);
      first = -1;
    }
  }
  if (first !== -1) ranges.push([first, last]);
  return ranges;
}

const hex = (codePoint) => codePoint.toString(16).padStart(4, '0');

/** One `first-last` line per range (a single code point is written alone). */
export function formatRanges(ranges) {
  return ranges.map(([first, last]) => (first === last ? hex(first) : `${hex(first)}-${hex(last)}`));
}

// Built in two pieces so the REUSE parser does not read this literal as a licence tag.
export const SPDX_LINE = '# SPDX-License-' + 'Identifier: MIT';

/** The commented lines the table starts with; `version` is the package's own. */
export function header(version) {
  return [
    SPDX_LINE,
    '#',
    `# Code points github-slugger ${version} removes from a heading (after lower-casing)`,
    '# before it turns each space into "-": one inclusive hex range per line. Space',
    '# (0020) and hyphen (002d) are not listed, so they survive. Read by',
    '# scripts/dev/github_slugger.py; generated from the installed package by',
    '# site/scripts/github-slugger-table.mjs, which `npm test` re-runs with --check.',
    '# github-slugger is ISC-licensed (https://github.com/Flet/github-slugger).',
  ];
}

export function renderTable(regex, version) {
  return `${[...header(version), ...formatRanges(removedRanges(regex))].join('\n')}\n`;
}

/** The installed github-slugger's regex and version. */
export async function installedSlugger() {
  const { regex } = await import('github-slugger/regex.js');
  const regexPath = fileURLToPath(import.meta.resolve('github-slugger/regex.js'));
  const { version } = JSON.parse(readFileSync(join(dirname(regexPath), 'package.json'), 'utf8'));
  return { regex, version };
}

async function main() {
  const { regex, version } = await installedSlugger();
  const table = renderTable(regex, version);
  if (process.argv.includes('--check')) {
    if (readFileSync(TABLE_PATH, 'utf8') !== table) {
      console.error(`${TABLE_PATH} is stale: run \`node scripts/github-slugger-table.mjs\` from site/.`);
      process.exit(1);
    }
    console.log(`github-slugger ${version} table is current`);
    return;
  }
  writeFileSync(TABLE_PATH, table);
  console.log(`wrote ${TABLE_PATH}`);
}

if (import.meta.main) await main();
