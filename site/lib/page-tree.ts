// SPDX-License-Identifier: MIT

import type { Folder, Node, Root } from 'fumadocs-core/page-tree';
import { HIDDEN_ROOT_PAGES } from './hidden-pages.mjs';

/**
 * Sidebar page-tree clean-up applied by the content loader (`lib/source.ts`).
 *
 * The section `meta.json` lists leave the `index` page out, so a section's
 * folder title is the link to its overview page (see `scripts/author-ia.mjs`).
 * Fumadocs still builds a folder for a section whose only page is that index,
 * and draws it with an open/close chevron over an empty list. Such a folder is
 * shown as its index page instead: one plain link, no chevron.
 */
export function flattenIndexOnlyFolders(root: Root): Root {
  return {
    ...root,
    children: flattenNodes(root.children),
    ...(root.fallback ? { fallback: flattenIndexOnlyFolders(root.fallback) } : {}),
  };
}

/**
 * Whether a docs page is left out of the sidebar on purpose (the root pages in
 * `lib/hidden-pages.mjs`, the list `scripts/author-ia.mjs` also reads). A
 * hidden page has no previous or next page in the sidebar order, so the docs
 * routes turn its previous/next footer off rather than render an empty grid.
 */
export function isHiddenFromSidebar(slugs: readonly string[]): boolean {
  return slugs.length === 1 && HIDDEN_ROOT_PAGES.includes(slugs[0]);
}

function flattenNodes(nodes: Node[]): Node[] {
  return nodes.map((node) => {
    if (node.type !== 'folder') return node;
    const folder: Folder = { ...node, children: flattenNodes(node.children) };
    if (folder.children.length > 0 || !folder.index) return folder;
    // The section's own label (its meta.json title) and icon stay on the link,
    // so a translator's edit to the section title still shows in the sidebar.
    const icon = folder.icon ?? folder.index.icon;
    return { ...folder.index, name: folder.name, ...(icon === undefined ? {} : { icon }) };
  });
}
