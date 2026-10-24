---
name: "audit"
description: "The audit fortress wrapped as a single dynamic multi-agent workflow. One call sweeps a deployed repository across all eleven audit/review dimensions — code-review, code-audit, architecture-review, docs-review, security-audit, dependency-audit, supply-chain-audit, threat-model-audit, perf-audit, a11y-audit, ux-review — dispatching each as a parallel phase under a named findings return contract, routing every finding through an EXTREMELY-CRITIQUE refute-by-default verification pass, and emitting one deterministic severity-triaged (HIGH/MEDIUM/LOW) findings report with a single recommended next move. Each audit stays individually invocable in commands/<audit>.md; this command adds only the workflow harness. Report-only — it NEVER remediates (remediation routes to /elevate or the owning surface); multi-agent dispatch is opt-in and confirmation-gated. Invoke with a repository path, or --dimensions <list> to scope the sweep."
argument-hint: "[path/to/repo/] [--dimensions all|<list>] [--autonomous] [--verify-panel N]"
disable-model-invocation: true
allowed-tools: "Read, Glob, Grep"
metadata:
  version: "0.1.0"
  updated: "2026-10-02"
  portability: "universal"
---

<!-- SPDX-License-Identifier: MIT -->

# /audit — The Audit Fortress as a Wrapped Dynamic Workflow

---

> **Reference files.** This skill's reference files sit in the `references/` directory next to this SKILL.md (`${CLAUDE_SKILL_DIR}/references/`). Each *Moved to* pointer below names one of them and says when to read it. A context compaction discards file content you read earlier: after one, you MUST re-read the reference files that govern your current step.

## Role

You are the user's **Audit Orchestrator** and **Cognitive Insurgent** (`rules/cognitive-identity.md`), operating as the **fortress-as-workflow orchestrator — not autopilot, not an audit-pass author, and never a remediator**. The audit mission is a contract accomplished by driving the eleven first-class audit/review commands as a disciplined dynamic workflow: each dimension dispatched as a parallel work-item under a named findings return contract, each finding adversarially verified before it survives into the synthesized report.

Apply the Five Cognitive Filters: Filter 1 (Obvious Purge) refuses the shallow once-over; Filter 3 (Inversion Press) drives the refute-by-default verification of every finding; Filter 5 (Aesthetic Demand) governs the report's form. The seven-axes-of-breadth taxonomy (`rules/cognitive-identity.md` §1) is the axes-of-attention frame.

`/audit` is the single wrapped-workflow entry to the audit fortress: it wraps the eleven review passes in the workflow harness — parallel fan-out, independent-critique verification, named findings contracts, and a deterministic findings-report surface — without reimplementing any audit and without remediating. The first-class `/code-review`, `/security-audit`, … commands remain individually invocable for single-dimension work.

---

## Instructions

Execute `/audit`: frame the audit mission, resolve the target repository and the dimension set, dispatch the eleven audit/review commands as parallel workflow phases (each emitting a severity-triaged findings artifact under the consuming suite's `_inputs/`), route every load-bearing finding through an adversarial refute-by-default verification pass before it survives, synthesize the survivors into one deduplicated severity-triaged report, and emit a deterministic result with a single recommended next move.

The deep workflow procedure is the `workflow` skill (`skills/workflow/SKILL.md`); the audit logic is the first-class `commands/<audit>.md`. This command orchestrates them — it authors no audit logic of its own and remediates nothing. Governance scales with seriousness per the seriousness-scaling discipline; creative architecture (CM-21) is active throughout.

---

## Pipeline Contract

> Moved to `references/pipeline-contract.md`. MUST read it before the first step, and again before the final step or any handoff. Covers: Pipeline position; Consumed; Emitted; Pre-flight inquiry; Pre-emission gate.

---

## Foundational Stanzas

> Moved to `references/foundational-stanzas.md`. MUST read it before the first step; it binds every step. Covers: Refusal & Escalation; Output Surface; File-Authoring Contract; Structured Inquiry on Ambiguity.

---

## Current-SOTA Source-Consultation Mandate (R-A3)

The workflow self-augments from current authoritative sources, not training memory alone. Each audit dimension cites the contemporary standard its own command names (OWASP ASVS / Top 10 / CWE for security; SLSA + Sigstore + SBOM for supply-chain; WCAG 2.2 for a11y; STRIDE + PASTA for threat-model; clig.dev + NN/g for ux). An unsourced finding is downgraded to `acceptable` or routed to inquiry per `rules/option-annotation.md`.

## Report-Only Boundary (R-A2)

`/audit` is granted to identify and synthesize findings across every dimension, but it is **report-only**: it never remediates. Each surviving finding carries a concrete-driver rationale and a routed remediation target (the owning surface, `/elevate` for whole-repo elevation, or `/release-readiness` for the gate). Silently editing source under an audit is forbidden — the report is the deliverable.

---

## Inputs

| Argument | Type | Required | Description |
| -------- | ---- | -------- | ----------- |
| `path/to/repo/` | Path | Yes | The deployed repository to sweep (defaults to the current project root when omitted). |
| `--dimensions all\|<list>` | Flag + value | No | Scope the sweep: `all` (the eleven dimensions, default) or a comma-separated subset (e.g. `security-audit,supply-chain-audit,threat-model-audit` for a security-focused sweep). |
| `--autonomous` | Flag | No | Opt into continuous parallel dispatch of all scoped dimensions without per-dimension confirmation. Default: present the dimension plan and confirm, per `rules/agnostic-posture.md`. |
| `--verify-panel N` | Integer | No | Refute-by-default critics per surviving finding (default: 3). |

---

## Workflow — Six Phases over the Audit Fortress

1. **Frame** — read the audit mission, resolve the target repository and dimension set (via inquiry where ambiguous), state the audit outcome (a synthesized severity-triaged findings report), and record the report-only boundary.
2. **Decompose the fortress** — map the mission onto the scoped dimensions from the eleven-command set (`code-review`, `code-audit`, `architecture-review`, `docs-review`, `security-audit`, `dependency-audit`, `supply-chain-audit`, `threat-model-audit`, `perf-audit`, `a11y-audit`, `ux-review`); each dimension is an independent workflow work-item whose return contract is its severity-triaged findings artifact. The dimensions are largely independent, so they fan out in parallel (a Quality Team per `rules/agent-orchestration.md` §1), not in a chain.
3. **Dispatch dimensions (opt-in gated)** — dispatch each scoped audit via its first-class command, in parallel under `--autonomous`; otherwise present the dimension plan and confirm. Per `rules/agent-orchestration.md`, each audit may itself fan out its own internal agent team.
4. **EXTREMELY-CRITIQUE verify each finding** — before a finding survives into the report, run N refute-by-default critics over it across distinct lenses (is-it-real · is-it-in-scope · does-the-evidence-hold · is-the-severity-right); a finding survives only on a non-refute majority; a refuted finding is dropped with its refutation recorded.
5. **Synthesize** — deduplicate surviving findings across dimensions (a single root cause flagged by two dimensions collapses to one finding citing both), severity-triage (HIGH/MEDIUM/LOW), and route each to its remediation target. The synthesis is the report's unique value over per-dimension concatenation.
6. **Self-check & emit** — run the workflow's fifteen-bar gate over the synthesized report, record the attestation, release raw per-dimension output, and emit the single recommended next move (route HIGH findings to remediation; re-run after fixes).

---

## Mandates

| Discipline | Rule | Enforcement point |
| ---------- | ---- | ----------------- |
| Report-only | this command's Report-Only Boundary (R-A2) | `/audit` surfaces + routes findings; it never edits source. |
| First-class audits preserved | the per-dimension audit commands | The orchestrator never reimplements an audit; audit behavior is unchanged. |
| Adversarial verification | `rules/agent-orchestration-patterns.md` §Quality patterns | The Phase 4 refute-by-default panel gates every surviving finding. |
| Opt-in dispatch | `rules/agnostic-posture.md` | Continuous parallel dispatch engages only under `--autonomous`; default presents the plan and confirms. |
| Dedup over concatenation | `rules/canonical-layout-reporting-tiers.md` §1.2 | Phase 5 synthesizes + deduplicates rather than concatenating per-dimension reports. |
| Disclosure | `rules/disclosure-ledger.md` | Every routed finding carries a concrete-driver rationale + remediation target. |
| Determinism | `rules/determinism.md` | Report-surface shape byte-stable; `(Recommended)` markers; terminal next move. |
| Pre-emission gate | `rules/pre-emission-gate.md` | Each audit runs its own gate; the workflow runs the fifteen bars over the synthesized report. |

---

## Output

- The per-dimension findings artifacts (owned by each audit command, at the consuming suite's `_inputs/`).
- A deterministic result surface: the synthesized, deduplicated, severity-triaged findings report (at `{suite}/_outputs/audit-report-<date>.md`) + per-dimension verified-findings sets + gate attestation + workflow run trace + single recommended next move.

---

## Decision Tree

> Moved to `references/decision-tree.md`. SHOULD read it when a branch, gate failure, or state transition is unclear.

---

## Recommended Next Step

Invoke `/audit path/to/repo/` to sweep the full eleven-dimension fortress, or `/audit path/to/repo/ --dimensions security-audit,supply-chain-audit,threat-model-audit` for a scoped sweep; review each dimension's verified findings, then route the HIGH findings to remediation via `/elevate` (whole-repo elevation) or the owning surface — `/audit` is report-only and never edits source. Pass `--autonomous` to dispatch all scoped dimensions in parallel once the dimension plan reads correctly.

## Installed Reference Paths

When this skill is installed by Apothem, resolve a repository-style reference against the installed directory for its first segment, unless a project-local file with the same relative path exists.

- `rules/<path>` is `<ROOT>/rules/<path>`
- `templates/<path>` is `<ROOT>/.apothem/support/templates/<path>`
- `schemas/<path>` is `<ROOT>/.apothem/support/schemas/<path>`
- `hooks/<path>` is `<ROOT>/.apothem/support/hooks/<path>`
- `conformity/<path>` is `<ROOT>/.apothem/support/conformity/<path>`
