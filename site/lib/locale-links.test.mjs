// SPDX-License-Identifier: MIT

// Unit tests for `localizeDocsHref`, the step that keeps a reader in their
// language when they follow a body link on a translated docs page. The site
// ships no JS test framework, so these run on Node's built-in runner, importing
// the TypeScript core under `--experimental-strip-types` as
// `search-index-core.test.mjs` does:
//
//   cd site && node --test --experimental-strip-types lib/locale-links.test.mjs
//
// The loader lookup is replaced by a small table of pages, shaped as the
// component in `components/localized-link.tsx` builds them from the content
// loader: a fallback page (the language has no translation) carries the
// requested language's URL but is not `authored`.

import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { isAuthoredPath, localizeDocsHref } from './locale-links.ts';

const toc = (...entries) => entries.map(([id, depth]) => ({ url: `#${id}`, depth }));

const PAGES = {
  'en:': { url: '/docs', authored: true, toc: toc(['home', 2]) },
  'de:': { url: '/de/docs', authored: true, toc: toc(['start', 2]) },
  'en:guide': {
    url: '/docs/guide',
    authored: true,
    toc: toc(['setup', 2], ['shared-roots', 2], ['detail', 3]),
  },
  'de:guide': {
    url: '/de/docs/guide',
    authored: true,
    toc: toc(['einrichtung', 2], ['gemeinsame-wurzeln', 2], ['detail', 3]),
  },
  // A page whose translation has other headings than the English page.
  'en:drift': { url: '/docs/drift', authored: true, toc: toc(['a', 2], ['b', 2]) },
  'de:drift': { url: '/de/docs/drift', authored: true, toc: toc(['x', 2]) },
  'en:levels': { url: '/docs/levels', authored: true, toc: toc(['a', 2], ['b', 2]) },
  'de:levels': { url: '/de/docs/levels', authored: true, toc: toc(['x', 2], ['y', 3]) },
  // A translated id that equals another heading's English id.
  'en:swap': { url: '/docs/swap', authored: true, toc: toc(['overview', 2], ['plugin', 2]) },
  'de:swap': { url: '/de/docs/swap', authored: true, toc: toc(['plugin', 2], ['uebersicht', 2]) },
  // Percent-encoded and raw ids name the same heading.
  'en:roots': { url: '/docs/roots', authored: true, toc: toc(['raíces', 2], ['other', 2]) },
  'de:roots': { url: '/de/docs/roots', authored: true, toc: toc(['wurzeln', 2], ['andere', 2]) },
  // Not translated: the loader serves the English page under the German URL.
  'en:pipeline/plan': { url: '/docs/pipeline/plan', authored: true, toc: toc(['usage', 2]) },
  'de:pipeline/plan': { url: '/de/docs/pipeline/plan', authored: false, toc: toc(['usage', 2]) },
};

const lookup = (slug, lang) => PAGES[`${lang}:${slug.join('/')}`];
const localize = (href) => localizeDocsHref(href, 'de', 'en', lookup);

describe('isAuthoredPath', () => {
  it('is true for a content file under the language folder only', () => {
    assert.equal(isAuthoredPath('ja/install/index.mdx', 'ja'), true);
    assert.equal(isAuthoredPath('pt-br/index.mdx', 'pt-br'), true);
    assert.equal(isAuthoredPath('install/index.mdx', 'ja'), false);
    assert.equal(isAuthoredPath('ja/install/index.mdx', 'de'), false);
    assert.equal(isAuthoredPath('jaa/install/index.mdx', 'ja'), false);
  });
});

describe('links that are not docs links', () => {
  it('are returned as written', () => {
    for (const href of [
      'https://example.com/docs/guide#shared-roots',
      '//example.com/docs/guide',
      'mailto:me@example.com',
      '#setup',
      './guide',
      '../guide#setup',
      'guide',
      '/docs-archive/guide',
      '/de/docs/guide#einrichtung',
      '/llms.txt',
      '/#features',
      '',
    ]) {
      assert.equal(localize(href), href);
    }
  });
});

describe('a docs link without a fragment', () => {
  it('opens the translated page', () => {
    assert.equal(localize('/docs/guide'), '/de/docs/guide');
  });

  it('opens the translated docs index', () => {
    assert.equal(localize('/docs'), '/de/docs');
    assert.equal(localize('/docs/'), '/de/docs');
  });

  it('ignores a trailing slash and keeps a query string', () => {
    assert.equal(localize('/docs/guide/'), '/de/docs/guide');
    assert.equal(localize('/docs/guide?tab=two'), '/de/docs/guide?tab=two');
  });

  it('treats an empty fragment as none', () => {
    assert.equal(localize('/docs/guide#'), '/de/docs/guide');
  });

  it('stays on the English page for a page the language has not translated', () => {
    assert.equal(localize('/docs/pipeline/plan'), '/docs/pipeline/plan');
    assert.equal(localize('/docs/pipeline/plan#usage'), '/docs/pipeline/plan#usage');
  });

  it('leaves a link to no page alone', () => {
    assert.equal(localize('/docs/nope'), '/docs/nope');
    assert.equal(localize('/docs/nope#x'), '/docs/nope#x');
  });
});

describe('a docs link with a fragment', () => {
  it('maps the English id to the translated heading at the same position', () => {
    assert.equal(localize('/docs/guide#setup'), '/de/docs/guide#einrichtung');
    assert.equal(localize('/docs/guide#shared-roots'), '/de/docs/guide#gemeinsame-wurzeln');
    assert.equal(localize('/docs/guide#detail'), '/de/docs/guide#detail');
  });

  it('keeps a query string before the fragment', () => {
    assert.equal(localize('/docs/guide?tab=two#shared-roots'), '/de/docs/guide?tab=two#gemeinsame-wurzeln');
  });

  it('maps the docs index too', () => {
    assert.equal(localize('/docs#home'), '/de/docs#start');
  });

  it('finds the heading whether the fragment is percent-encoded or raw', () => {
    assert.equal(localize('/docs/roots#ra%C3%ADces'), '/de/docs/roots#wurzeln');
    assert.equal(localize('/docs/roots#raíces'), '/de/docs/roots#wurzeln');
  });

  it('goes by the English heading, not by a translated id that happens to match', () => {
    assert.equal(localize('/docs/swap#overview'), '/de/docs/swap#plugin');
    assert.equal(localize('/docs/swap#plugin'), '/de/docs/swap#uebersicht');
  });

  it('stays on the English page when the fragment is not an English id', () => {
    assert.equal(localize('/docs/guide#einrichtung'), '/docs/guide#einrichtung');
    assert.equal(localize('/docs/guide#no-such-heading'), '/docs/guide#no-such-heading');
  });

  it('stays on the English page when the translation has other headings', () => {
    assert.equal(localize('/docs/drift#b'), '/docs/drift#b');
    assert.equal(localize('/docs/levels#b'), '/docs/levels#b');
  });

  it('stays on the English page when the English page cannot be found', () => {
    const noEnglish = (slug, lang) => (lang === 'en' ? undefined : lookup(slug, lang));
    assert.equal(localizeDocsHref('/docs/guide#setup', 'de', 'en', noEnglish), '/docs/guide#setup');
  });
});
