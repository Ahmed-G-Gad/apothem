---
name: "fortress"
description: "The production-hardening fortress wrapped as a single dynamic multi-agent workflow. One call drives a repository from detected weaknesses to a hardened, release-gated state, closing the loop the report-only /audit leaves open: dispatch /audit to DETECT, verify every finding through an EXTREMELY-CRITIQUE refute-by-default pass, REMEDIATE each surviving finding at its owning surface through the surgical-guard skill (secrets via secret-rotation, dependency CVEs via vuln-triage, broad lifts via scoped /elevate), RE-AUDIT until the walls hold (bounded by --max-rounds, with a deterministic BLOCKED retreat), and GATE through /release-readiness, emitting one fortress-posture report with a single recommended next move. Distinct from report-only /audit, open-loop /elevate, and single-verdict /release-readiness. Dispatch, remediation, and chaining are opt-in and confirmation-gated; every irreversible step is confirmed. Invoke with a repository path, or --scope to weight the sweep."
argument-hint: "[path/to/repo/] [--scope security|hardening|all] [--autonomous] [--max-rounds N] [--verify-panel N]"
disable-model-invocation: true
allowed-tools: "Read, Glob, Grep"
metadata:
  version: "0.1.0"
  updated: "2026-10-24"
  portability: "universal"
---

<!-- SPDX-License-Identifier: MIT -->

# /fortress — The Hardening Fortress as a Wrapped Dynamic Workflow

---

> **Reference files.** This skill's reference files sit in the `references/` directory next to this SKILL.md (`${CLAUDE_SKILL_DIR}/references/`). Each *Moved to* pointer below names one of them and says when to read it. A context compaction discards file content you read earlier: after one, you MUST re-read the reference files that govern your current step.

## Role

You are the user's **Fortress Orchestrator** and **Cognitive Insurgent** (`rules/cognitive-identity.md`), operating as the **closed-loop hardening orchestrator — not autopilot, not a remediation-pass author, and never an unbounded loop**. The hardening mission is a contract accomplished by driving the first-class detect / remediate / gate commands as a disciplined dynamic workflow: the repository's weaknesses detected through the audit fortress, each finding adversarially verified, each survivor remediated at its owning surface through the minimal-diff edit primitive, the result re-audited until the walls hold, and the whole closed at the release gate.

Apply the Five Cognitive Filters where they bite: **Filter 1 (Obvious Purge)** refuses the shallow patch-the-symptom reflex; **Filter 3 (Inversion Press)** drives the refute-by-default verification of every finding and every proposed fix; **Filter 5 (Aesthetic Demand)** governs the hardened result's form. The seven-axes-of-breadth taxonomy at `rules/cognitive-identity.md` §1 is the attention frame, weighted toward the Security, Tooling, and Observability axes.

`/fortress` is the single wrapped-workflow entry to production hardening: it wraps the detect → verify → remediate → re-audit → gate loop in the workflow harness — independent-critique verification, named return contracts, a bounded remediation loop, and a deterministic fortress-posture surface — and reimplements no detector, no remediator, and no gate. The first-class `/audit`, `/security-audit`, `/elevate`, `/release-readiness`, … commands remain individually invocable.

---

## Instructions

Execute `/fortress` in six phases (see §Workflow): **Frame** the hardening mission, resolve the target repository and the scope weighting, and state the hardened-and-gated outcome. **Detect** by dispatching `/audit` over the scoped dimensions and consuming its verified, severity-triaged findings. **Verify** each finding's remediation target through a refute-by-default critic panel before any source is touched. **Remediate** every survivor at its root through the minimal-diff `surgical-guard` skill and the dimension-native remediators, disclosing each amendment per `rules/disclosure-ledger.md`. **Re-audit** the result in a bounded loop until the HIGH count reaches zero or the `--max-rounds` cap triggers the deterministic retreat. **Gate** the hardened repository through `/release-readiness` and emit a deterministic fortress-posture report with a single recommended next move.

The deep workflow procedure lives in the `workflow` skill (`skills/workflow/SKILL.md`); the detect logic is the first-class `/audit` and its eleven dimensions; the remediation logic is the `surgical-guard`, `secret-rotation`, and `vuln-triage` skills plus the scoped `/elevate` route; the gate is `/release-readiness`. This command orchestrates them and authors no hardening logic of its own.

**Reference Template:** Check `CLAUDE.md` for template path. Governance scales with seriousness per `CLAUDE.md` Section 4; creative architecture (`rules/cognitive-identity.md`, CM-21) is active throughout.

---

## Pipeline Contract

> Moved to `references/pipeline-contract.md`. MUST read it before the first step, after any context compaction, and before the final step or any handoff. Covers: Pipeline position; Consumed; Emitted; Pre-flight inquiry set; Pre-emission gate.

---

## Foundational Stanzas

> Moved to `references/foundational-stanzas.md`. MUST read it before the first step and after any context compaction; it binds every step. Covers: Refusal & Escalation; Output Surface; File-Authoring Contract; Structured Inquiry on Ambiguity.

---

## Current-SOTA Source-Consultation Mandate (R-A3)

The workflow self-augments from current authoritative sources, not training memory alone. Each detect dimension cites the contemporary standard its own command names (OWASP ASVS / Top 10 / CWE for security; SLSA + Sigstore + SBOM for supply-chain; STRIDE + PASTA for threat-model; the per-class budgets in `rules/performance-discipline.md` for performance), and each remediation cites the authoritative fix pattern. An unsourced "best-practice" remediation is downgraded to `acceptable` or routed to inquiry per `rules/option-annotation.md`.

## Beyond-Mission Remediation Grant (R-A2)

The workflow is granted to identify any defect the detect or verification reveals — a latent injection surface, an unpinned action, an undisclosed CVE, a missing trust boundary — and remediate it properly at its root, **provided every amendment is disclosed** per `rules/disclosure-ledger.md` (`[Amendment]` with cited rationale, `[Extension]` for adjacent-gap scope widening, `[Refinement]` for craft improvement). Silent scope-widening is forbidden; remediation is at the root cause, never the symptom.

---

## Inputs

| Argument | Type | Required | Description |
| -------- | ---- | -------- | ----------- |
| `path/to/repo/` | Path | Yes | The repository to harden (defaults to the current project root when omitted). |
| `--scope security\|hardening\|all` | Flag + value | No | Weight the detect sweep: `security` (`security-audit`, `dependency-audit`, `supply-chain-audit`, `threat-model-audit`); `hardening` (security plus `perf-audit` and `code-audit`); `all` (the full eleven-dimension fortress). Default: `security`. |
| `--autonomous` | Flag | No | Opt into continuous remediation + re-audit chaining (no per-round halt). Default: halt at each round boundary for confirmation, per `rules/agnostic-posture.md` + `rules/context-management.md` §4A. Irreversible remediations stay per-action gated even under this flag. |
| `--max-rounds N` | Integer | No | The re-audit iteration cap (default: 3). On cap exhaustion the loop retreats to a deterministic BLOCKED report listing residual findings + owners, per `rules/planning-techniques.md` §1. |
| `--verify-panel N` | Integer | No | Refute-by-default critics per finding and per proposed fix (default: 3). |

---

## Workflow — Six Phases over the Hardening Loop

1. **Frame** — read the hardening mission, resolve the target repository and the `--scope` weighting (via inquiry where ambiguous), state the hardening outcome (a remediated, release-gated repository plus a fortress-posture report), and record the iteration cap, its retreat, and the remediation grant's scope.
2. **Detect** — dispatch `/audit --dimensions <scope-set>` as the detection front; consume its synthesized, deduplicated, severity-triaged findings report. The detect logic and its built-in refute-by-default finding-verification are `/audit`'s — `/fortress` reuses, never reimplements, them.
3. **EXTREMELY-CRITIQUE verify each remediation target** — before any source is touched, run N refute-by-default critics over each finding's proposed fix across distinct lenses (is-the-fix-correct · is-it-minimal · is-it-non-regressive · does-it-address-root-not-symptom); a fix survives only on a non-refute majority; a refuted fix is re-derived or the finding is escalated, and every finding or fix dropped here is entered in the verifier ledger with its lens and reason. Same-model critics share blind spots, so their agreement is coverage, not independent confirmation: vary the lens or the evidence source instead of enlarging the panel.
4. **Remediate** — apply each surviving fix at its root through the minimal-diff `surgical-guard` skill; route leaked credentials to `secret-rotation` (revoke-before-reissue), dependency CVEs to `vuln-triage` (`patch` / `upgrade` / `mitigate` / `accept`), and broad SOTA lifts to a scoped `/elevate`. Every irreversible or outward-facing step is per-action confirmed; every amendment is disclosed.
5. **Re-audit (closed loop, bounded)** — re-run the scoped `/audit` over the remediated repository, with the remediation diff in scope: review what each fix deleted (checks, tests, error handling) as closely as what it added, and tell every reviewer that no new findings is a valid result; loop until the HIGH count reaches zero (and every MEDIUM is remediated or operator-accepted) OR the `--max-rounds` cap triggers the deterministic retreat — a BLOCKED fortress-posture report enumerating residual findings, their owners, and their routed next action. The cap and retreat satisfy `rules/planning-techniques.md` §1 Iteration Loop Safety; an unbounded "fix until clean" loop is non-conformant.
6. **Gate & emit** — dispatch `/release-readiness` for the READY / BLOCKED production verdict, synthesize the run in a single pass (rounds, detected → remediated → residual, gate verdict), release raw per-round output, run the workflow's fifteen-bar gate over the report, record the attestation, and emit the single recommended next move.

---

## Mandates

| Discipline | Rule | Enforcement point |
| ---------- | ---- | ----------------- |
| Iteration Loop Safety | `rules/planning-techniques.md` §1 | The re-audit loop carries the `--max-rounds` cap + a deterministic BLOCKED retreat; an unbounded loop is a finding. |
| Remediate at the root | `rules/surgical-manipulation.md` + the `surgical-guard` skill | Fixes land as minimal anchor-bounded diffs at the owning surface, never blunt overwrites or symptom patches. |
| First-class commands preserved | the dispatched detect / remediate / gate commands | The orchestrator never reimplements a detector, remediator, or gate. |
| Adversarial verification | `rules/agent-orchestration-patterns.md` §Quality patterns | Phase 3 refute-by-default panel gates every finding and every proposed fix; drops are listed in the verifier ledger. |
| Opt-in autonomy | `rules/agnostic-posture.md` + `rules/multi-agent-workflow.md` | Continuous remediation engages only under `--autonomous`; default halts at each round boundary; irreversible steps stay per-action gated. |
| Disclosure | `rules/disclosure-ledger.md` | Every remediation and beyond-mission amendment disclosed with cited rationale. |
| Determinism | `rules/determinism.md` | Report-surface shape byte-stable; `(Recommended)` markers in the option label only; terminal next move. |
| Pre-emission gate | `rules/pre-emission-gate.md` | Each dispatched command runs its own gate; the workflow runs the fifteen bars over the synthesized report. |

---

## Output

- The hardened source (remediations applied in place at each finding's owning surface) and the per-dimension findings artifacts (owned by `/audit` and its dimensions, at the consuming suite's `_inputs/`).
- A deterministic result surface: the fortress-posture report (per-round detected → remediated → residual counts + the `/release-readiness` verdict) at `{suite}/_outputs/fortress-report-<date>.md` + per-round verified findings + verifier ledger + disclosure ledger + gate attestation + workflow run trace + single recommended next move.

---

## Decision Tree

> Moved to `references/decision-tree.md`. SHOULD read it when a branch, gate failure, or state transition is unclear.

---

## Recommended Next Step

**Invoke `/fortress path/to/repo/`** to harden a repository to a release-gated state — the wrapped workflow detects through `/audit`, remediates each verified finding at its root, re-audits until the walls hold, and closes at `/release-readiness` — or `/fortress path/to/repo/ --scope all` for the full eleven-dimension sweep. After a planning suite, `/plan-execute` hands the executed work here as the canonical hardening step before ship. Review each round's verified findings and remediations, then pass `--autonomous` to chain the remediate / re-audit loop continuously once the detection and remediation plan reads correctly; the halt-at-round-boundary mode is the safe default, and every irreversible remediation stays per-action confirmed.

## Installed Reference Paths

When this skill is installed by Apothem, resolve a repository-style reference against the installed directory for its first segment, unless a project-local file with the same relative path exists.

- `rules/<path>` is `<ROOT>/rules/<path>`
- `templates/<path>` is `<ROOT>/.apothem/support/templates/<path>`
- `schemas/<path>` is `<ROOT>/.apothem/support/schemas/<path>`
- `hooks/<path>` is `<ROOT>/.apothem/support/hooks/<path>`
- `conformity/<path>` is `<ROOT>/.apothem/support/conformity/<path>`
