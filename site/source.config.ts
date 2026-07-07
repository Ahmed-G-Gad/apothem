// SPDX-License-Identifier: MIT

import { defineDocs, defineConfig, frontmatterSchema } from 'fumadocs-mdx/config';
import { z } from 'zod';

// The docs collection extends the default Fumadocs page frontmatter schema with
// one custom field, `machineTranslated`. The default schema strips unknown
// frontmatter keys, so the flag must be admitted here for it to survive parsing.
//
// `machineTranslated: true` is internal review-tracking metadata: it marks a
// locale page whose translation has not yet been human-reviewed, so a later
// review pass can locate the pending pages. It drives no rendered surface — the
// docs route renders page content only — and is optional (absent = reviewed), so
// pages without it are unaffected.
export const docs = defineDocs({
  dir: 'content/docs',
  docs: {
    schema: frontmatterSchema.extend({
      machineTranslated: z.boolean().optional(),
    }),
  },
});

export default defineConfig();
