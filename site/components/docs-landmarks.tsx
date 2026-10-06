// SPDX-License-Identifier: MIT

'use client';

import type { ComponentProps } from 'react';
import { DocsLayout, type DocsLayoutProps } from 'fumadocs-ui/layouts/docs';
import { DocsPage, useDocsPage, type DocsPageProps } from 'fumadocs-ui/layouts/docs/page';
import {
  Sidebar,
  SidebarProvider,
  SidebarTrigger,
  useSidebar,
  type SidebarProps,
} from 'fumadocs-ui/layouts/docs/slots/sidebar';
import { cn } from '@/lib/utils';

/**
 * Landmark-bearing replacements for two Fumadocs docs-layout slots.
 *
 * Fumadocs renders the page content as an `<article>` and the sidebar as an
 * `<aside>`, so a docs page exposed no `main` and no `nav` landmark (axe
 * `landmark-one-main`; screen-reader users could not jump between sidebar and
 * content). These wrappers keep Fumadocs' markup and classes and add the
 * landmarks:
 *
 * - the page container renders as `<main id="main-content">`, which is also
 *   the target of the root layout's "Skip to content" link;
 * - the sidebar is wrapped in a `<nav>` with `display: contents`, so the nav
 *   box adds no grid cell and the sidebar keeps its `[grid-area:sidebar]`
 *   placement in the layout grid.
 *
 * The slots hold functions, which cannot cross from a server component into a
 * client one, so the slot wiring lives here in a client module and the server
 * shells pass only serializable props.
 */

function MainContainer({ className, ...props }: ComponentProps<'article'>) {
  const { full } = useDocsPage();
  return (
    <main
      id="main-content"
      tabIndex={-1}
      data-full={full}
      {...props}
      className={cn(
        // Fumadocs' own page-container classes (layouts/docs/page/slots/container).
        'flex flex-col w-full max-w-[900px] mx-auto [grid-area:main] px-4 py-6 gap-4 md:px-6 md:pt-8 xl:px-8 xl:pt-14',
        full && 'max-w-[1168px]',
        // A programmatic focus target for the skip link, not a control.
        'focus:outline-none',
        className,
      )}
    />
  );
}

function NavSidebar(props: SidebarProps) {
  return (
    <nav aria-label="Documentation" className="contents">
      <Sidebar {...props} />
    </nav>
  );
}

// Module-level so the slot's component identity is stable across renders (an
// inline component would remount the sidebar and drop its open/collapsed state).
const SIDEBAR_SLOT = {
  provider: SidebarProvider,
  root: NavSidebar,
  trigger: SidebarTrigger,
  useSidebar,
};

/** Fumadocs `DocsLayout` with the sidebar inside a labelled `nav` landmark. */
export function LandmarkDocsLayout(props: DocsLayoutProps) {
  return <DocsLayout {...props} slots={{ ...props.slots, sidebar: SIDEBAR_SLOT }} />;
}

/** Fumadocs `DocsPage` whose content container is the page's `main` landmark. */
export function LandmarkDocsPage(props: DocsPageProps) {
  return <DocsPage {...props} slots={{ ...props.slots, container: MainContainer }} />;
}
