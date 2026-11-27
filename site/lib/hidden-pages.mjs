// SPDX-License-Identifier: MIT

/**
 * Root docs pages that exist but are left out of the sidebar on purpose.
 *
 * The one list both sides read: `scripts/author-ia.mjs` leaves these keys out
 * of the root meta.json (and accepts them in its drift guard), and the docs
 * routes turn off the previous/next footer on these pages through
 * `isHiddenFromSidebar` in `lib/page-tree.ts`, since a page outside the sidebar
 * order has no neighbours. The 404 page is the not-found fallback: the sitemap
 * and llms.txt leave it out too.
 *
 * @type {readonly string[]}
 */
export const HIDDEN_ROOT_PAGES = Object.freeze(['404']);
