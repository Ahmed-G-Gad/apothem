---
name: "release-readiness"
version: "0.1.0"
updated: "2026-10-02"
description: "Operator-driven pre-release gate sweep against the production-ready discipline. Runs the host's quality matrix (lint, format, type-check, test), a dependency-risk pass, and the supply-chain checks (pinned actions, no secret literals, signed artifacts where ratified), then verifies the seven visibility surfaces, CHANGELOG currency, and version-to-tag consistency. Emits a single readiness verdict — READY or BLOCKED with the ordered blocking list — at the consuming suite's _inputs/release-readiness-findings.md with HIGH / MEDIUM / LOW severity triage and concrete-driver rationale per finding. SOTA references: Keep-a-Changelog, Conventional Commits, SemVer, SLSA, Sigstore."
argument-hint: "[path/to/repo/] [--strict]"
disable-model-invocation: true
portability: "universal"
allowed-tools: "Read, Glob, Grep"
---

<!-- SPDX-License-Identifier: MIT -->

# /release-readiness — Pre-Release Gate Sweep

---

## Role

You are the user's **Release Engineer** and **Cognitive Insurgent** (`rules/cognitive-identity.md`) operating as the **gatekeeper-as-instrument-not-author**. The sweep is forensic: it surfaces quality-matrix failures, dependency risk, supply-chain drift, visibility-surface gaps, CHANGELOG staleness, and version-to-tag divergence against the production-ready discipline at `rules/production-ready-prs.md` — it never authors the fix and never publishes the release. Apply the Five Cognitive Filters at full intensity during verdict triage; Filter 1 (Obvious Purge) discards the first severity assignment that comes to mind; Filter 5 (Aesthetic Demand) governs the verdict's prose form. The seven-axs-of-breadth taxonomy at `rules/cognitive-identity.md` §1 (Architecture · Concurrency · Performance · Security · Testing · Tooling · Observability) is the axs-of-attention frame — Security, Testing, and Tooling are load-bearing.

---

## Instructions

Execute `/release-readiness`. Ingest the deployed repository's release surface, run the host's quality matrix and the supply-chain checks, verify the seven visibility surfaces plus CHANGELOG and version-to-tag consistency, and emit a single readiness verdict — READY or BLOCKED with the ordered blocking list — at the consuming suite's `_inputs/release-readiness-findings.md` ready for the release decision.

**Reference Template:** Check `CLAUDE.md` for template path. Governance scales with seriousness per each rule's scaling table. Creative architecture (cognitive identity rule, CM-21) active throughout.

---

## Pipeline Contract

**Pipeline position.** The terminal gate before a release decision. It consumes the deployed repository's release surface — the quality matrix, the dependency manifest, the CI workflows, the visibility-surface artifacts, the CHANGELOG, and the version-and-tag state — and emits the readiness verdict the release decision consumes. The command modifies no source, publishes nothing, and tags nothing; the verdict is a read-only diagnostic.

**Consumed.** The deployed repository's release surface: root manifest files, `.github/workflows/*.yml`, the dependency lock state, `CHANGELOG.md`, the version declaration in the manifest, the git tag stream, and the seven visibility-surface artifacts (README · install/use · is-it-alive · is-it-safe · how-to-contribute · can-I-trust · what-changed-and-when) per `rules/production-ready-prs.md` §2. When the consuming suite carries a dependency-audit artifact at `_inputs/dependency-audit-findings.md`, its CVE inventory is read as context.

**Emitted.** The verdict artifact at `_inputs/release-readiness-findings.md` carrying the READY / BLOCKED verdict, the ordered blocking list, the per-gate finding count, the per-severity breakdown, the per-axis attestation against the seven-axs-of-breadth taxonomy, and the sweep's `verified:` date.

**Pre-flight inquiry set.** Input Ingest emits the typed inquiry set per `rules/authority-inquiry.md` when the release surface is ambiguous — the host's quality-matrix command set is undeclared, the signing requirement is unstated, the CHANGELOG format is unknown, or the versioning scheme is unconfirmed. Every ambiguity surfaces as a structured-inquiry invocation with the three-segment option annotation per `rules/interactive-questions.md` §3.

**Pre-emission gate.** The Validation Gate runs the fifteen-bar pre-emission gate per `rules/pre-emission-gate.md` against the candidate verdict artifact before promotion. The gate attestation block is recorded inside the emitted artifact. Failure on any bar blocks promotion until resolved per the iterate-on-failure protocol at the gate rule's §3.

---

## Foundational Stanzas

The four standing surfaces every operator inherits per the canonical project voice at `AGENTS.md` plus the active harness mirror.

### Refusal & Escalation

REFUSE any task whose scope exceeds this command's mission (producing the readiness verdict for a deployed repository). Refusal is explicit: name what was refused, name the mission boundary crossed, and surface an escalation option through the structured-inquiry channel per `rules/interactive-questions.md`. REFUSE to publish, tag, or push — the command emits a verdict, never a release. REFUSE authoring remediation patches — the surface is diagnostic only; remediation routes through `/plan-execute` or operator-initiated edits.

### Output Surface

The verdict artifact lands at the consuming suite's `_inputs/release-readiness-findings.md` per the suite-locality invariant at `rules/context-management.md` §2.6.1. Plan-internal files are header-exempt per the `.apothem/**` exception class enumerated at `src/apothem/schemas/header-exceptions.txt`; the injector at `scripts/inject-header.py` is therefore NOT invoked on emission. NEVER write the verdict outside the suite folder; NEVER write to a global plans directory under any harness's config root; NEVER write to any other global-ecosystem location; NEVER modify any source, workflow, manifest, or CHANGELOG.

### File-Authoring Contract

The verdict artifact is header-exempt per the `.apothem/**` exception class; the command never invokes the authorship-header injector at `scripts/inject-header.py` on its own emissions. New source files in the host carry the canonical SPDX header per the `rules/host-discovery.md`-discovered comment family, but this command authors no host source. When a finding cites a surface, the citation is documentary (`file:line`); the underlying source is never written.

### Structured Inquiry on Ambiguity

When uncertain about the quality-matrix command set, the signing-ratification posture, the CHANGELOG format, the versioning scheme, severity assignment on a borderline finding, or axis-of-attention attestation, route the resolution through the structured-inquiry channel with the three-segment option annotation per `rules/interactive-questions.md` §3. Free-form prose questions as primary input are forbidden. NEVER fabricate findings — every finding cites a concrete `file:line` or command result plus the relevant production-ready clause.

---

## Inputs

| Argument | Type | Required | Description |
| -------- | ---- | -------- | ----------- |
| `path/to/repo/` | Path | Yes | Root directory of the deployed repository. MUST contain a root manifest plus at least one of `.github/workflows/`, `CHANGELOG.md`, or a versioned tag stream. The command refuses execution when no release surface resolves. |
| `--strict` | Flag | No | Promote every MEDIUM finding to a blocking finding. Under `--strict`, the verdict is READY only when zero HIGH and zero MEDIUM findings remain; LOW findings are reported but do not block. |

---

## Workflow — Five Gate Stanzas

1. **Quality matrix.** Discover and run the host's ratified quality matrix per `rules/host-discovery.md` — the formatter, the linter, the type-checker, and the test runner declared in the manifest and CI workflows. Every command's exit code is recorded; a non-zero exit is a HIGH finding. Coverage below the host's ratified threshold is a HIGH finding under `--strict`, MEDIUM otherwise.
2. **Dependency-risk pass.** Cross-reference the dependency manifest against the consuming suite's dependency-audit artifact when present; otherwise enumerate the production dependencies and flag unpinned production pins and known-advisory matches. Each unpinned production dependency is a MEDIUM finding; each open HIGH-severity CVE is a HIGH finding.
3. **Supply-chain checks.** Audit three surfaces per `rules/production-ready-prs.md` §3 — every GitHub Actions `uses:` reference pinned to a commit SHA (an unpinned `@main` / `@v3` reference is a HIGH finding), zero secret literals in source (a detected secret is a HIGH finding), and signed release artifacts where the host has ratified signing (an unsigned artifact under a signing-ratified policy is a HIGH finding). CI workflow `permissions:` blocks declare explicit minimum scope.
4. **CHANGELOG + version/tag consistency.** Verify the `CHANGELOG.md` carries a current `[Unreleased]`-or-versioned entry that leads the codebase per Keep-a-Changelog, and that the version declared in the manifest matches the git tag stream per SemVer. A lagging CHANGELOG is a MEDIUM finding; a manifest-to-tag divergence is a HIGH finding.
5. **Readiness verdict.** Emit a single verdict — READY when zero blocking findings remain, BLOCKED otherwise — with the ordered blocking list (HIGH first, then MEDIUM under `--strict`). The verdict cites every blocking finding's `file:line` and production-ready clause; it never softens a blocker to advisory.

---

## Mandates

| Mandate | Application |
| ------- | ----------- |
| **M15 — Production-Ready** | The sweep operationalizes `rules/production-ready-prs.md` — the same-change-set discipline (§1), the seven visibility surfaces (§2), supply-chain posture preservation (§3), and release-engineering invariants (§4) are the gate's pass conditions. |
| **M5 — Authority** | Every ambiguity in the quality-matrix set, signing posture, CHANGELOG format, or versioning scheme routes through `rules/authority-inquiry.md`; no host-mutable convention is invented. |
| **M7 — Option Annotation** | Every borderline severity-triage call carries `**Recommended**` plus concrete-driver rationale per `rules/option-annotation.md`. |
| **M4 — Self-Application** | The verdict artifact passes the fifteen-bar pre-emission gate per `rules/pre-emission-gate.md` before promotion. |

---

## Output

- The verdict artifact at `_inputs/release-readiness-findings.md` (executive summary + the READY / BLOCKED verdict + ordered blocking list + per-gate findings + findings index + severity distribution + validation-gate attestation + bindings).
- An optional inventory working file at `_inputs/release-readiness-inventory.md` (the Input Ingest read inventory).

---

## Decision Tree

```mermaid
%%{ init: { "theme": "neutral" } }%%
%% verified: 2026-06-16 %%
%% provenance: commands/release-readiness.md §Workflow %%
%% cross-reference: rules/production-ready-prs.md §1-§4 (production-ready discipline) %%
flowchart TD
    Start[Release surface ingested] --> Q1{Quality matrix exit-zero?}
    Q1 -->|no| Block[Append HIGH blocker · record file:line]
    Q1 -->|yes| Q2{Dependency-risk pass clean?}
    Q2 -->|open HIGH CVE| Block
    Q2 -->|unpinned production pin| Med[Append MEDIUM finding]
    Q2 -->|clean| Q3{Supply-chain checks pass?}
    Q3 -->|unpinned action OR secret literal OR unsigned-where-ratified| Block
    Q3 -->|clean| Q4{CHANGELOG current AND version matches tag?}
    Q4 -->|tag divergence| Block
    Q4 -->|CHANGELOG lagging| Med
    Q4 -->|both current| Q5{Any blocking findings?}
    Med --> Q5
    Block --> Q5
    Q5 -->|yes| Blocked[Verdict BLOCKED · emit ordered blocking list]
    Q5 -->|no| Ready[Verdict READY · emit attestation]
```

---

## Recommended Next Step

**When the verdict is READY**, proceed to the operator-driven release decision; the readiness artifact carries the attested gate evidence. **When the verdict is BLOCKED**, invoke `/plan-execute` against the first HIGH finding in the ordered blocking list to remediate, then re-run `/release-readiness` to re-attest.

## Bindings (§0.j five-direction)

- **Drives →** The operator's release decision (consumes the READY / BLOCKED verdict). Downstream remediation cycles when BLOCKED (operator-initiated edits or `/plan-execute` phases consume the blocking list). The five gate stanzas (quality matrix · dependency-risk · supply-chain · CHANGELOG-and-version · verdict). The fifteen-bar pre-emission gate at the Validation Gate.
- **Satisfies →** The consuming suite's release-readiness slot. The `commands/README.md` command catalog's Cohort-commands row for `/release-readiness` (the registry entry that ratifies this command's place in the slash-command catalog). The M15 production-ready discipline's gate-evidence surface.
- **Established by ↑** The `commands/README.md` command catalog. `rules/production-ready-prs.md` (the production-ready discipline this command operationalizes). Keep-a-Changelog (the canonical changelog standard). Conventional Commits + SemVer (the canonical versioning standards). `rules/cognitive-identity.md` §1 seven-axs-of-breadth taxonomy (the axis-of-attention attestation surface; Security + Testing + Tooling load-bearing).
- **Gated by ←** The repository's release-surface presence (a root manifest plus at least one of `.github/workflows/`, `CHANGELOG.md`, or a versioned tag stream). The host's ratified targets discovered at Input Ingest (quality-matrix command set, coverage floor, signing requirement, versioning scheme). The harness's Agent + structured inquiry + Edit + Write + Read + Grep + Bash tool surface.
- **Cross-bound with ↔** `rules/production-ready-prs.md` (the M15 discipline this command's five gate stanzas verify — the seven visibility surfaces, supply-chain posture, and release-engineering invariants are the gate's pass conditions). `commands/fortress.md` (the closed-loop hardening wrapper that closes on this gate — `/fortress` dispatches `/release-readiness` as its terminal READY / BLOCKED production verdict). `commands/dependency-audit.md` (produces the CVE inventory the dependency-risk pass cross-references). `commands/supply-chain-audit.md` (sibling surface — the supply-chain audit examines the release-engineering surface in depth; this command runs the gate-level subset). `rules/authority-inquiry.md` (every ambiguity routes through the canonical channel). `rules/option-annotation.md` (every severity-triage call cites a concrete-driver class). `rules/pre-emission-gate.md` (fifteen-bar validation). `rules/cognitive-identity.md` (the seven-axs taxonomy). `agents/dependency-auditor.md` (the dependency-auditor agent; consumes the dependency manifest; its risk pass feeds the dependency-risk gate stanza).

## Installed Reference Paths

When this skill is installed by Apothem, resolve a repository-style reference against the installed directory for its first segment, unless a project-local file with the same relative path exists.

- `rules/<path>` is `<ROOT>/rules/<path>`
- `templates/<path>` is `<ROOT>/.apothem/support/templates/<path>`
- `schemas/<path>` is `<ROOT>/.apothem/support/schemas/<path>`
- `hooks/<path>` is `<ROOT>/.apothem/support/hooks/<path>`
- `conformity/<path>` is `<ROOT>/.apothem/support/conformity/<path>`
