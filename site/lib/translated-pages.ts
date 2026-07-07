// SPDX-License-Identifier: MIT

import { readdirSync, statSync } from 'node:fs';
import { join, relative, sep } from 'node:path';

/**
 * Enumerate the slugs that have an *authored* translation for a given locale,
 * read directly from the content filesystem (`content/docs/<locale>/`).
 *
 * This is intentionally filesystem-driven rather than loader-driven: Fumadocs'
 * i18n loader merges each locale's storage with the English fallback, so
 * `source.generateParams()` for a routed locale would enumerate the *entire*
 * fallback tree (~190 pages) plus every authored translation, conflating the
 * two. Reading the content filesystem directly returns the complete set of
 * genuinely-authored pages for the locale — `authoredSlugs` yields the full
 * authored page set for every routed locale — so static params stay tied to
 * each locale's real translated surface rather than the fallback duplicates.
 *
 * The returned slugs are locale-agnostic (the `<locale>/` prefix and the
 * `.mdx`/`.md` extension are stripped, and an `index` file maps to its parent
 * directory's slug — `index.mdx` → `[]`, `install/index.mdx` →
 * `['install']`). This matches the slug shape Fumadocs' `getPage` /
 * `generateParams` expect.
 */
export function authoredSlugs(locale: string): string[][] {
  const contentRoot = join(process.cwd(), 'content', 'docs', locale);

  let entries: string[];
  try {
    entries = walk(contentRoot);
  } catch {
    // No content directory for this locale yet — no authored pages.
    return [];
  }

  const slugs: string[][] = [];
  for (const absPath of entries) {
    if (!/\.mdx?$/.test(absPath)) continue;
    const rel = relative(contentRoot, absPath);
    const withoutExt = rel.replace(/\.mdx?$/, '');
    const parts = withoutExt.split(sep).filter((p) => p.length > 0);
    // `index` files collapse to their parent directory's slug.
    if (parts[parts.length - 1] === 'index') parts.pop();
    slugs.push(parts);
  }
  return slugs;
}

/** Recursively list every file under `dir`. */
function walk(dir: string): string[] {
  const out: string[] = [];
  for (const name of readdirSync(dir)) {
    const full = join(dir, name);
    if (statSync(full).isDirectory()) {
      out.push(...walk(full));
    } else {
      out.push(full);
    }
  }
  return out;
}
