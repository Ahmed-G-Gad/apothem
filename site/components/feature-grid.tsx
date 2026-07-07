// SPDX-License-Identifier: MIT

import {
  Boxes,
  ScrollText,
  Workflow,
  RotateCcw,
  ShieldCheck,
  BrainCircuit,
  Fingerprint,
  Layers,
  Eye,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';

/**
 * Landing feature section. Each card states one concrete capability backed by
 * a named command or surface — no claim without adjacent evidence.
 */

type Feature = {
  icon: LucideIcon;
  title: string;
  body: string;
};

const features: Feature[] = [
  {
    icon: Layers,
    title: 'One profile, seventeen harnesses',
    body: 'A single shared profile at ~/.config/apothem/profile.yaml renders into the native config of seventeen harnesses — each adapter writes the format that tool actually reads.',
  },
  {
    icon: Boxes,
    title: 'A governed synced unit',
    body: 'Rules, skills, hooks, slash-commands, and MCP servers travel together as one governed source — not rules alone, and not arbitrary files.',
  },
  {
    icon: ScrollText,
    title: 'A conformity gate that ships with it',
    body: 'Behavioral rules plus a mechanical conformity gate (python -m apothem.conformity.gate) come bundled, so the profile itself is held to a fifteen-bar pre-emission standard.',
  },
  {
    icon: Workflow,
    title: 'Deterministic plan & research pipelines',
    body: 'A deterministic /plan-spec to /plan-execute pipeline and a thirteen-stage /research pipeline run inside the tool — every option set carries a recommended choice, never a silent default.',
  },
  {
    icon: ShieldCheck,
    title: 'An eleven-command audit fortress',
    body: 'Code, security, performance, accessibility, dependency, supply-chain, and threat-model audits sweep in one parallel pass, then /fortress remediates and re-audits in a bounded loop.',
  },
  {
    icon: BrainCircuit,
    title: 'Durable memory, opt-in learning',
    body: 'A two-tier memory carries conventions across sessions; the learning loop is default-off under the agnostic posture — a clean install never auto-applies a workflow.',
  },
  {
    icon: Fingerprint,
    title: 'Supply-chain hardened releases',
    body: 'Each tagged release attaches signed artifacts — sdist, wheel, SBOM, Sigstore cosign signature, SLSA provenance, and npm provenance — with an OpenSSF Scorecard target on the producer pipeline.',
  },
  {
    icon: Eye,
    title: 'Preview before any write',
    body: 'apothem diff --harness <name> shows every pending change to a tool config before it lands — inspect the full diff, then install.',
  },
  {
    icon: RotateCcw,
    title: 'Reversible, verified lifecycle',
    body: 'Every install backs up what it replaces; apothem verify --json reports drift; uninstall reverses cleanly with zero orphans left behind.',
  },
];

export function FeatureGrid() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {features.map((f) => {
        const Icon = f.icon;
        return (
          <Card key={f.title} className="gap-3">
            <CardHeader className="gap-3">
              <span className="inline-flex size-10 items-center justify-center rounded-lg border border-[color-mix(in_oklch,var(--primary)_30%,transparent)] bg-[color-mix(in_oklch,var(--primary)_12%,transparent)] text-[var(--primary)]">
                <Icon className="size-5" />
              </span>
              <CardTitle className="text-base">{f.title}</CardTitle>
            </CardHeader>
            <CardDescription className="leading-relaxed">
              {f.body}
            </CardDescription>
          </Card>
        );
      })}
    </div>
  );
}
