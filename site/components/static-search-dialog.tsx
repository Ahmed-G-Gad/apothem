// SPDX-License-Identifier: MIT

'use client';

import { useDocsSearch } from 'fumadocs-core/search/client';
import { oramaStaticClient } from 'fumadocs-core/search/client/orama-static';
import {
  SearchDialog,
  SearchDialogClose,
  SearchDialogContent,
  SearchDialogFooter,
  SearchDialogHeader,
  SearchDialogIcon,
  SearchDialogInput,
  SearchDialogList,
  SearchDialogOverlay,
  type SharedProps,
} from 'fumadocs-ui/components/dialog/search';
import { useI18n } from 'fumadocs-ui/contexts/i18n';

/**
 * Static-export search dialog. The site is `output: 'export'`, so the search
 * index is emitted as a static file at build time (the per-locale handler at
 * app/api/search/[locale]/route.ts `staticGET` emits one index per locale) and
 * queried entirely in the browser — there is no dynamic
 * `/api/search` route on static hosting. The default Fumadocs dialog uses
 * `fetchClient`, which POSTs queries to that non-existent route and returns the
 * whole index unfiltered. `oramaStaticClient` instead downloads the prebuilt
 * index once and runs Orama locally. The active locale (from the RootProvider i18n context)
 * selects the matching per-locale sub-index — the static i18n index is keyed by
 * the routed path form (`en`, `es`, `zh-cn`), exactly what `useI18n().locale`
 * carries here.
 */
export default function StaticSearchDialog(props: SharedProps) {
  const { locale } = useI18n();
  const { search, setSearch, query } = useDocsSearch({
    // Per-locale static index: one file per routed locale at
    // `/api/search/<locale>`, split because the single combined index exceeded
    // GitHub Pages' hard 100 MB per-file limit. Each file is a single-locale
    // (non-i18n) index, so `locale` is omitted — the client reads the unkeyed
    // default db, and passing a locale would miss it and warn.
    client: oramaStaticClient({ from: `/api/search/${locale}` }),
  });

  return (
    <SearchDialog
      search={search}
      onSearchChange={setSearch}
      isLoading={query.isLoading}
      {...props}
    >
      <SearchDialogOverlay />
      <SearchDialogContent>
        <SearchDialogHeader>
          <SearchDialogIcon />
          <SearchDialogInput />
          <SearchDialogClose />
        </SearchDialogHeader>
        <SearchDialogList
          items={query.data !== 'empty' ? query.data : null}
        />
      </SearchDialogContent>
      <SearchDialogFooter />
    </SearchDialog>
  );
}
