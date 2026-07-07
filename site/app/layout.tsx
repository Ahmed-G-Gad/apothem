// SPDX-License-Identifier: MIT

import './global.css';
import type { ReactNode } from 'react';
import type { Metadata, Viewport } from 'next';
import { SITE_URL, DEFAULT_LOCALE, COHORT_LOCALES } from '@/lib/i18n';
import { buildAlternates } from '@/lib/hreflang';
import { SiteProviders } from '@/components/site-providers';

// The site is a single-root-layout static export, so `<html>` is rendered once
// here for every locale's pages and cannot read a `[lang]` route param. The
// static markup is post-processed per output path by `export-to-dist.mjs` to
// bake the correct `lang`/`dir` into each locale's HTML files. This inline
// head script complements that at runtime: it derives the active locale from
// the URL path against the cohort table and sets `documentElement.lang`/`dir`
// before paint — so client-side navigation into (and within) the RTL locale
// flips direction with no flash, and LTR locales stay `ltr`. The locale →
// (lang, dir) pairs are projected from COHORT_LOCALES so this script never
// diverges from the single i18n source of truth.
const LOCALE_DIR_SCRIPT = `(function(){try{var P=${JSON.stringify(
  COHORT_LOCALES.filter((l) => l.path).map((l) => [l.path, l.code, l.dir]),
)};var s=location.pathname.split('/').filter(Boolean);var seg=s[0];var lang='${DEFAULT_LOCALE}',dir='ltr';for(var i=0;i<P.length;i++){if(P[i][0]===seg){lang=P[i][1];dir=P[i][2];break;}}var e=document.documentElement;e.lang=lang;e.dir=dir;}catch(_){}})();`;

// In Next 14+, `themeColor` belongs in the `viewport` export, not `metadata`.
// The pair tracks the site's light/dark backgrounds so the browser UI (mobile
// address bar, PWA chrome) blends with the page rather than flashing a default.
export const viewport: Viewport = {
  themeColor: [
    { media: '(prefers-color-scheme: light)', color: '#fcfcfd' },
    { media: '(prefers-color-scheme: dark)', color: '#0f172a' },
  ],
};

export const metadata: Metadata = {
  // Absolute base for canonical and hreflang alternate URLs.
  metadataBase: new URL(SITE_URL),
  // Wires the PWA web app manifest (public/manifest.json) into the document
  // head so the install/theme metadata is discoverable.
  manifest: '/manifest.json',
  title: {
    default: 'Apothem',
    template: '%s — Apothem',
  },
  description:
    'A host-agnostic configuration manager for your assistant harnesses. One shared profile, rendered into every tool’s native configuration.',
  // hreflang set for the landing page. The landing route resolves for every
  // routed locale, so buildAlternates('/') emits the full cohort cluster — the
  // `en` self-link, `x-default`, and one alternate per routed non-default
  // locale (see lib/i18n.ts + lib/hreflang.ts).
  alternates: buildAlternates('/'),
  // Social-share cards. Per-page metadata (generateMetadata in the docs
  // route) inherits these defaults and overrides title/description.
  openGraph: {
    type: 'website',
    siteName: 'Apothem',
    url: SITE_URL,
    title: 'Apothem',
    description:
      'A host-agnostic configuration manager for your assistant harnesses. One shared profile, rendered into every tool’s native configuration.',
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
    title: 'Apothem',
    description:
      'A host-agnostic configuration manager for your assistant harnesses. One shared profile, rendered into every tool’s native configuration.',
    images: ['/twitter-card.png'],
  },
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" dir="ltr" suppressHydrationWarning>
      <head>
        {/* Set per-locale lang/dir before paint from the URL path, so RTL (ar)
            flips direction with no flash on first paint and on client nav. The
            static files are additionally baked per-locale by export-to-dist. */}
        <script dangerouslySetInnerHTML={{ __html: LOCALE_DIR_SCRIPT }} />
      </head>
      <body className="flex min-h-screen flex-col">
        <a
          href="#main-content"
          className="sr-only z-50 rounded-md bg-[var(--primary)] px-4 py-2 text-sm font-medium text-[var(--primary-foreground)] focus-visible:not-sr-only focus-visible:absolute focus-visible:inset-inline-start-4 focus-visible:top-4"
        >
          Skip to content
        </a>
        <SiteProviders currentLocale={DEFAULT_LOCALE}>
          {children}
        </SiteProviders>
      </body>
    </html>
  );
}
