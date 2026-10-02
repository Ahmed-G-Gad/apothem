// SPDX-License-Identifier: MIT

'use client';

import { usePathname } from 'next/navigation';
import { useEffect } from 'react';
import { COHORT_LOCALES, DEFAULT_LOCALE, ROUTED_NON_DEFAULT_LOCALES } from '@/lib/i18n';

/**
 * Language-of-parts markup for the site chrome (WCAG 3.1.2).
 *
 * The docs chrome comes from Fumadocs, and the site supplies no translation
 * dictionary for it, so on a translated page (`lang="ja"`, `lang="ar"`, …) its
 * labels stay English: "Search", "On this page", "Open Sidebar", the code-block
 * "Copy Text" button, and so on. Without markup a screen reader speaks them
 * with the page language's voice. This component marks each of those strings
 * `lang="en"` on translated pages, and marks every locale name in the language
 * switcher with its own language on every page ("日本語" is Japanese even on
 * an English page).
 *
 * Fumadocs renders these elements itself and offers no prop for their `lang`,
 * so the marking runs on the rendered DOM: once after hydration and again
 * whenever the chrome re-renders (route changes, the search dialog, the TOC
 * popover). React leaves attributes it does not manage in place, so the marks
 * persist. The strings are Fumadocs' own UI keys plus the site's chrome.
 */
const ENGLISH_CHROME = new Set([
  'Search',
  'Open Search',
  'Close Search',
  'No results found',
  'Open Sidebar',
  'Collapse Sidebar',
  'Toggle Menu',
  'Choose a language',
  'On this page',
  'No Headings',
  'Table of Contents',
  'Previous Page',
  'Next Page',
  'Copy Anchor Link',
  'Copy Link',
  'Copy Text',
  'Copied Text',
  'Toggle Theme',
  'Toggle theme',
  'Switch to light theme',
  'Switch to dark theme',
  'Light',
  'Dark',
  'System',
  'Documentation',
  'Change language',
  'Skip to content',
]);

const LOCALE_BY_LABEL = new Map(COHORT_LOCALES.map((locale) => [locale.label, locale.code]));
const TRANSLATED = new Set(ROUTED_NON_DEFAULT_LOCALES);

function isTranslatedPath(pathname: string): boolean {
  const first = pathname.split('/').filter(Boolean)[0];
  return first !== undefined && first !== DEFAULT_LOCALE && TRANSLATED.has(first);
}

function mark(element: Element | null, lang: string): void {
  if (element && !element.hasAttribute('lang')) element.setAttribute('lang', lang);
}

function markChrome(englishChrome: boolean): void {
  if (englishChrome) {
    for (const element of document.querySelectorAll('[aria-label], [placeholder]')) {
      const label = (element.getAttribute('aria-label') ?? element.getAttribute('placeholder') ?? '').trim();
      if (ENGLISH_CHROME.has(label)) mark(element, DEFAULT_LOCALE);
    }
  }
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    const text = node.nodeValue?.trim();
    if (!text) continue;
    const localeCode = LOCALE_BY_LABEL.get(text);
    if (localeCode) mark(node.parentElement, localeCode);
    else if (englishChrome && ENGLISH_CHROME.has(text)) mark(node.parentElement, DEFAULT_LOCALE);
  }
}

export function ChromeLang() {
  const pathname = usePathname();
  useEffect(() => {
    const englishChrome = isTranslatedPath(pathname);
    let frame = 0;
    const schedule = () => {
      if (frame) return;
      frame = requestAnimationFrame(() => {
        frame = 0;
        markChrome(englishChrome);
      });
    };
    markChrome(englishChrome);
    const observer = new MutationObserver(schedule);
    observer.observe(document.body, { childList: true, subtree: true });
    return () => {
      observer.disconnect();
      if (frame) cancelAnimationFrame(frame);
    };
  }, [pathname]);
  return null;
}
