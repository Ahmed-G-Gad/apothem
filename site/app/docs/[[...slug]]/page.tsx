// SPDX-License-Identifier: MIT

import { source } from '@/lib/source';
import { DocsBody, DocsDescription, DocsTitle } from 'fumadocs-ui/page';
import { LandmarkDocsPage } from '@/components/docs-landmarks';
import { notFound } from 'next/navigation';
import { getMDXComponents } from '@/mdx-components';
import { buildAlternates } from '@/lib/hreflang';
import { DEFAULT_LOCALE } from '@/lib/i18n';
import type { Metadata } from 'next';

// English docs route. The source loader is now i18n-aware, so pages are
// resolved with an explicit language argument. English keeps its existing
// root URLs (`/docs/...`) — the `[lang]` segment under app/[lang]/docs handles
// the non-default locales (e.g. Spanish at `/es/docs/...`).
export default async function Page(props: {
  params: Promise<{ slug?: string[] }>;
}) {
  const params = await props.params;
  const page = source.getPage(params.slug, DEFAULT_LOCALE);
  if (!page) notFound();

  const MDXContent = page.data.body;

  return (
    <LandmarkDocsPage toc={page.data.toc} full={page.data.full}>
      <DocsTitle>{page.data.title}</DocsTitle>
      <DocsDescription>{page.data.description}</DocsDescription>
      <DocsBody>
        <MDXContent components={getMDXComponents()} />
      </DocsBody>
    </LandmarkDocsPage>
  );
}

export function generateStaticParams() {
  // Only the English (default) locale is emitted from this root route; the
  // generated params carry the `slug` only (no `lang`), so URLs stay at
  // `/docs/...` exactly as before i18n was wired.
  return source
    .generateParams('slug', 'lang')
    .filter((param) => param.lang === DEFAULT_LOCALE)
    .map(({ slug }) => ({ slug }));
}

export async function generateMetadata(props: {
  params: Promise<{ slug?: string[] }>;
}): Promise<Metadata> {
  const params = await props.params;
  const page = source.getPage(params.slug, DEFAULT_LOCALE);
  if (!page) notFound();

  const title = page.data.title;
  const description = page.data.description;

  return {
    title,
    description,
    // Per-page hreflang set. page.url is the locale-agnostic path (e.g.
    // /docs/install); buildAlternates emits the en self-link + x-default plus
    // one alternate per routed locale that carries a version of the page.
    alternates: buildAlternates(page.url),
    // Override the root social-card title/description per page so a shared
    // docs link previews with the page's own heading rather than the generic
    // site default. Next.js replaces (does not deep-merge) the parent
    // openGraph/twitter objects when a child provides them, so the shared
    // banner image and card type are re-declared here to keep the rich card.
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
