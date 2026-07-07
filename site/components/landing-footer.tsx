// SPDX-License-Identifier: MIT

import Link from 'next/link';
import { BrandMark } from '@/components/brand-mark';
import { GithubIcon } from '@/components/github-icon';

const REPO_URL = 'https://github.com/ahmed-g-gad/apothem';

const sections: { heading: string; links: { label: string; href: string }[] }[] =
  [
    {
      heading: 'Start',
      links: [
        { label: 'Install', href: '/docs/install' },
        { label: 'Quickstart', href: '/docs/install/quickstart' },
        { label: 'CLI reference', href: '/docs/cli-reference' },
      ],
    },
    {
      heading: 'Learn',
      links: [
        { label: 'Documentation', href: '/docs' },
        { label: 'Comparison', href: '/docs/comparison' },
        { label: 'Harnesses', href: '/docs/harnesses' },
      ],
    },
    {
      heading: 'Project',
      links: [
        { label: 'Changelog', href: '/docs/changelog' },
        { label: 'Community', href: '/docs/community' },
        { label: 'Security', href: '/docs/security' },
      ],
    },
  ];

export function LandingFooter({ version }: { version: string }) {
  return (
    <footer className="border-t border-[var(--border)]">
      <div className="mx-auto grid max-w-6xl gap-10 px-4 py-12 sm:px-6 md:grid-cols-[1.4fr_repeat(3,1fr)]">
        <div className="flex flex-col gap-3">
          <Link href="/" className="flex items-center gap-2 font-semibold">
            <BrandMark size={28} decorative />
            <span className="tracking-tight">Apothem</span>
          </Link>
          <p className="max-w-xs text-sm text-[var(--muted-foreground)]">
            One profile, every harness&apos;s native configuration.
          </p>
          <a
            href={REPO_URL}
            target="_blank"
            rel="noreferrer"
            className="inline-flex w-fit items-center gap-2 text-sm text-[var(--muted-foreground)] transition-colors hover:text-[var(--foreground)]"
          >
            <GithubIcon className="size-4" />
            ahmed-g-gad/apothem
          </a>
        </div>
        {sections.map((s) => (
          <div key={s.heading} className="flex flex-col gap-3">
            <h3 className="text-sm font-semibold text-[var(--foreground)]">
              {s.heading}
            </h3>
            <ul className="flex flex-col gap-2">
              {s.links.map((l) => (
                <li key={l.label}>
                  <Link
                    href={l.href}
                    className="text-sm text-[var(--muted-foreground)] transition-colors hover:text-[var(--foreground)]"
                  >
                    {l.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      <div className="border-t border-[var(--border)]">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-2 px-4 py-5 text-xs text-[var(--muted-foreground)] sm:flex-row sm:px-6">
          <span>
            &copy; {new Date().getFullYear()} Ahmed G. Gad. Released under the
            MIT License.
          </span>
          <span className="font-mono">v{version}</span>
        </div>
      </div>
    </footer>
  );
}
