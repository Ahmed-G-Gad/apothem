// SPDX-License-Identifier: MIT

import type { Folder, Node, Root } from 'fumadocs-core/page-tree';

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
 * Whether a docs page is left out of the sidebar on purpose. Only the 404 page
 * is (see HIDDEN_ROOT_PAGES in `scripts/author-ia.mjs`). A hidden page has no
 * previous or next page in the sidebar order, so the docs routes turn its
 * previous/next footer off rather than render an empty footer grid.
 */
export function isHiddenFromSidebar(slugs: readonly string[]): boolean {
  return slugs.length === 1 && slugs[0] === '404';
}

function flattenNodes(nodes: Node[]): Node[] {
  return nodes.map((node) => {
    if (node.type !== 'folder') return node;
    const folder: Folder = { ...node, children: flattenNodes(node.children) };
    return folder.children.length === 0 && folder.index ? folder.index : folder;
  });
}
