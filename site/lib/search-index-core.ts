// SPDX-License-Identifier: MIT

import { basename, extname } from 'node:path';
import type { AdvancedIndex } from 'fumadocs-core/search/server';

/**
 * Pure, dependency-light core of the per-locale search-index builder.
 *
 * This module deliberately imports nothing from `@/lib/source`, the MDX content
 * pipeline, or any runtime path alias — only `node:path` and a type-only
 * `fumadocs-core` type (erased at build). That isolation is intentional: the
 * page-to-index transform is the single point that can silently drop a page
 * from the search index, so it must be unit-testable on its own, without
 * standing up the whole content/source pipeline. `lib/search-index.ts` imports
 * `pageToIndex` from here and wires it to the live `source.getPages()` set.
 */

/**
 * The frontmatter-and-loader shape {@link pageToIndex} reads off a Fumadocs
 * page's `data`. A page exposes its searchable body either as a
 * `structuredData` field (a value or an async thunk) or via an async `load()`
 * — Fumadocs uses one or the other depending on the content adapter.
 */
export interface SearchablePageData {
  title?: string;
  description?: string;
  structuredData?:
    | AdvancedIndex['structuredData']
    | (() => Promise<AdvancedIndex['structuredData']>);
  load?: () => Promise<{ structuredData: AdvancedIndex['structuredData'] }>;
}

/** The minimal page surface {@link pageToIndex} reads: URL, source path, data. */
export interface SearchablePage {
  url: string;
  path: string;
  data: unknown;
}

/**
 * Transform a Fumadocs page into an `AdvancedIndex` entry.
 *
 * This inlines Fumadocs' internal `buildIndexDefault` (not a public export) so
 * each per-locale entry is identical in shape to what the combined index
 * produced: `id`/`url` from the page URL, `title`/`description` from the page
 * frontmatter, and the page's structured data as the searchable body.
 *
 * Fail-fast on missing structured data is intentional: a page with no
 * `structuredData` (and no `load()`) cannot be searched, and a silently-skipped
 * page would leave a hole in the index that no error surfaces. Throwing here
 * fails the whole per-locale index build loudly at build time — caught in CI —
 * rather than shipping a quietly-incomplete search index.
 */
export async function pageToIndex(page: SearchablePage): Promise<AdvancedIndex> {
  const raw = page.data as SearchablePageData;

  let structuredData: AdvancedIndex['structuredData'] | undefined;
  if (raw.structuredData) {
    structuredData =
      typeof raw.structuredData === 'function'
        ? await raw.structuredData()
        : raw.structuredData;
  } else if (typeof raw.load === 'function') {
    structuredData = (await raw.load()).structuredData;
  }
  if (!structuredData) {
    throw new Error(
      `Cannot find structured data for search index entry: ${page.url}`,
    );
  }

  return {
    id: page.url,
    title: raw.title ?? basename(page.path, extname(page.path)),
    description: raw.description,
    url: page.url,
    structuredData,
  };
}
