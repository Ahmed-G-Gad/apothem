// SPDX-License-Identifier: MIT

import type { ReactNode } from 'react';
import { DocsShell } from '@/components/docs-shell';

// Per-locale docs chrome. Renders the same shared docs shell as the English
// root layout, but with the locale's own page tree (so the sidebar reflects
// the locale's content, falling back to English where a page is untranslated).
export default async function LangDocsLayout(props: {
  children: ReactNode;
  params: Promise<{ lang: string }>;
}) {
  const { lang } = await props.params;
  return <DocsShell locale={lang}>{props.children}</DocsShell>;
}
