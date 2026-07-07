// SPDX-License-Identifier: MIT

import type { ReactNode } from 'react';
import { notFound } from 'next/navigation';
import { LocaleOverride } from '@/components/locale-override';
import { ROUTED_NON_DEFAULT_LOCALES } from '@/lib/i18n';

// Layout for the non-default-locale subtree. The default (English) locale is
// served by the root routes (`app/page.tsx`, `app/docs/...`) and is never
// emitted under `[lang]`, so `[lang]` only ever resolves to one of the eleven
// routed non-default locales. The LocaleOverride re-supplies the active
// locale to Fumadocs' i18n context so the language switcher is accurate.
export default async function LangLayout(props: {
  children: ReactNode;
  params: Promise<{ lang: string }>;
}) {
  const { lang } = await props.params;
  if (!ROUTED_NON_DEFAULT_LOCALES.includes(lang)) notFound();

  return <LocaleOverride locale={lang}>{props.children}</LocaleOverride>;
}

export function generateStaticParams() {
  // Enumerate only the non-default routed locales — English is served at the
  // root, so it is intentionally absent here. This yields one param per routed
  // non-default locale (the eleven cohort locales).
  return ROUTED_NON_DEFAULT_LOCALES.map((lang) => ({ lang }));
}
