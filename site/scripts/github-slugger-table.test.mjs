// SPDX-License-Identifier: MIT

// Unit tests for the github-slugger removal table
// (`scripts/dev/github-slugger-removed.txt`) that the Python anchor guard reads.
// The site ships no JS test framework, so these run on Node's built-in runner:
//
//   cd site && node --test scripts/github-slugger-table.test.mjs
//
// The last test is the one that matters in CI: it regenerates the table from the
// installed package and fails when the committed copy differs, which is how a
// github-slugger upgrade that changes its Unicode data reaches the guard.

import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { describe, it } from 'node:test';
import { SPDX_LINE, TABLE_PATH, formatRanges, header, installedSlugger, removedRanges, renderTable } from './github-slugger-table.mjs';

describe('removedRanges', () => {
  it('lists each run of removed code points once, in order', () => {
    assert.deepEqual(removedRanges(/[\x41-\x43\x45]/g), [
      [0x41, 0x43],
      [0x45, 0x45],
    ]);
  });

  it('removes a whole astral character or fails', () => {
    assert.deepEqual(removedRanges(/[\u{1F600}-\u{1F64F}]/gu), [[0x1f600, 0x1f64f]]);
    // A regex that deletes only the high surrogate of a pair would leave a lone low surrogate.
    const highSurrogateOnly = new RegExp(String.fromCharCode(0xd83d), 'g');
    assert.throws(() => removedRanges(highSurrogateOnly), /removes part of U\+1F400/);
  });
});

describe('formatRanges', () => {
  it('writes a lone code point once and a run as first-last, in four-digit hex', () => {
    assert.deepEqual(formatRanges([[0, 0x1f], [0x60, 0x60], [0xe01f0, 0x10ffff]]), ['0000-001f', '0060', 'e01f0-10ffff']);
  });
});

describe('renderTable', () => {
  it('opens with the SPDX line and names the package version', () => {
    const lines = header('9.8.7');
    assert.equal(lines[0], SPDX_LINE);
    assert.match(lines[2], /github-slugger 9\.8\.7 removes/);
    assert.ok(lines.every((line) => line.startsWith('#')));
  });
});

describe('the committed table', () => {
  it('matches the installed github-slugger', async () => {
    const { regex, version } = await installedSlugger();
    assert.equal(
      readFileSync(TABLE_PATH, 'utf8'),
      renderTable(regex, version),
      'run `node scripts/github-slugger-table.mjs` from site/ and commit the result',
    );
  });
});
