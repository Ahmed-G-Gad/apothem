// SPDX-License-Identifier: MIT

'use client';

import { I18nProvider } from 'fumadocs-ui/contexts/i18n';
import { usePathname, useRouter } from 'next/navigation';
import { useCallback } from 'react';
import type { ReactNode } from 'react';
import {
  DEFAULT_LOCALE,
  ROUTED_LOCALES,
  LOCALE_SWITCHER_ITEMS,
} from '@/lib/i18n';

const ROUTED_SET = new Set<string>(ROUTED_LOCALES);

function stripLocale(pathname: string): string {
  const segments = pathname.split('/').filter((s) => s.length > 0);
  if (segments.length > 0 && ROUTED_SET.has(segments[0]) && segments[0] !== DEFAULT_LOCALE) {
    segments.shift();
  }
  return `/${segments.join('/')}`;
}

/**
 * Overrides the locale context for a non-default-locale subtree
 * (`app/[lang]/...`). The root `RootProvider` (in `app/layout.tsx`) defaults
 * the locale to English; this provider, mounted inside the `[lang]` layout,
 * re-supplies the correct current locale and the same `hideLocale`-aware
 * `onLocaleChange` so the language switcher reflects the active locale and
 * routes English back to its un-prefixed root URLs.
 */
export function LocaleOverride({
  locale,
  children,
}: {
  locale: string;
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
    <I18nProvider
      locale={locale}
      locales={LOCALE_SWITCHER_ITEMS}
      onLocaleChange={onLocaleChange}
    >
      {children}
    </I18nProvider>
  );
}
