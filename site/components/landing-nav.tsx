// SPDX-License-Identifier: MIT

'use client';

import * as React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Menu, X } from 'lucide-react';
import { BrandMark } from '@/components/brand-mark';
import { GithubIcon } from '@/components/github-icon';
import { ThemeToggle } from '@/components/theme-toggle';
import { LocaleSwitcher } from '@/components/locale-switcher';

const REPO_URL = 'https://github.com/ahmed-g-gad/apothem';

const navLinks = [
  { label: 'Install', href: '/docs/install' },
  { label: 'Docs', href: '/docs' },
  { label: 'Comparison', href: '/docs/comparison' },
  { label: 'Changelog', href: '/docs/changelog' },
];

export function LandingNav() {
  const pathname = usePathname();
  const [open, setOpen] = React.useState(false);

  // Close the mobile sheet on route change so a tapped link does not leave the
  // panel open over the destination.
  React.useEffect(() => {
    setOpen(false);
  }, [pathname]);

  return (
    <header className="sticky top-0 z-40 w-full border-b border-[var(--border)] bg-[color-mix(in_oklch,var(--background)_85%,transparent)] backdrop-blur">
      <nav
        aria-label="Primary"
        className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4 sm:px-6"
      >
        <Link
          href="/"
          aria-current={pathname === '/' ? 'page' : undefined}
          className="flex items-center gap-2 font-semibold"
        >
          <BrandMark size={26} decorative />
          <span className="tracking-tight">Apothem</span>
        </Link>

        <div className="flex items-center gap-1 sm:gap-2">
          <ul className="hidden items-center gap-1 sm:flex">
            {navLinks.map((l) => {
              const active =
                pathname === l.href || pathname.startsWith(`${l.href}/`);
              return (
                <li key={l.label}>
                  <Link
                    href={l.href}
                    aria-current={active ? 'page' : undefined}
                    className="rounded-md px-3 py-2 text-sm text-[var(--muted-foreground)] transition-colors hover:text-[var(--foreground)] aria-[current=page]:text-[var(--foreground)]"
                  >
                    {l.label}
                  </Link>
                </li>
              );
            })}
          </ul>
          <LocaleSwitcher />
          <ThemeToggle />
          <a
            href={REPO_URL}
            target="_blank"
            rel="noreferrer"
            aria-label="Apothem on GitHub"
            className="inline-flex size-11 items-center justify-center rounded-md text-[var(--muted-foreground)] transition-colors hover:bg-[var(--muted)] hover:text-[var(--foreground)] sm:size-9"
          >
            <GithubIcon className="size-5" />
          </a>

          {/* Mobile menu trigger — surfaces the primary nav below the `sm`
              breakpoint, where the inline link row is hidden. The 44px target
              clears the WCAG 2.5.8 minimum. */}
          <button
            type="button"
            aria-label={open ? 'Close menu' : 'Open menu'}
            aria-expanded={open}
            aria-controls="mobile-nav"
            onClick={() => setOpen((v) => !v)}
            className="inline-flex size-11 items-center justify-center rounded-md text-[var(--muted-foreground)] transition-colors hover:bg-[var(--muted)] hover:text-[var(--foreground)] sm:hidden"
          >
            {open ? (
              <X className="size-5" aria-hidden />
            ) : (
              <Menu className="size-5" aria-hidden />
            )}
          </button>
        </div>
      </nav>

      {/* Mobile nav sheet. Rendered as a collapsible region below the bar so
          the primary links stay reachable on phones; hidden at `sm`+. */}
      {open ? (
        <nav
          id="mobile-nav"
          aria-label="Primary"
          className="border-t border-[var(--border)] bg-[var(--background)] sm:hidden"
        >
          <ul className="mx-auto flex max-w-6xl flex-col gap-1 px-4 py-3">
            {navLinks.map((l) => {
              const active =
                pathname === l.href || pathname.startsWith(`${l.href}/`);
              return (
                <li key={l.label}>
                  <Link
                    href={l.href}
                    aria-current={active ? 'page' : undefined}
                    className="flex min-h-11 items-center rounded-md px-3 text-sm font-medium text-[var(--muted-foreground)] transition-colors hover:bg-[var(--muted)] hover:text-[var(--foreground)] aria-[current=page]:bg-[var(--muted)] aria-[current=page]:text-[var(--foreground)]"
                  >
                    {l.label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
      ) : null}
    </header>
  );
}
