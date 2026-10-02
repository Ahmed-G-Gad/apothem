// SPDX-License-Identifier: MIT

import type { ReactNode } from 'react';
import { source } from '@/lib/source';
import { i18n } from '@/lib/i18n';
import { BrandMark } from '@/components/brand-mark';
import { GithubIcon } from '@/components/github-icon';
import { LandmarkDocsLayout } from '@/components/docs-landmarks';
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
 * `RootProvider` i18n prop. The sidebar sits in a `nav` landmark and each
 * page's content in the `main` landmark the skip link targets (see
 * `docs-landmarks.tsx`).
 */
export function DocsShell({
  locale,
  children,
}: {
  locale: string;
  children: ReactNode;
}) {
  return (
    <LandmarkDocsLayout
      tree={source.getPageTree(locale)}
      // Enables Fumadocs' built-in language switcher in the docs chrome so
      // readers can move to any routed locale (the twelve cohort locales) from
      // any docs page.
      i18n={i18n}
      // Surfaces the repository link as a GitHub icon in the docs chrome, so
      // the source is reachable from every docs page. The link is declared
      // here rather than through `githubUrl`: Fumadocs' built-in icon is an
      // untitled `svg role="img"` (axe svg-img-alt, WCAG 1.1.1), while the
      // site's glyph is `aria-hidden` inside a link the `label` names.
      links={[
        {
          type: 'icon',
          url: REPO_URL,
          label: 'GitHub',
          text: 'GitHub',
          icon: <GithubIcon />,
          external: true,
        },
      ]}
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
      {children}
    </LandmarkDocsLayout>
  );
}
