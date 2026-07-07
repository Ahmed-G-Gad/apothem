// SPDX-License-Identifier: MIT

import type { ReactNode } from 'react';
import { DocsShell } from '@/components/docs-shell';
import { DEFAULT_LOCALE } from '@/lib/i18n';

// English docs chrome — renders the English page tree and the shared docs
// shell. Every non-default routed locale renders the same shell under
// app/[lang]/docs with its own locale.
export default function Layout({ children }: { children: ReactNode }) {
  return <DocsShell locale={DEFAULT_LOCALE}>{children}</DocsShell>;
}
