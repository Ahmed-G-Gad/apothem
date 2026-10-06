// SPDX-License-Identifier: MIT

'use client';

import { RootProvider } from 'fumadocs-ui/provider/next';
import { usePathname, useRouter } from 'next/navigation';
import { useCallback } from 'react';
import type { ReactNode } from 'react';
import {
  DEFAULT_LOCALE,
  ROUTED_LOCALES,
  LOCALE_SWITCHER_ITEMS,
} from '@/lib/i18n';
import StaticSearchDialog from '@/components/static-search-dialog';
import { ChromeLang } from '@/components/chrome-lang';

const ROUTED_SET = new Set<string>(ROUTED_LOCALES);

/**
 * Strip a leading routed-locale segment from a pathname, returning the
 * locale-agnostic path. `/es/docs/x` → `/docs/x`; `/docs/x` (English, no
 * prefix) → `/docs/x` unchanged.
 */
function stripLocale(pathname: string): string {
  const segments = pathname.split('/').filter((s) => s.length > 0);
  if (segments.length > 0 && ROUTED_SET.has(segments[0]) && segments[0] !== DEFAULT_LOCALE) {
    segments.shift();
  }
  return `/${segments.join('/')}`;
}

/**
 * Client-side site providers. Wraps Fumadocs' `RootProvider` and supplies a
 * locale-aware `onLocaleChange` that honors `hideLocale: 'default-locale'`:
 * switching to English navigates to the un-prefixed root URL, while switching
 * to a non-default locale prepends that locale's path segment. The default
 * Fumadocs switcher always prefixes every locale (including the default),
 * which would route English to `/en/...` and break the EN-at-root URLs.
 *
 * `currentLocale` is the locale of the rendered subtree (`en` at the root,
 * the `[lang]` param under the per-locale routes).
 */
export function SiteProviders({
  currentLocale,
  children,
}: {
  currentLocale: string;
  children: ReactNode;
}) {
  const router = useRouter();
  const pathname = usePathname();

  const onLocaleChange = useCallback(
    (nextLocale: string) => {
      const agnostic = stripLocale(pathname);
      const normalized = agnostic === '/' ? '' : agnostic;
      const target =
        nextLocale === DEFAULT_LOCALE
          ? normalized || '/'
          : `/${nextLocale}${normalized}`;
      router.push(target);
    },
    [pathname, router],
  );

  return (
    <RootProvider
      theme={{ defaultTheme: 'dark', enableSystem: true }}
      // Static-export search: replace the default fetch-based dialog with one
      // that downloads the prebuilt index and runs Orama in the browser (see
      // static-search-dialog.tsx). The default dialog POSTs to a dynamic
      // /api/search route that does not exist under `output: 'export'`.
      search={{ SearchDialog: StaticSearchDialog }}
      i18n={{
        locale: currentLocale,
        locales: LOCALE_SWITCHER_ITEMS,
        onLocaleChange,
      }}
    >
      {/* Marks the untranslated chrome strings `lang="en"` on translated pages
          and each language-switcher entry with its own language (WCAG 3.1.2). */}
      <ChromeLang />
      {children}
    </RootProvider>
  );
}
