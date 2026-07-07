// SPDX-License-Identifier: MIT

import { Check, Minus } from 'lucide-react';
import { cn } from '@/lib/utils';

/**
 * Differentiation matrix rendered on the landing page. The rows and the
 * honest concessions are sourced from the repository's "How apothem compares"
 * section and the peer-differentiation source of truth — apothem trades raw
 * tool count for the governance and lifecycle discipline shipped around the
 * sync, and where a peer is stronger it is named.
 */

type Cell = { kind: 'yes'; note: string } | { kind: 'no'; note: string } | { kind: 'na' };

type Row = {
  capability: string;
  apothem: Cell;
  fileManagers: Cell; // chezmoi, GNU Stow
  ruleSync: Cell; // rulesync and peers
};

const columns = ['Apothem', 'File config managers', 'Cross-tool rule sync'] as const;

const rows: Row[] = [
  {
    capability: "One source to many tools' native schemas",
    apothem: { kind: 'yes', note: 'seventeen harness adapters' },
    fileManagers: { kind: 'no', note: 'copy or symlink, no translation' },
    ruleSync: { kind: 'yes', note: 'reaches more tools' },
  },
  {
    capability: 'Synced unit',
    apothem: { kind: 'yes', note: 'rules, skills, hooks, commands, MCP' },
    fileManagers: { kind: 'na' },
    ruleSync: { kind: 'yes', note: 'rules, MCP, commands, skills, hooks' },
  },
  {
    capability: 'Governance corpus with a mechanical conformity gate',
    apothem: { kind: 'yes', note: 'python -m apothem.conformity.gate' },
    fileManagers: { kind: 'no', note: 'config only' },
    ruleSync: { kind: 'no', note: 'config only' },
  },
  {
    capability: 'Deterministic plan and research pipelines',
    apothem: { kind: 'yes', note: '/plan-spec to /plan-execute, thirteen-stage /research' },
    fileManagers: { kind: 'no', note: 'none' },
    ruleSync: { kind: 'no', note: 'none' },
  },
  {
    capability: 'Audit fortress that detects and remediates',
    apothem: { kind: 'yes', note: 'eleven-command sweep, /fortress re-audit loop' },
    fileManagers: { kind: 'no', note: 'none' },
    ruleSync: { kind: 'no', note: 'none' },
  },
  {
    capability: 'Supply-chain hardened releases',
    apothem: { kind: 'yes', note: 'SBOM, Sigstore, SLSA, npm provenance, Scorecard target' },
    fileManagers: { kind: 'no', note: 'none' },
    ruleSync: { kind: 'no', note: 'varies' },
  },
  {
    capability: 'Reversible, verified lifecycle',
    apothem: { kind: 'yes', note: 'backup, verify --json drift, zero-orphan uninstall' },
    fileManagers: { kind: 'no', note: 'varies' },
    ruleSync: { kind: 'no', note: 'varies' },
  },
];

function CellMark({ cell, accent }: { cell: Cell; accent?: boolean }) {
  if (cell.kind === 'na') {
    return (
      <span className="inline-flex items-center text-[var(--muted-foreground)]">
        <Minus className="size-4" aria-label="not applicable" />
      </span>
    );
  }
  const isYes = cell.kind === 'yes';
  return (
    <span className="flex flex-col items-center gap-1 text-center">
      {isYes ? (
        <Check
          className={cn(
            'size-4 shrink-0',
            accent ? 'text-[var(--primary)]' : 'text-[var(--foreground)]'
          )}
          aria-label="yes"
        />
      ) : (
        <Minus
          className="size-4 shrink-0 text-[var(--muted-foreground)]"
          aria-label="no"
        />
      )}
      <span className="text-xs leading-snug text-[var(--muted-foreground)]">
        {cell.note}
      </span>
    </span>
  );
}

export function FeatureMatrix() {
  return (
    <div className="overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--card)]">
      {/* Horizontal scroll on narrow viewports: the prose-heavy four-column
          grid keeps its min-width and scrolls rather than crushing on mobile. */}
      <div className="overflow-x-auto">
        <table className="w-full min-w-[40rem] border-collapse text-sm">
        <thead>
          <tr className="border-b border-[var(--border)] bg-[var(--muted)]/40">
            <th className="px-4 py-3 text-start font-medium text-[var(--muted-foreground)]">
              Capability
            </th>
            {columns.map((c, i) => (
              <th
                key={c}
                className={cn(
                  'px-4 py-3 text-center font-semibold',
                  i === 0
                    ? 'text-[var(--primary)]'
                    : 'text-[var(--foreground)]'
                )}
              >
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, ri) => (
            <tr
              key={row.capability}
              className={cn(
                ri % 2 === 1 && 'bg-[var(--muted)]/20',
                'border-b border-[var(--border)] last:border-b-0'
              )}
            >
              <th
                scope="row"
                className="px-4 py-3 text-start font-medium text-[var(--foreground)]"
              >
                {row.capability}
              </th>
              <td className="px-4 py-3 align-top">
                <CellMark cell={row.apothem} accent />
              </td>
              <td className="px-4 py-3 align-top">
                <CellMark cell={row.fileManagers} />
              </td>
              <td className="px-4 py-3 align-top">
                <CellMark cell={row.ruleSync} />
              </td>
            </tr>
          ))}
        </tbody>
        </table>
      </div>
      <p className="border-t border-[var(--border)] px-4 py-3 text-xs text-[var(--muted-foreground)]">
        Where a peer is stronger, it is named: cross-tool rule sync reaches
        more tools and carries a comparably wide synced unit, and several sync
        tools materialize native schemas. Apothem trades raw tool count for the
        governance, audit, and lifecycle discipline shipped around the sync — a
        conformity gate, deterministic pipelines, an audit fortress, and a
        reversible verified lifecycle.
      </p>
    </div>
  );
}
