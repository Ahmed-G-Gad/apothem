// SPDX-License-Identifier: MIT

// Unit tests for the per-locale search-index page transform.
//
// The site ships no JS test framework (no vitest/jest in site/package.json), so
// these run on Node's built-in test runner (`node:test` + `node:assert`, stable
// since Node 18). The test is plain `.mjs` rather than `.ts` on purpose: it
// imports the TypeScript core under `--experimental-strip-types` (the explicit
// `.ts` import specifier is required by Node's runtime resolver), and a `.mjs`
// file is outside tsconfig's `**/*.ts` include, so `next build`'s project
// type-check never sees the `.ts`-extension import (which `tsc` rejects without
// `allowImportingTsExtensions`). This keeps the test runnable AND keeps the
// build's type-check green, with no new dependency and no tsconfig change. Run:
//
//   cd site && node --test --experimental-strip-types lib/search-index-core.test.mjs
//
// The test targets `pageToIndex` — the pure transform extracted from
// `buildIndex` so it can be exercised without standing up the MDX `source`
// pipeline. `pageToIndex` is the single point that decides whether a page makes
// it into a locale's search index, including the intentional fail-fast throw on
// a page with no structured data; that throw is the documented single point of
// failure for the whole per-locale index build, so it is asserted explicitly.

import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { pageToIndex } from './search-index-core.ts';

/** A minimal structured-data body shaped like a Fumadocs page's searchable content. */
const sampleStructuredData = {
  headings: [{ id: 'overview', content: 'Overview' }],
  contents: [
    { heading: 'overview', content: 'Apothem installs harness configs.' },
  ],
};

/** A page carrying inline structured data (the common Fumadocs shape). */
function pageWithInlineData() {
  return {
    url: '/docs/install',
    path: 'install.mdx',
    data: {
      title: 'Install',
      description: 'How to install Apothem.',
      structuredData: sampleStructuredData,
    },
  };
}

describe('pageToIndex', () => {
  it('builds a complete index entry from inline structured data', async () => {
    const entry = await pageToIndex(pageWithInlineData());

    assert.equal(entry.id, '/docs/install');
    assert.equal(entry.url, '/docs/install');
    assert.equal(entry.title, 'Install');
    assert.equal(entry.description, 'How to install Apothem.');
    assert.deepEqual(entry.structuredData, sampleStructuredData);
  });

  it('resolves structured data exposed as an async thunk', async () => {
    const page = {
      url: '/docs/harnesses',
      path: 'harnesses.mdx',
      data: {
        title: 'Harnesses',
        structuredData: async () => sampleStructuredData,
      },
    };

    const entry = await pageToIndex(page);
    assert.deepEqual(entry.structuredData, sampleStructuredData);
    assert.equal(entry.title, 'Harnesses');
  });

  it('resolves structured data exposed via an async load()', async () => {
    const page = {
      url: '/docs/concepts',
      path: 'concepts.mdx',
      data: {
        title: 'Concepts',
        load: async () => ({ structuredData: sampleStructuredData }),
      },
    };

    const entry = await pageToIndex(page);
    assert.deepEqual(entry.structuredData, sampleStructuredData);
  });

  it('derives the title from the file basename when frontmatter omits it', async () => {
    const page = {
      url: '/docs/reference/cli',
      path: 'reference/cli.mdx',
      data: { structuredData: sampleStructuredData },
    };

    const entry = await pageToIndex(page);
    // basename('reference/cli.mdx', '.mdx') -> 'cli'
    assert.equal(entry.title, 'cli');
  });

  it('fails fast with a clear error when a page has no structured data', async () => {
    // Intentional single-point-of-failure assertion. A page with neither
    // `structuredData` nor `load()` cannot be searched; the build MUST throw
    // loudly (caught in CI) rather than silently drop the page and ship a
    // quietly-incomplete index. This documents the throw as deliberate
    // fail-fast behavior — if a future change swaps it for skip-with-warning,
    // this test fails and forces an explicit, reviewed decision.
    const page = {
      url: '/docs/orphan',
      path: 'orphan.mdx',
      data: { title: 'Orphan' },
    };

    await assert.rejects(
      () => pageToIndex(page),
      (err) => {
        assert.ok(err instanceof Error, 'expected an Error to be thrown');
        assert.match(err.message, /structured data/i);
        assert.match(err.message, /\/docs\/orphan/);
        return true;
      },
    );
  });
});
