// SPDX-License-Identifier: MIT

/**
 * Keeps a reader in their language when they follow a link in the body of a
 * translated docs page.
 *
 * A body link is written once, as `/docs/<page>` or `/docs/<page>#<id>`, and the
 * English and translated sources carry the same target. Nothing in the content
 * pipeline adds a locale prefix, so without this step every such link on a
 * translated page opens the English page. `localizeDocsHref` is the step: on a
 * page served in `lang` it turns the link into the language's own copy of the
 * target when the language has one, and leaves it alone otherwise.
 *
 * A heading's id is a slug of that page's own heading text, so a translated page
 * has translated ids. The fragment in a link is the English id (the guard in
 * `scripts/dev/check_site_anchor_links.py` requires it), so it is mapped to the
 * translated page's id by the heading's position: both pages list their headings
 * in the same order when they have the same structure.
 *
 * This module is pure so `node --test` can load it. The loader lookup and the
 * React wrapper that use it are in `components/localized-link.tsx`.
 */

/** One heading in a page's table of contents: its `#id` and its level. */
export interface TocEntry {
  readonly url: string;
  readonly depth: number;
}

/** A docs page as the localizer needs to see it. */
export interface DocsPage {
  /** The URL the site serves the page at, locale prefix included. */
  readonly url: string;
  /**
   * True when the language has its own copy. False when the loader served the
   * English page for it (`fallbackLanguage`), which carries the requested
   * language's URL all the same.
   */
  readonly authored: boolean;
  readonly toc: readonly TocEntry[];
}

/** Finds the page at `slug` in `lang`, as the content loader's `getPage` does. */
export type PageLookup = (slug: readonly string[], lang: string) => DocsPage | undefined;

// `/docs` itself, or `/docs` followed by a path, a query or a fragment.
const DOCS_HREF = /^\/docs(?:[/?#]|$)/;

function decode(text: string): string {
  try {
    return decodeURIComponent(text);
  } catch {
    return text;
  }
}

/**
 * The id of the translated page's heading that sits where `fragment`'s heading
 * sits on the English page, or `undefined` when the two pages cannot be lined
 * up: the English page has no such heading, or the two pages do not have the
 * same headings at the same levels.
 */
function translatedFragment(
  fragment: string,
  english: DocsPage | undefined,
  translated: DocsPage,
): string | undefined {
  if (english === undefined || english.toc.length !== translated.toc.length) return undefined;
  const wanted = decode(fragment);
  const position = english.toc.findIndex((entry) => decode(entry.url.slice(1)) === wanted);
  if (position === -1) return undefined;
  const sameStructure = english.toc.every((entry, index) => entry.depth === translated.toc[index].depth);
  return sameStructure ? translated.toc[position].url.slice(1) : undefined;
}

/**
 * The href to render for a body link on a page served in `lang`.
 *
 * - A link that is not a `/docs` link is returned as it is.
 * - A `/docs/<page>` link becomes the language's own page when it has one (its
 *   URL carries the locale prefix) and stays on the English page when it does not.
 * - With a `#fragment`, the fragment becomes the translated heading's id. When
 *   the pages cannot be lined up the link stays on the English page, where the
 *   English id it carries is valid.
 */
export function localizeDocsHref(
  href: string,
  lang: string,
  defaultLang: string,
  lookup: PageLookup,
): string {
  if (!DOCS_HREF.test(href)) return href;
  const hashAt = href.indexOf('#');
  const fragment = hashAt === -1 ? '' : href.slice(hashAt + 1);
  const target = hashAt === -1 ? href : href.slice(0, hashAt);
  const queryAt = target.indexOf('?');
  const path = queryAt === -1 ? target : target.slice(0, queryAt);
  const query = queryAt === -1 ? '' : target.slice(queryAt);
  const slug = path.split('/').slice(2).filter((segment) => segment !== '');

  const translated = lookup(slug, lang);
  if (translated === undefined || !translated.authored) return href;
  if (fragment === '') return `${translated.url}${query}`;
  const id = translatedFragment(fragment, lookup(slug, defaultLang), translated);
  return id === undefined ? href : `${translated.url}${query}#${id}`;
}
