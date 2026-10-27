// SPDX-License-Identifier: MIT

'use client';

import { usePathname } from 'next/navigation';
import { useLayoutEffect } from 'react';
import { documentLocaleFromPathname } from '@/lib/i18n';

/**
 * Keeps `<html lang>` and `dir` on the current page's locale (WCAG 3.1.1).
 *
 * The site has one root layout, so React does not re-render `<html>` when the
 * language switcher, or any link, moves to another locale on the client. The
 * static HTML and the head script in `app/layout.tsx` set both attributes when
 * a document first loads, and never again: without this component, switching
 * from German to Arabic left the Arabic page marked `lang="de"` and laid out
 * left to right. A layout effect runs before the browser paints the new
 * route, so the direction changes without a frame of the old layout.
 */
export function DocumentLocale() {
  const pathname = usePathname();
  useLayoutEffect(() => {
    const { lang, dir } = documentLocaleFromPathname(pathname);
    const root = document.documentElement;
    if (root.lang !== lang) root.lang = lang;
    if (root.dir !== dir) root.dir = dir;
  }, [pathname]);
  return null;
}
