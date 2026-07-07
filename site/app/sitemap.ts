// SPDX-License-Identifier: MIT

import type { MetadataRoute } from 'next';
import { source } from '@/lib/source';
import { buildAlternates } from '@/lib/hreflang';
import {
  SITE_URL,
  DEFAULT_LOCALE,
  ROUTED_NON_DEFAULT_LOCALES,
} from '@/lib/i18n';
import { authoredSlugs } from '@/lib/translated-pages';

/**
 * Sitemap generator for the Apothem documentation site.
 *
 * Next.js App Router emits this as `/sitemap.xml` (the `Sitemap:` line in
 * `public/robots.txt` points here). The file enumerates every routed page —
 * the landing page, the docs index, and every authored docs page across the
 * routed locales — as an absolute URL under `SITE_URL`.
 *
 * The enumeration deliberately mirrors the routing strategy in `lib/source.ts`
 * + `lib/translated-pages.ts`: English pages come from `source.getPages()`
 * (the source-locale tree), while non-default locales contribute ONLY their
 * genuinely-authored translations via `authoredSlugs()`. Using
 * `source.getPages('<locale>')` directly would enumerate the entire English
 * fallback tree for each seeded locale and flood the sitemap with locale URLs
 * that have no real translation — the EN-only-drift the i18n discipline
 * forbids. Each entry carries `alternates.languages` (hreflang) derived from
 * `buildAlternates`, so search engines see the symmetric cross-locale cluster.
 */

// The site builds with `output: export` (static HTML export), so the sitemap
// route must be statically generated at build time rather than served
// dynamically. This emits a single `/sitemap.xml` into the export output.
export const dynamic = 'force-static';

/** The locale-agnostic docs paths that are not real indexable routes. */
const EXCLUDED_AGNOSTIC_PATHS = new Set(['/docs/404']);

/** Build one sitemap entry from a locale-agnostic-or-routed URL path. */
function entry(routedPath: string): MetadataRoute.Sitemap[number] {
  const alternates = buildAlternates(routedPath);
  return {
    url: alternates.canonical,
    alternates: { languages: alternates.languages },
  };
}

export default function sitemap(): MetadataRoute.Sitemap {
  const seen = new Set<string>();
  const entries: MetadataRoute.Sitemap = [];

  const add = (routedPath: string) => {
    if (seen.has(routedPath)) return;
    seen.add(routedPath);
    entries.push(entry(routedPath));
  };

  // 1. The landing page and the docs index, explicitly.
  add('/');
  add('/docs');

  // 1b. Every localized landing page — app/[lang]/page.tsx statically generates
  //     one per routed non-default locale at `/<lang>`. Without these the
  //     localized homepages (reachable, HTTP 200) are invisible to crawlers.
  for (const lang of ROUTED_NON_DEFAULT_LOCALES) {
    add(`/${lang}`);
  }

  // 2. Every English (source-locale) docs page. `page.url` is the routed
  //    `/docs/...` path; the 404 placeholder page is not an indexable route.
  for (const page of source.getPages(DEFAULT_LOCALE)) {
    if (EXCLUDED_AGNOSTIC_PATHS.has(page.url)) continue;
    add(page.url);
  }

  // 3. Every authored non-default-locale docs page, by its routed URL. Only
  //    genuinely-translated slugs are emitted (no English-fallback duplicates).
  for (const lang of ROUTED_NON_DEFAULT_LOCALES) {
    for (const slug of authoredSlugs(lang)) {
      const page = source.getPage(slug, lang);
      if (!page) continue;
      if (EXCLUDED_AGNOSTIC_PATHS.has(`/docs/${slug.join('/')}`)) continue;
      add(page.url);
    }
  }

  return entries;
}
