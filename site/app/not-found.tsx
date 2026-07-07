// SPDX-License-Identifier: MIT

import Link from 'next/link';
import { ArrowLeft, BookOpen } from 'lucide-react';
import pkg from '@/package.json';
import { Button } from '@/components/ui/button';
import { BrandMark } from '@/components/brand-mark';
import { LandingNav } from '@/components/landing-nav';
import { LandingFooter } from '@/components/landing-footer';

/**
 * Branded 404 surface. The Next.js default not-found page is an unstyled
 * "This page could not be found." with no navigation; this replaces it with
 * the site's own nav, brand mark, and recovery links so a missed URL stays
 * on-brand and navigable.
 */
export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col">
      <LandingNav />

      <main
        id="main-content"
        className="relative flex flex-1 items-center overflow-hidden"
      >
        <div
          aria-hidden
          className="apothem-grid pointer-events-none absolute inset-0"
        />
        <div className="relative mx-auto flex max-w-2xl flex-col items-center gap-8 px-4 py-24 text-center sm:px-6 sm:py-32">
          <div className="relative flex items-center justify-center">
            <div
              aria-hidden
              className="apothem-glow pointer-events-none absolute -inset-12 -z-10"
            />
            <BrandMark size={96} />
          </div>

          <div className="flex flex-col items-center gap-3">
            <p className="font-mono text-sm tracking-wide text-[var(--primary)]">
              404
            </p>
            <h1 className="text-balance text-4xl font-bold tracking-tight sm:text-5xl">
              This page is off the lattice
            </h1>
            <p className="max-w-md text-pretty text-[var(--muted-foreground)]">
              The page you asked for is not here. Head back to the start or
              browse the documentation to find your way.
            </p>
          </div>

          <div className="flex flex-col items-center gap-3 sm:flex-row">
            <Button asChild size="lg">
              <Link href="/">
                <ArrowLeft className="size-4" />
                Back to home
              </Link>
            </Button>
            <Button asChild size="lg" variant="outline">
              <Link href="/docs">
                <BookOpen className="size-4" />
                Browse the docs
              </Link>
            </Button>
          </div>
        </div>
      </main>

      <LandingFooter version={pkg.version} />
    </div>
  );
}
