// SPDX-License-Identifier: MIT

import { DocsLayout } from 'fumadocs-ui/layouts/docs';
import type { ReactNode } from 'react';
import { source } from '@/lib/source';
import { i18n } from '@/lib/i18n';
import { BrandMark } from '@/components/brand-mark';
import { ThemeToggle } from '@/components/theme-toggle';

const REPO_URL = 'https://github.com/ahmed-g-gad/apothem';

/**
 * Shared docs chrome rendered by both the English root docs layout
 * (`app/docs/layout.tsx`) and the per-locale docs layout
 * (`app/[lang]/docs/layout.tsx`). Centralizing it keeps the docs chrome —
 * the brand mark, the header-owned theme toggle, the GitHub link, and the
 * defaultOpenLevel sidebar — identical across every locale.
 *
 * The `locale` selects which per-language page tree the sidebar renders;
 * `i18n` enables Fumadocs' built-in language switcher. The current locale and
 * the available locale list are supplied by the enclosing layout's
 * `RootProvider` i18n prop.
 */
export function DocsShell({
  locale,
  children,
}: {
  locale: string;
  children: ReactNode;
}) {
  return (
    <DocsLayout
      tree={source.getPageTree(locale)}
      // Enables Fumadocs' built-in language switcher in the docs chrome so
      // readers can move to any routed locale (the twelve cohort locales) from
      // any docs page.
      i18n={i18n}
      // Surfaces the repository link as a GitHub icon in the docs chrome, so
      // the source is reachable from every docs page (it is absent by default).
      githubUrl={REPO_URL}
      nav={{
        title: (
          <span className="flex items-center gap-2 font-semibold">
            <BrandMark size={22} decorative />
            Apothem
          </span>
        ),
        // The same top-right theme toggle the landing nav carries, surfaced in
        // the docs header so the control sits in one consistent, always-visible
        // location across every surface (Fumadocs' default buries it in the
        // sidebar footer — see the disabled themeSwitch below).
        children: <ThemeToggle className="ms-auto" />,
      }}
      // The header now owns the theme toggle; disabling the sidebar-footer
      // switch keeps exactly one toggle on the page (no confusing duplicate).
      themeSwitch={{ enabled: false }}
      sidebar={{
        // Open the top-level section groups by default so the full information
        // architecture is visible on first load without a click.
        defaultOpenLevel: 1,
      }}
    >
      {/* Target for the root layout's "Skip to content" link (href
          `#main-content`); Fumadocs' DocsLayout/DocsPage renders no such id, so
          docs routes must supply one (WCAG 2.4.1 bypass-blocks).

          It is a dedicated sentinel rather than a wrapper around `children` on
          purpose. DocsPage renders its three regions — the article
          (`[grid-area:main]`), the "On this page" TOC rail (`[grid-area:toc]`),
          and the mobile TOC popover (`[grid-area:toc-popover]`) — as direct
          participants in the CSS grid defined on the enclosing DocsLayout
          container. A block wrapper around them inserts a box between that grid
          and its named-area items, so `[grid-area:*]` stops resolving and the
          TOC rail collapses (it never renders). Leaving `children` unwrapped
          keeps the grid intact.

          `sr-only` is `position: absolute`, so the sentinel is out of grid flow
          and never occupies a grid cell, yet it remains a real, focusable box
          (`tabIndex={-1}`) — so the skip link both scrolls to and moves focus
          into the content, which a box-less (`display: contents`) element
          cannot receive. */}
      <div id="main-content" tabIndex={-1} className="sr-only" />
      {children}
    </DocsLayout>
  );
}
