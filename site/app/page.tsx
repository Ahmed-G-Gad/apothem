// SPDX-License-Identifier: MIT

import Link from 'next/link';
import { ArrowRight, BookOpen, Terminal } from 'lucide-react';
import pkg from '@/package.json';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { AnimatedMark } from '@/components/animated-mark';
import { HeroBadges } from '@/components/hero-badges';
import { CommandBlock } from '@/components/command-block';
import { FeatureGrid } from '@/components/feature-grid';
import { FeatureMatrix } from '@/components/feature-matrix';
import { LandingNav } from '@/components/landing-nav';
import { LandingFooter } from '@/components/landing-footer';

// Supported harnesses, named in a supported-tools context.
const supportedTools = [
  'Claude Code',
  'Cursor',
  'Gemini CLI',
  'GitHub Copilot',
  'Codex',
  'Windsurf',
  'Zed',
  'OpenCode',
  'Qwen Code',
  'Kiro',
  'Trae',
  'CodeBuddy',
  'Antigravity',
  'Hermes',
  'Open-Claw',
  'Kimi Code',
  'GLM (Z.ai)',
];

const installLines = [
  {
    comment: '# Claude Code plugin (inside Claude Code)',
    cmd: '/plugin marketplace add ahmed-g-gad/apothem',
  },
  {
    comment: '# npx — any machine with Node and Python 3.10+',
    cmd: 'npx @ahmed-g-gad/apothem quickstart',
  },
  {
    comment: '# one-shot installer (POSIX)',
    cmd: 'curl -fsSL https://apothem.ahmedgad.com/install.sh | bash',
  },
];

export default function HomePage() {
  // Version is read from the package manifest at build time — never a literal.
  const version = pkg.version;

  return (
    <div className="flex min-h-screen flex-col">
      <LandingNav />

      <main id="main-content" className="flex-1">
        {/* Hero */}
        <section className="relative overflow-hidden">
          <div
            aria-hidden
            className="apothem-grid pointer-events-none absolute inset-0"
          />
          <div className="relative mx-auto flex max-w-3xl flex-col items-center gap-8 px-4 pt-24 pb-20 text-center sm:px-6 sm:pt-32 sm:pb-24">
            {/* Focal point: animated mark over a soft emerald bloom. */}
            <div className="relative flex items-center justify-center">
              <div
                aria-hidden
                className="apothem-glow pointer-events-none absolute -inset-16 -z-10"
              />
              <AnimatedMark size={132} className="drop-shadow-sm" />
            </div>

            <div className="flex flex-col items-center gap-5">
              <Badge variant="accent" className="font-mono">
                One profile · seventeen harnesses
              </Badge>
              <h1 className="text-balance text-5xl font-bold tracking-tight sm:text-7xl">
                Apothem
              </h1>
              <p className="text-balance text-xl font-medium tracking-tight text-[var(--foreground)] sm:text-2xl">
                One profile, every harness.
              </p>
              <p className="max-w-2xl text-pretty text-lg leading-relaxed text-[var(--muted-foreground)]">
                Write your rules, skills, hooks, and commands once in a single
                shared profile — Apothem renders them into the native
                configuration of seventeen harnesses, each in the exact format
                that tool reads.
              </p>
            </div>

            <HeroBadges />

            <div className="flex flex-col items-center gap-3 sm:flex-row">
              <Button asChild size="lg">
                <Link href="/docs/install">
                  <Terminal className="size-4" />
                  Install Apothem
                  <ArrowRight className="size-4" />
                </Link>
              </Button>
              <Button asChild size="lg" variant="outline">
                <Link href="/docs/install/quickstart">
                  <BookOpen className="size-4" />
                  Quickstart
                </Link>
              </Button>
            </div>

            <CommandBlock lines={installLines} className="mt-4 w-full" />
          </div>
        </section>

        {/* Supported tools strip */}
        <section className="border-y border-[var(--border)] bg-[var(--muted)]/30">
          <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
            <p
              id="supported-tools-label"
              className="mb-4 text-center text-xs font-medium tracking-wide text-[var(--muted-foreground)] uppercase"
            >
              Renders native config for
            </p>
            <ul
              aria-labelledby="supported-tools-label"
              className="flex flex-wrap items-center justify-center gap-x-6 gap-y-2"
            >
              {supportedTools.map((t) => (
                <li
                  key={t}
                  className="text-sm font-medium text-[var(--muted-foreground)]"
                >
                  {t}
                </li>
              ))}
            </ul>
          </div>
        </section>

        {/* Features */}
        <section className="mx-auto max-w-6xl px-4 py-20 sm:px-6">
          <div className="mx-auto mb-12 max-w-2xl text-center">
            <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
              One source of truth, kept honest
            </h2>
            <p className="mt-3 text-[var(--muted-foreground)]">
              The synced unit is wider than rules alone, and the discipline to
              keep it correct ships in the box.
            </p>
            <div className="apothem-rule mx-auto mt-6 w-24" />
          </div>
          <FeatureGrid />
        </section>

        {/* Differentiation matrix */}
        <section className="border-t border-[var(--border)] bg-[var(--muted)]/20">
          <div className="mx-auto max-w-5xl px-4 py-20 sm:px-6">
            <div className="mx-auto mb-12 max-w-2xl text-center">
              <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
                How Apothem compares
              </h2>
              <p className="mt-3 text-[var(--muted-foreground)]">
                The category is contested, not empty. Here is where Apothem
                sits against the tools operators reach for first.
              </p>
            </div>
            <FeatureMatrix />
            <div className="mt-6 text-center">
              <Button asChild variant="ghost">
                <Link href="/docs/comparison">
                  See the full comparison
                  <ArrowRight className="size-4" />
                </Link>
              </Button>
            </div>
          </div>
        </section>

        {/* Closing CTA */}
        <section className="mx-auto max-w-3xl px-4 py-20 text-center sm:px-6 sm:py-24">
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
            Configure once. Carry it everywhere.
          </h2>
          <div className="apothem-rule mx-auto mt-6 w-24" />
          <p className="mx-auto mt-6 max-w-xl text-[var(--muted-foreground)]">
            Install in one command and preview every file each tool will write
            before anything lands.
          </p>
          <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Button asChild size="lg">
              <Link href="/docs/install/quickstart">
                <Terminal className="size-4" />
                Run the quickstart
              </Link>
            </Button>
            <Button asChild size="lg" variant="outline">
              <Link href="/docs/comparison">Compare alternatives</Link>
            </Button>
          </div>
        </section>
      </main>

      <LandingFooter version={version} />
    </div>
  );
}
