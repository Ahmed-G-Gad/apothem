// SPDX-License-Identifier: MIT

'use client';

import { useId, type ReactNode } from 'react';
import { usePathname } from 'fumadocs-core/framework';
import type { Folder } from 'fumadocs-core/page-tree';
import {
  SidebarFolder,
  SidebarFolderContent,
  SidebarFolderTrigger,
  SidebarItem,
  useFolder,
  useFolderDepth,
} from 'fumadocs-ui/components/sidebar/base';
import { useTreePath } from 'fumadocs-ui/contexts/tree';
import { localeFromPathname, SIDEBAR_TOGGLE_HINT } from '@/lib/i18n';
import { cn } from '@/lib/utils';

/**
 * Sidebar folder with a separate, keyboard-reachable disclosure button.
 *
 * Fumadocs draws a folder that has an overview page (an `index`) as a single
 * link with the open/close chevron inside it. The chevron is an aria-hidden
 * icon that only a mouse click reaches, so keyboard and screen-reader users
 * can neither open nor close the section and never hear its state. The site's
 * section lists leave `index` out on purpose (one link per section, see
 * `scripts/author-ia.mjs`), which puts every section in that shape.
 *
 * This component keeps the section title as the link to its overview page and
 * puts the chevron in its own `<button>`: the Radix collapsible trigger, which
 * carries `aria-expanded` and `aria-controls` for the folder's list. The button
 * is named by the link plus a visually hidden action ("Install show or hide
 * pages", `aria-labelledby`), all in the reader's language, so a screen reader
 * tells it apart from the link (strings: `SIDEBAR_TOGGLE_HINT` in
 * `lib/i18n.ts`). The list stays in the page while closed, hidden with the
 * `hidden` attribute, so the button's `aria-controls` always points at an
 * element that exists. A folder without an overview page keeps Fumadocs'
 * own trigger, which is already a button. The classes and offsets mirror
 * Fumadocs' docs-layout sidebar (`layouts/docs/slots/sidebar.js`) so the
 * sidebar looks the same.
 */

const ITEM =
  'relative flex flex-row items-center gap-2 rounded-lg p-2 text-start text-fd-muted-foreground wrap-anywhere [&_svg]:size-4 [&_svg]:shrink-0';
const LINK =
  'transition-colors hover:bg-fd-accent/50 hover:text-fd-accent-foreground/80 hover:transition-none data-[active=true]:bg-fd-primary/10 data-[active=true]:text-fd-primary data-[active=true]:hover:transition-colors';
const BUTTON =
  'transition-colors hover:bg-fd-accent/50 hover:text-fd-accent-foreground/80 hover:transition-none';
const HIGHLIGHT =
  "data-[active=true]:before:content-[''] data-[active=true]:before:bg-fd-primary data-[active=true]:before:absolute data-[active=true]:before:w-px data-[active=true]:before:inset-y-2.5 data-[active=true]:before:inset-s-2.5";

function itemOffset(depth: number): string {
  return `calc(${2 + 3 * depth} * var(--spacing))`;
}

function normalize(url: string): string {
  return url.length > 1 && url.endsWith('/') ? url.slice(0, -1) : url;
}

function FolderHeader({ item }: { item: Folder }) {
  const depth = useFolderDepth();
  const pathname = usePathname();
  const labelId = useId();
  const hintId = useId();
  const collapsible = item.collapsible ?? true;
  const offset = { paddingInlineStart: itemOffset(depth - 1) };

  if (!item.index) {
    return (
      <SidebarFolderTrigger className={cn(ITEM, collapsible && BUTTON, 'w-full')} style={offset}>
        {item.icon}
        {item.name}
      </SidebarFolderTrigger>
    );
  }

  return (
    <div className="relative flex items-center">
      <SidebarItem
        id={labelId}
        href={item.index.url}
        external={item.index.external}
        active={normalize(item.index.url) === normalize(pathname)}
        className={cn(ITEM, LINK, depth > 1 && HIGHLIGHT, 'w-full', collapsible && 'pe-10')}
        style={offset}
      >
        {item.icon}
        {item.name}
      </SidebarItem>
      {collapsible ? (
        <SidebarFolderTrigger
          aria-labelledby={`${labelId} ${hintId}`}
          className={cn(ITEM, BUTTON, 'absolute inset-e-0 inset-y-0 justify-center px-2')}
        >
          <span id={hintId} className="sr-only">
            {SIDEBAR_TOGGLE_HINT[localeFromPathname(pathname)]}
          </span>
        </SidebarFolderTrigger>
      ) : null}
    </div>
  );
}

// Radix removes a closed list from the page, which leaves the button's
// `aria-controls` pointing at nothing. `forceMount` keeps the list mounted; it
// also keeps Radix from hiding it, so the closed state sets `hidden` here.
function FolderList({ depth, children }: { depth: number; children: ReactNode }) {
  const open = useFolder()?.open ?? true;
  return (
    <SidebarFolderContent
      forceMount
      hidden={!open}
      className={cn(
        'relative',
        depth === 1 &&
          "before:content-[''] before:absolute before:w-px before:inset-y-1 before:bg-fd-border before:inset-s-2.5",
      )}
    >
      <div className="flex flex-col gap-0.5 pt-0.5">{children}</div>
    </SidebarFolderContent>
  );
}

export function DisclosureFolder({ item, children }: { item: Folder; children: ReactNode }) {
  const path = useTreePath();
  const depth = useFolderDepth() + 1;
  return (
    <SidebarFolder
      collapsible={item.collapsible}
      active={path.includes(item)}
      defaultOpen={item.defaultOpen}
    >
      <FolderHeader item={item} />
      <FolderList depth={depth}>{children}</FolderList>
    </SidebarFolder>
  );
}
