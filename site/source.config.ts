// SPDX-License-Identifier: MIT

import { defineDocs, defineConfig, frontmatterSchema } from 'fumadocs-mdx/config';
import { z } from 'zod';
import { CODE_COLOR_REPLACEMENTS } from './lib/code-theme.mjs';

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

// Code blocks keep the Fumadocs default github-light / github-dark themes
// (named again here because the option type requires them); the colour
// replacements lift the token colours that fail WCAG 1.4.3 contrast on the
// code-block surfaces (see lib/code-theme.mjs). The options merge over the
// Fumadocs defaults, so the transformers and dual-theme CSS variables are
// unchanged.
export default defineConfig({
  mdxOptions: {
    rehypeCodeOptions: {
      themes: { light: 'github-light', dark: 'github-dark' },
      colorReplacements: CODE_COLOR_REPLACEMENTS,
    },
  },
});
