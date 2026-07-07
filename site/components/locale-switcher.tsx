// SPDX-License-Identifier: MIT

'use client';

import * as React from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { Globe, Check } from 'lucide-react';
import { DEFAULT_LOCALE, ROUTED_LOCALES, COHORT_LOCALES } from '@/lib/i18n';

// The routed locales, in cohort order, as {code, path, label} for the menu.
// `path` is '' for the source locale (English at the site root) and the
// URL-path segment otherwise (`es`, `zh-cn`, …).
const ROUTED_SET = new Set<string>(ROUTED_LOCALES);
// `ROUTED_LOCALES` holds URL-path forms (`zh-cn`), while a cohort entry's
// `code` is the BCP-47 tag (`zh-CN`); match on either so code≠path locales
// (zh-CN, pt-BR) are included, not silently dropped.
const ITEMS = COHORT_LOCALES.filter(
  (l) => ROUTED_SET.has(l.code) || (l.path !== '' && ROUTED_SET.has(l.path)),
);

/**
 * Strip a leading routed-locale segment from a pathname, returning the
 * locale-agnostic path. `/es/docs/x` → `/docs/x`; `/docs/x` (English, no
 * prefix) → `/docs/x` unchanged. Mirrors the logic in site-providers.tsx so
 * the landing switcher and the docs switcher navigate identically.
 */
function stripLocale(pathname: string): string {
  const segments = pathname.split('/').filter((s) => s.length > 0);
  if (
    segments.length > 0 &&
    ROUTED_SET.has(segments[0]) &&
    segments[0] !== DEFAULT_LOCALE
  ) {
    segments.shift();
  }
  return `/${segments.join('/')}`;
}

/**
 * Landing-surface language switcher. The docs chrome carries Fumadocs' own
 * switcher; this gives the marketing landing (English and every localized
 * variant) the same control so the twelve-locale corpus is discoverable from
 * the first page a visitor sees — not buried inside the docs. It navigates to
 * the same logical page in the chosen locale, honoring `hideLocale:
 * 'default-locale'` (English at the un-prefixed root). Built on a native
 * `<details>` disclosure: accessible and keyboard-operable with no dropdown
 * dependency, and it closes on selection and on outside click.
 */
export function LocaleSwitcher({ className }: { className?: string }) {
  const router = useRouter();
  const pathname = usePathname();
  const ref = React.useRef<HTMLDetailsElement>(null);

  // Derive the active locale from the URL's first path segment.
  const activeCode = React.useMemo(() => {
    const seg = pathname.split('/').filter(Boolean)[0];
    const match = ITEMS.find((l) => l.path && l.path === seg);
    return match ? match.code : DEFAULT_LOCALE;
  }, [pathname]);
  const activeLabel =
    ITEMS.find((l) => l.code === activeCode)?.label ?? 'English';

  // Close the menu on any outside click, or on Escape — returning focus to the
  // summary so a keyboard user can dismiss the open menu the standard way.
  React.useEffect(() => {
    function onDocClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        ref.current.removeAttribute('open');
      }
    }
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape' && ref.current?.hasAttribute('open')) {
        ref.current.removeAttribute('open');
        ref.current.querySelector<HTMLElement>('summary')?.focus();
      }
    }
    document.addEventListener('click', onDocClick);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('click', onDocClick);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, []);

  const go = React.useCallback(
    (locale: (typeof ITEMS)[number]) => {
      ref.current?.removeAttribute('open');
      const agnostic = stripLocale(pathname);
      const normalized = agnostic === '/' ? '' : agnostic;
      const target = locale.path ? `/${locale.path}${normalized}` : normalized || '/';
      router.push(target);
    },
    [pathname, router],
  );

  return (
    <details ref={ref} className={`group relative ${className ?? ''}`}>
      <summary
        aria-label="Change language"
        title="Change language"
        className="inline-flex size-11 cursor-pointer list-none items-center justify-center rounded-md text-[var(--muted-foreground)] transition-colors hover:bg-[var(--muted)] hover:text-[var(--foreground)] [&::-webkit-details-marker]:hidden sm:size-9"
      >
        <Globe className="size-5" aria-hidden />
      </summary>
      <ul
        className="absolute end-0 z-50 mt-1 max-h-[70vh] w-44 overflow-auto rounded-md border border-[var(--border)] bg-[var(--background)] p-1 shadow-lg"
      >
        {ITEMS.map((l) => {
          const active = l.code === activeCode;
          return (
            <li key={l.code}>
              <button
                type="button"
                dir={l.dir}
                onClick={() => go(l)}
                aria-current={active ? 'true' : undefined}
                className="flex min-h-9 w-full items-center justify-between gap-2 rounded-sm px-3 text-sm text-[var(--muted-foreground)] transition-colors hover:bg-[var(--muted)] hover:text-[var(--foreground)] aria-[current=true]:text-[var(--foreground)]"
              >
                <span>{l.label}</span>
                {active ? <Check className="size-4" aria-hidden /> : null}
              </button>
            </li>
          );
        })}
      </ul>
    </details>
  );
}
