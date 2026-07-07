// SPDX-License-Identifier: MIT

import { docs } from '@/.source/server';
import { loader } from 'fumadocs-core/source';
import { i18n } from '@/lib/i18n';

// The content loader is i18n-aware: passing the i18n config makes `pageTree` a
// per-language map, `getPage`/`generateParams` accept a language argument, and
// generated URLs honor `hideLocale: 'default-locale'` (English keeps its
// existing root `/docs/...` URLs; Spanish is served under `/es/docs/...`).
export const source = loader({
  baseUrl: '/docs',
  i18n,
  source: docs.toFumadocsSource(),
});
