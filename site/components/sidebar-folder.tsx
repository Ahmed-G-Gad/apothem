// SPDX-License-Identifier: MIT

'use client';

import {
  useId,
  useLayoutEffect,
  useRef,
  useState,
  type AnimationEvent,
  type ReactNode,
} from 'react';
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
 * `hidden` attribute once its close animation ends, so the button's
 * `aria-controls` always points at an element that exists. A folder without
 * an overview page keeps Fumadocs' own trigger, which is already a button.
 * The classes and offsets mirror Fumadocs' docs-layout sidebar
 * (`layouts/docs/slots/sidebar.js`) so the sidebar looks the same.
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

function FolderHeader({ item, listId }: { item: Folder; listId: string }) {
  const depth = useFolderDepth();
  const pathname = usePathname();
  const labelId = useId();
  const hintId = useId();
  const collapsible = item.collapsible ?? true;
  const offset = { paddingInlineStart: itemOffset(depth - 1) };

  if (!item.index) {
    return (
      <SidebarFolderTrigger
        aria-controls={collapsible ? listId : undefined}
        className={cn(ITEM, collapsible && BUTTON, 'w-full')}
        style={offset}
      >
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
          aria-controls={listId}
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

// Radix removes a closed list from the page and drops the button's
// `aria-controls` while it is closed. Here the list stays mounted
// (`forceMount`, which also stops Radix hiding it) under an id of our own, and
// the button always names that id. A closing list keeps showing until its
// collapse animation ends and only then gets `hidden`, so the close animates
// the same way the open does. When no animation runs (none is set), `hidden`
// is set at once. The site's reduced-motion rule keeps the animation but
// shortens it to 0.01 ms, so an animation that short is also treated as none
// and `hidden` is set at once rather than on the next `animationend`. A
// cancelled animation also settles the list, and a fallback timer sets
// `hidden` even when no animation event ever fires (a page whose animation
// timeline never advances, such as a background tab). The timer starts with
// the close, not with the animation (an animation that never starts sends no
// event), so it allows more than three times Fumadocs' 150 ms collapse for a
// busy main thread to finish the animation first. A list that starts closed
// is `hidden` in the server HTML.
const SETTLE_FALLBACK_MS = 500;

// The longest animation duration at or below which a closing list is treated
// as not animating: the 0.01 ms the reduced-motion rule sets.
const NO_ANIMATION_MS = 0.01;

// Whether a computed style runs a collapse animation worth waiting for. Each
// property may hold a comma-separated list, one entry per animation.
export function runsAnimation(style: { animationName: string; animationDuration: string }): boolean {
  const names = style.animationName.split(',').map((name) => name.trim());
  if (names.every((name) => !name || name === 'none')) return false;
  const longest = Math.max(
    0,
    ...style.animationDuration.split(',').map((entry) => {
      const value = entry.trim();
      const amount = Number.parseFloat(value);
      if (!Number.isFinite(amount)) return 0;
      return value.endsWith('ms') ? amount : amount * 1000;
    }),
  );
  return longest > NO_ANIMATION_MS;
}

function useHiddenAfterClose(open: boolean) {
  const ref = useRef<HTMLDivElement>(null);
  const [settled, setSettled] = useState(!open);
  if (open && settled) setSettled(false);

  useLayoutEffect(() => {
    // `ref` sits on the list's only child; the list is its parent.
    const node = ref.current?.parentElement;
    if (open || settled || !node) return;
    if (!runsAnimation(getComputedStyle(node))) {
      setSettled(true);
      return;
    }
    const settle = () => setSettled(true);
    // React has no `onAnimationCancel` prop, so listen on the list directly.
    const onCancel = (event: Event) => {
      if (event.target === node) settle();
    };
    node.addEventListener('animationcancel', onCancel);
    const timer = setTimeout(settle, SETTLE_FALLBACK_MS);
    return () => {
      node.removeEventListener('animationcancel', onCancel);
      clearTimeout(timer);
    };
  }, [open, settled]);

  const onAnimationEnd = (event: AnimationEvent<HTMLDivElement>) => {
    if (event.target === event.currentTarget && !open) setSettled(true);
  };

  return { ref, hidden: !open && settled, onAnimationEnd };
}

function FolderList({
  id,
  depth,
  children,
}: {
  id: string;
  depth: number;
  children: ReactNode;
}) {
  const open = useFolder()?.open ?? true;
  const { ref, hidden, onAnimationEnd } = useHiddenAfterClose(open);
  return (
    <SidebarFolderContent
      id={id}
      forceMount
      hidden={hidden}
      onAnimationEnd={onAnimationEnd}
      className={cn(
        'relative',
        depth === 1 &&
          "before:content-[''] before:absolute before:w-px before:inset-y-1 before:bg-fd-border before:inset-s-2.5",
      )}
    >
      <div ref={ref} className="flex flex-col gap-0.5 pt-0.5">
        {children}
      </div>
    </SidebarFolderContent>
  );
}

export function DisclosureFolder({ item, children }: { item: Folder; children: ReactNode }) {
  const path = useTreePath();
  const depth = useFolderDepth() + 1;
  const listId = useId();
  return (
    <SidebarFolder
      collapsible={item.collapsible}
      active={path.includes(item)}
      defaultOpen={item.defaultOpen}
    >
      <FolderHeader item={item} listId={listId} />
      <FolderList id={listId} depth={depth}>
        {children}
      </FolderList>
    </SidebarFolder>
  );
}
