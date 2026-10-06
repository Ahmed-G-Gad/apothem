// SPDX-License-Identifier: MIT

import { source } from '@/lib/source';
import { DocsBody, DocsDescription, DocsTitle } from 'fumadocs-ui/page';
import { LandmarkDocsPage } from '@/components/docs-landmarks';
import { notFound } from 'next/navigation';
import { getMDXComponents } from '@/mdx-components';
import { buildAlternates } from '@/lib/hreflang';
import { ROUTED_NON_DEFAULT_LOCALES, DEFAULT_LOCALE } from '@/lib/i18n';
import { translationState } from '@/lib/translation-status';
import { StaleTranslationNotice } from '@/components/stale-translation-notice';
import type { Metadata } from 'next';

// Per-locale docs route (e.g. Spanish at `/es/docs/...`). Pages are resolved for
// the route's locale; every English page is authored in every routed locale, so
// each route renders that locale's own translation. The loader's
// `fallbackLanguage: 'en'` remains the safety net for any page a locale has not
// authored. The `machineTranslated` frontmatter flag is internal review-tracking
// metadata only — it drives no rendered surface. The `sourceHash` flag drives
// the staleness marker (see lib/translation-status.ts).
export default async function Page(props: {
  params: Promise<{ lang: string; slug?: string[] }>;
}) {
  const { lang, slug } = await props.params;
  const page = source.getPage(slug, lang);
  if (!page) notFound();

  const MDXContent = page.data.body;
  // A translation whose English source changed after it was made carries a
  // staleness marker. An untranslated page is the English fallback: it is
  // served silently, but its text is marked English (WCAG 3.1.2).
  const state = translationState(page.path, lang, page.data.sourceHash);
  const english = state === 'fallback' ? { lang: DEFAULT_LOCALE, dir: 'ltr' as const } : {};

  return (
    <LandmarkDocsPage toc={page.data.toc} full={page.data.full}>
      <DocsTitle {...english}>{page.data.title}</DocsTitle>
      {state === 'stale' ? (
        <StaleTranslationNotice englishUrl={page.url.replace(`/${lang}/`, '/')} />
      ) : null}
      <DocsDescription {...english}>{page.data.description}</DocsDescription>
      <DocsBody {...english}>
        <MDXContent components={getMDXComponents()} />
      </DocsBody>
    </LandmarkDocsPage>
  );
}

export function generateStaticParams() {
  // Emit the FULL English page set for every routed non-default locale so each
  // locale is navigable across the whole site. Every English page is authored in
  // every routed locale, so each generated route renders that locale's own
  // translation; the loader's `fallbackLanguage: 'en'` remains the safety net for
  // any page a locale has not authored. The sitemap and hreflang sets are derived
  // per-file from authored content (`authoredSlugs`), so only genuine
  // translations are advertised to search engines.
  const englishSlugs = source
    .generateParams('slug', 'lang')
    .filter((param) => param.lang === DEFAULT_LOCALE)
    .map(({ slug }) => slug);

  return ROUTED_NON_DEFAULT_LOCALES.flatMap((lang) =>
    englishSlugs.map((slug) => ({ lang, slug })),
  );
}

export async function generateMetadata(props: {
  params: Promise<{ lang: string; slug?: string[] }>;
}): Promise<Metadata> {
  const { lang, slug } = await props.params;
  const page = source.getPage(slug, lang);
  if (!page) notFound();

  const title = page.data.title;
  const description = page.data.description;

  return {
    title,
    description,
    // page.url is the locale-prefixed path for non-default locales (e.g.
    // /es/docs/install); buildAlternates derives the locale-agnostic path and
    // emits the symmetric hreflang set (en self-link + x-default + es).
    alternates: buildAlternates(page.url),
    openGraph: {
      type: 'website',
      siteName: 'Apothem',
      title,
      description,
      url: page.url,
      images: [
        {
          url: '/og-banner-1200x630.png',
          width: 1200,
          height: 630,
          alt: 'Apothem — one profile, seventeen harnesses',
        },
      ],
    },
    twitter: {
      card: 'summary_large_image',
      title,
      description,
      images: ['/twitter-card.png'],
    },
  };
}
