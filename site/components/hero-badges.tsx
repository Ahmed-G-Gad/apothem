// SPDX-License-Identifier: MIT

/**
 * Hero badge row. Each badge is a shields.io endpoint that resolves its value
 * live against the upstream service (GitHub Actions, npm, Codecov, OSSF
 * Scorecard) at request time — no value is baked into source, so the row
 * stays current without a code change. The version and downloads badges read
 * the published npm package coordinates, never a literal version string.
 */

const REPO = 'ahmed-g-gad/apothem';
// npm-scoped package name, URL-encoded for shields.io (@ -> %40, / -> %2F).
const NPM_PKG = '%40ahmed-g-gad%2Fapothem';
const NPM_URL = 'https://www.npmjs.com/package/@ahmed-g-gad/apothem';
const STYLE = 'flat-square';

type BadgeLink = {
  label: string;
  /** shields.io image URL — value resolved live by shields/upstream. */
  img: string;
  href: string;
  alt: string;
};

const badges: BadgeLink[] = [
  {
    label: 'Build',
    img: `https://img.shields.io/github/actions/workflow/status/${REPO}/ci.yml?style=${STYLE}&label=build&labelColor=0f172a&color=059669`,
    href: `https://github.com/${REPO}/actions`,
    alt: 'Build status',
  },
  {
    label: 'License',
    img: `https://img.shields.io/github/license/${REPO}?style=${STYLE}&labelColor=0f172a&color=059669`,
    href: `https://github.com/${REPO}/blob/main/LICENSE`,
    alt: 'License: MIT',
  },
  {
    label: 'Version',
    img: `https://img.shields.io/npm/v/${NPM_PKG}?style=${STYLE}&labelColor=0f172a&color=059669&label=npm`,
    href: NPM_URL,
    alt: 'Latest published version',
  },
  {
    label: 'Coverage',
    img: `https://img.shields.io/codecov/c/github/${REPO}?style=${STYLE}&labelColor=0f172a&color=059669`,
    href: `https://app.codecov.io/gh/${REPO}`,
    alt: 'Test coverage',
  },
  {
    label: 'Scorecard',
    img: `https://img.shields.io/ossf-scorecard/github.com/${REPO}?style=${STYLE}&labelColor=0f172a&color=059669&label=scorecard`,
    href: `https://scorecard.dev/viewer/?uri=github.com/${REPO}`,
    alt: 'OSSF Scorecard',
  },
  {
    label: 'Docs',
    img: `https://img.shields.io/badge/docs-apothem.ahmedgad.com-059669?style=${STYLE}&labelColor=0f172a`,
    href: '/docs',
    alt: 'Documentation',
  },
  {
    label: 'Downloads',
    img: `https://img.shields.io/npm/dm/${NPM_PKG}?style=${STYLE}&labelColor=0f172a&color=059669&label=downloads`,
    href: NPM_URL,
    alt: 'Monthly downloads',
  },
];

export function HeroBadges() {
  return (
    <div className="flex flex-wrap items-center justify-center gap-2">
      {badges.map((b) => (
        <a
          key={b.label}
          href={b.href}
          target={b.href.startsWith('/') ? undefined : '_blank'}
          rel={b.href.startsWith('/') ? undefined : 'noreferrer'}
          /* min-h/py give the 20px-tall badge image a ≥24px touch target
             (WCAG 2.5.8); rounded-sm shapes the keyboard focus ring. */
          className="inline-flex min-h-6 items-center rounded-sm py-1 transition-opacity hover:opacity-80"
        >
          {/* shields.io renders the live value as an SVG; native <img> keeps
              it static-export friendly and unproxied. */}
          <img
            src={b.img}
            alt={b.href.startsWith('/') ? b.alt : `${b.alt} (opens in new tab)`}
            height={20}
            className="h-5"
          />
        </a>
      ))}
    </div>
  );
}
