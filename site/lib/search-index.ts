// SPDX-License-Identifier: MIT

import { source } from '@/lib/source';
import {
  createSearchAPI,
  type AdvancedIndex,
  type AdvancedOptions,
} from 'fumadocs-core/search/server';
import { pageToIndex } from '@/lib/search-index-core';

/**
 * Per-locale static search-index construction.
 *
 * The site is `output: 'export'`, so each locale's search index is emitted as a
 * static file at build time and queried client-side. Fumadocs' `createFromSource`
 * emits ONE combined index keyed by all twelve cohort locales — a single file
 * that, with the full English fallback tree indexed per locale, grows past
 * GitHub Pages' hard 100 MB per-file limit, so the CDN refuses to serve it and
 * client search fails outright.
 *
 * This module instead builds a SINGLE-locale index per locale: `getPages(locale)`
 * yields only that locale's resolved page set, each page is transformed to an
 * `AdvancedIndex` entry, and `createSearchAPI('advanced', …)` produces a
 * non-i18n index whose `staticGET`/`export()` emits one small file per locale
 * (served at `/api/search/<locale>`). No single file approaches the limit.
 */

/**
 * Per-locale Orama language (stemmer/tokenizer) selection.
 *
 * Orama auto-derives a tokenizer from a bare ISO code (`es` -> Spanish), but it
 * has no built-in tokenizer for several routed codes — `zh-cn`, `ja`, `ko`,
 * `hi`, `ar`, and `id` are unrecognized, and the kebab `pt-br` is not the bare
 * `pt` ISO code Orama expects. Each entry below is mapped explicitly so the
 * static index build is deterministic and never aborts with
 * `LANGUAGE_NOT_SUPPORTED`.
 *
 * `pt-br`/`fr`/`de`/`ru` map to their Orama built-in stemmers
 * (`portuguese`/`french`/`german`/`russian`). Mandarin (`zh-cn`) and Japanese
 * (`ja`) — the two scripts with no word boundaries that the English tokenizer
 * cannot segment — use the dedicated CJK tokenizers from `@orama/tokenizers`
 * (see {@link CJK_TOKENIZER}); they are wired as a custom Orama tokenizer
 * rather than a `language` string. Korean, Arabic, Hindi, and Indonesian have
 * no dedicated tokenizer in `@orama/tokenizers`, so they map to the English
 * tokenizer: their seeded pages are dominated by Latin-script search tokens
 * (the `apothem` name, CLI commands, flags, and code) that the English
 * tokenizer indexes correctly.
 */
const LOCALE_LANGUAGE: Record<string, string> = {
  'pt-br': 'portuguese',
  fr: 'french',
  de: 'german',
  ru: 'russian',
  ko: 'english',
  id: 'english',
  hi: 'english',
  ar: 'english',
};

/**
 * Locales served by a dedicated `@orama/tokenizers` CJK tokenizer. Mandarin
 * and Japanese have no whitespace word boundaries, so the English tokenizer
 * indexes whole runs as single tokens and search misses every interior term;
 * the script-aware tokenizers segment them correctly. The factory is imported
 * lazily so the (native-ish) tokenizer modules load only for the two locales
 * that need them, and the result is cached per locale across the per-locale
 * index builds.
 */
const CJK_TOKENIZER: Record<string, () => Promise<{ createTokenizer: () => unknown }>> =
  {
    'zh-cn': () => import('@orama/tokenizers/mandarin'),
    ja: () => import('@orama/tokenizers/japanese'),
  };

type OramaTokenizer = NonNullable<AdvancedOptions['tokenizer']>;

const _tokenizerCache = new Map<string, OramaTokenizer>();

/**
 * The dedicated CJK tokenizer for a routed locale, or `undefined` when the
 * locale is served by a `language` string instead. Cached per locale so the
 * tokenizer module loads at most once per build.
 */
async function tokenizerFor(locale: string): Promise<OramaTokenizer | undefined> {
  const loader = CJK_TOKENIZER[locale];
  if (!loader) return undefined;
  const cached = _tokenizerCache.get(locale);
  if (cached) return cached;
  const { createTokenizer } = await loader();
  const tokenizer = createTokenizer() as OramaTokenizer;
  _tokenizerCache.set(locale, tokenizer);
  return tokenizer;
}

/**
 * The Orama language for a routed-locale path segment. `en` and `es` are bare
 * ISO codes Orama recognizes directly (English/Spanish), so they fall through
 * to auto-derivation via the locale code; every other Latin-script code is
 * mapped above. Returns `undefined` for the CJK locales (`zh-cn`, `ja`), which
 * carry a custom tokenizer instead — Orama forbids passing both.
 */
function languageFor(locale: string): string | undefined {
  if (locale in CJK_TOKENIZER) return undefined;
  if (locale === 'en') return 'english';
  if (locale === 'es') return 'spanish';
  return LOCALE_LANGUAGE[locale];
}

/**
 * Transform a Fumadocs page into an `AdvancedIndex` entry. Thin adapter over
 * {@link pageToIndex} (in `lib/search-index-core.ts`) that fixes the input type
 * to the `source.getPages()` element shape; the resolution logic — including
 * the intentional fail-fast throw on a page with no structured data — lives in
 * `pageToIndex` so it is unit-tested without loading the MDX `source` pipeline.
 */
async function buildIndex(
  page: ReturnType<typeof source.getPages>[number],
): Promise<AdvancedIndex> {
  return pageToIndex(page);
}

/**
 * Build the single-locale Fumadocs `SearchAPI` for one routed locale. Its
 * `staticGET` emits the locale's static index file at build time.
 *
 * CJK locales (`zh-cn`, `ja`) carry a dedicated `@orama/tokenizers` tokenizer
 * and no `language`; Orama rejects passing both. Every other locale carries a
 * `language` string (built-in stemmer) and no custom tokenizer.
 */
export async function localeSearchAPI(locale: string) {
  const [indexes, tokenizer] = await Promise.all([
    Promise.all(source.getPages(locale).map(buildIndex)),
    tokenizerFor(locale),
  ]);
  return createSearchAPI(
    'advanced',
    tokenizer
      ? { indexes, tokenizer }
      : { indexes, language: languageFor(locale) },
  );
}
