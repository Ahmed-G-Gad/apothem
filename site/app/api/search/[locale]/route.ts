// SPDX-License-Identifier: MIT

import { localeSearchAPI } from '@/lib/search-index';
import { ROUTED_LOCALES } from '@/lib/i18n';

// Per-locale static search index. The site is `output: 'export'`, so each
// locale's index is emitted as a static file at build time and queried
// client-side. Splitting the index per locale keeps every emitted file far
// below GitHub Pages' hard 100 MB per-file limit — the single combined index
// exceeded it and the CDN refused to serve it, breaking search entirely.
//
// `generateStaticParams` materializes one route per routed locale, so the build
// emits `dist/api/search/<locale>` for each of: en, es, zh-cn, pt-br, fr, de,
// ja, ko, ru, id, hi, ar. The `GET` handler reads only `params` (never the
// request), so it is statically rendered under `output: 'export'`;
// `dynamicParams = false` disallows any locale outside `generateStaticParams`.
export const dynamicParams = false;

export function generateStaticParams(): { locale: string }[] {
  return ROUTED_LOCALES.map((locale) => ({ locale }));
}

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ locale: string }> },
): Promise<Response> {
  const { locale } = await params;
  const api = await localeSearchAPI(locale);
  return api.staticGET();
}
