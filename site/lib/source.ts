// SPDX-License-Identifier: MIT

import { docs } from '@/.source/server';
import { loader } from 'fumadocs-core/source';
import { i18n } from '@/lib/i18n';
import { flattenIndexOnlyFolders } from '@/lib/page-tree';

// The content loader is i18n-aware: passing the i18n config makes `pageTree` a
// per-language map, `getPage`/`generateParams` accept a language argument, and
// generated URLs honor `hideLocale: 'default-locale'` (English keeps its
// existing root `/docs/...` URLs; Spanish is served under `/es/docs/...`).
export const source = loader({
  baseUrl: '/docs',
  i18n,
  source: docs.toFumadocsSource(),
  // A section whose only page is its overview shows as one plain link rather
  // than a folder with a chevron over an empty list (see lib/page-tree.ts).
  pageTree: {
    transformers: [{ root: flattenIndexOnlyFolders }],
  },
});
