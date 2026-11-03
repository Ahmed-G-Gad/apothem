// SPDX-License-Identifier: MIT

import type { ComponentProps } from 'react';
import defaultMdxComponents from 'fumadocs-ui/mdx';
import { DEFAULT_LOCALE } from '@/lib/i18n';
import { isAuthoredPath, localizeDocsHref, type PageLookup } from '@/lib/locale-links';
import { source } from '@/lib/source';

const DefaultLink = defaultMdxComponents.a;

type LinkProps = ComponentProps<typeof DefaultLink>;

/**
 * The content loader as `localizeDocsHref` sees it. A page is the language's own
 * when its content file sits under `<lang>/` (`isAuthoredPath`, the test
 * `lib/translation-status.ts` uses too); for any other language the loader returns
 * the English page. The page's `url` cannot tell them apart: the loader builds it
 * from the requested language either way.
 */
const lookupPage: PageLookup = (slug, lang) => {
  const page = source.getPage([...slug], lang);
  if (page === undefined) return undefined;
  return {
    url: page.url,
    authored: lang === DEFAULT_LOCALE || isAuthoredPath(page.path, lang),
    toc: page.data.toc,
  };
};

const linksByLanguage = new Map<string, (props: LinkProps) => React.JSX.Element>();

/**
 * The MDX `a` component for pages served in `lang`: the default link, with a
 * `/docs/...` href pointed at the language's own copy of the page when it has
 * one. The `[lang]` docs route passes it to `getMDXComponents`.
 */
export function createLocalizedLink(lang: string): (props: LinkProps) => React.JSX.Element {
  let link = linksByLanguage.get(lang);
  if (link === undefined) {
    link = function LocalizedLink({ href, ...props }: LinkProps) {
      const target =
        typeof href === 'string' ? localizeDocsHref(href, lang, DEFAULT_LOCALE, lookupPage) : href;
      return <DefaultLink {...props} href={target} />;
    };
    linksByLanguage.set(lang, link);
  }
  return link;
}
