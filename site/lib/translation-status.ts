// SPDX-License-Identifier: MIT

import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { sourceHash } from '@/lib/translation-source.mjs';

/**
 * How a page served under a locale URL relates to its English source.
 *
 * - `fallback`: the locale has no translation of the page, so the loader
 *   served the English page (`fallbackLanguage: 'en'`).
 * - `current`: the translation's recorded `sourceHash` matches the English
 *   page as it is now.
 * - `stale`: the English page has changed since the translation was made, or
 *   the translation records no source.
 */
export type TranslationState = 'fallback' | 'current' | 'stale';

// Each English page is hashed once per build, not once per locale.
const englishHashes = new Map<string, string>();

function englishHash(englishPath: string): string {
  let hash = englishHashes.get(englishPath);
  if (hash === undefined) {
    const text = readFileSync(join(process.cwd(), 'content', 'docs', englishPath), 'utf8');
    hash = sourceHash(text);
    englishHashes.set(englishPath, hash);
  }
  return hash;
}

/**
 * Classify a page resolved for `locale`. `pagePath` is the loader's
 * content-relative file path (`ja/install/index.mdx` for a translation,
 * `install/index.mdx` for the English fallback).
 */
export function translationState(
  pagePath: string,
  locale: string,
  recordedHash: string | undefined,
): TranslationState {
  const prefix = `${locale}/`;
  if (!pagePath.startsWith(prefix)) return 'fallback';
  return recordedHash === englishHash(pagePath.slice(prefix.length)) ? 'current' : 'stale';
}
