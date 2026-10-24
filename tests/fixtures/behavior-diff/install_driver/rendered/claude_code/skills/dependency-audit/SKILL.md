---
name: "dependency-audit"
description: "Operator-driven per-dependency audit pass (direct + transitive). Walks every dependency declared in the repository's manifest files (pyproject.toml, package.json, Cargo.toml, go.mod, Gemfile, etc.) plus their resolved lockfile entries and emits per-dependency findings covering license compatibility, CVE status, deprecation status, replacement recommendation, transitive depth, pinned-vs-range posture, and security-relevant identification. Tooling: pip-audit + safety + osv-scanner + configured dependency-update automation insights. Output lands at the consuming suite's _inputs/dependency-audit-findings.md with HIGH / MEDIUM / LOW severity triage and concrete-driver rationale per finding."
argument-hint: "[path/to/repo/] [--focus MANIFEST_OR_DEP] [--dry-run]"
disable-model-invocation: true
allowed-tools: "Read, Glob, Grep"
metadata:
  version: "0.1.0"
  updated: "2026-10-02"
  portability: "universal"
---

<!-- SPDX-License-Identifier: MIT -->

# /dependency-audit — Per-Dependency Audit (Direct + Transitive)

---

> **Reference files.** This skill's reference files sit in the `references/` directory next to this SKILL.md (`${CLAUDE_SKILL_DIR}/references/`). Each *Moved to* pointer below names one of them and says when to read it. A context compaction discards file content you read earlier: after one, you MUST re-read the reference files that govern your current step.

## Role

You are the user's **Supply-Chain Engineer** and **Cognitive Insurgent** (`rules/cognitive-identity.md`), the **auditor-as-instrument-not-author**. This is a read-only forensic surface: it names CVE exposure, license incompatibility, deprecation creep, and unpinned-production-dependency risk against the host's ratified dependency policy — it never writes the fix.

- **Cognitive filters** per `rules/cognitive-identity.md` §2 — Obvious Purge and Aesthetic Demand on every severity call.
- **Seven-axes attestation** per §1: **Security and Tooling lead** — the lockfile and advisory feed drive each finding.

---

## Instructions

Execute `/dependency-audit`: ingest the repository's manifests plus their resolved lockfile entries, walk every direct and transitive dependency, apply CVE scanning + license analysis + deprecation detection + transitive-depth analysis, and emit a per-dependency findings artifact at the consuming suite's `_inputs/dependency-audit-findings.md` ready for remediation.

Governance scales with seriousness per the seriousness-scaling discipline; creative architecture (CM-21) is active throughout.

---

## Pipeline Contract

> Moved to `references/pipeline-contract.md`. MUST read it before the first step, and again before the final step or any handoff. Covers: Pipeline position; Audit-fortress sequence position; Handoff Manifest; Pre-flight inquiry set; Pre-emission gate.

---

## Foundational Stanzas

> Moved to `references/foundational-stanzas.md`. MUST read it before the first step; it binds every step. Covers: Refusal & Escalation; Output Surface; File-Authoring Contract; Structured Inquiry on Ambiguity.

---

## Inputs

| Argument | Type | Required | Description |
| -------- | ---- | -------- | ----------- |
| `path/to/repo/` | Path | Yes | Root directory of the deployed repository. MUST contain at least one manifest file resolvable as a dependency declaration (`pyproject.toml`, `package.json`, `Cargo.toml`, `go.mod`, `Gemfile`, or sibling languages). The command refuses execution when none resolves. |
| `--focus MANIFEST_OR_DEP` | String | No | Restrict the per-dependency walk to a single manifest file (path) OR a single dependency name (package). Useful when triaging a single transitive chain incrementally. |
| `--dry-run` | Flag | No | Analyze what would be audited and report — no findings artifact emitted. The dry-run output enumerates the manifest count, the resolved dependency-graph node count per language, the per-tool invocation plan, and any pre-flight inquiries that would fire without committing the artifact. |

---

## Workflow — Five Transformation Phases

**Scan delegation.** The dependency-tree scan this workflow performs is owned by sibling capabilities; the command orchestrates them into a per-dependency findings artifact with license + deprecation coverage rather than re-implementing the detectors:

- **Dependency-tree risk scan → `agents/dependency-auditor.md`.** The read-only ecosystem-detection + four-risk-class walk (known-vulnerable · unpinned · duplicate · stale) across npm / pip / cargo / go is the dependency-auditor agent's owned surface. Phase 1's per-dependency walk dispatches that scan and consumes its risk-ranked table; the command deepens the agent's first-pass with the license-compatibility and deprecation analyses the agent does not carry, and emits the validation-gate-attested artifact.
- **CVE disposition → `skills/vuln-triage`.** Each known-vulnerable finding routes its severity-classify-and-remediation-route disposition (the seven-field triage record) to the vuln-triage skill; the command records the routed band per finding and does not re-publish CVSS or re-solve the dependency graph.
- **Upgrade remediation → `skills/dependency-upgrade`.** A finding whose remediation is an audited version bump routes its remediation to the dependency-upgrade skill (changelog-reviewed, pinned, gate-verified); the command names the routed owner per finding and never authors the bump inline.

### Phase 0 — Input Ingest

Read the manifest tree and lockfiles in full. Deploy a Research Team (CM-25A) for parallel ingest — one agent per language ecosystem present (Python / JavaScript / Rust / Go / Ruby / …). Each returns a structured dependency inventory ≤ 500 tokens (CM-25C) with required fields `status` · `manifest-list` · `dependency-count` · `transitive-depth-distribution` · `gaps`.

**Required reads.**

- **Every manifest** under the root (`pyproject.toml`, `setup.cfg`, `requirements*.txt`, `Pipfile`, `package.json`, `Cargo.toml`, `go.mod`, `Gemfile`, …) per `rules/host-discovery-manifests.md` §1.
- **Every lockfile sibling** (`uv.lock`, `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`, `Cargo.lock`, `go.sum`, `Gemfile.lock`) — the lockfile is the authoritative resolution; the manifest declares ranges the lockfile pins.
- **The host's ratified accepted-license list** (when present in a project policy file, `REUSE.toml`, or `pyproject.toml` `[tool.<linter>]`).

**Externalise** a working inventory at the suite's `_inputs/dependency-audit-inventory.md` (free-form scratch per `rules/context-management-scratch.md` §1): per-language ecosystem count, per-manifest declared dependency count, lockfile resolution count, transitive-depth histogram, and any `--focus` narrowing.

### Phase 1 — Per-Dependency Walk

Dispatch the `agents/dependency-auditor.md` read-only risk scan first (it enumerates every direct + transitive entry and ranks known-vulnerable → unpinned → duplicate → stale against the host's audit tooling), then deepen its findings with the license + deprecation analyses below. The command consumes the agent's risk-ranked table; it does not re-derive the four risk classes. Run five complementary tools across the present ecosystems:

| Tool | Scope | Surface |
| ---- | ----- | ------- |
| **pip-audit** | Python | PyPA Advisory Database + OSV CVEs per resolved version |
| **safety** | Python | sibling CVE feed; cross-referenced with pip-audit |
| **osv-scanner** | multi-language | Google OSV across Python / JS / Rust / Go / Ruby — the canonical cross-ecosystem CVE surface |
| **License analysis** | all | each dependency's declared `license` field resolved against the host's accepted-license list (SPDX-license-expression standard) |
| **Deprecation analysis** | all | registry deprecation markers (npm `deprecated`, crates.io `yanked`) per resolved version |

Attest each detected issue as one canonical finding class:

- **CVE** — a known CVE on the resolved version. Carry the CVE ID, CVSS score (CVSS v3.1 baseline), affected version range, and fixed version.
- **License incompatibility** — the license is off the host's accepted list (or no list exists and a long-lived ratification is needed).
- **Deprecation** — the resolved version (or whole package) is deprecated / yanked at the registry.
- **Unpinned production dependency** — a production-tier dependency declared with a range rather than a specific version (per the host's ratified pinning policy).
- **Transitive-depth concern** — a security-relevant dependency surfacing at transitive depth ≥ 3 (pulled indirectly, without explicit declaration).

**Externalise** per-dependency finding drafts at the suite's `_inputs/dependency-audit-per-dep/` (one file per dependency carrying a finding), each enumerating raw findings with `package@version` + the detecting tool's advisory ID before triage.

### Phase 2 — Per-Finding Triage

> Moved to `references/step-03-per-finding-triage.md`. MUST read it in full before executing this step.

### Phase 3 — Findings Emission

Emit the suite's `_inputs/dependency-audit-findings.md` with the following canonical sections:

1. **`## §1 Executive Summary`** — one paragraph stating the audit scope (manifest count per language, total dependency-graph node count, transitive-depth distribution, tools invoked with versions and advisory-feed dates), the finding count per severity, and the per-class distribution.
2. **`## §2 ... §N` Per-Dependency Findings** — one section per dependency carrying findings. Each finding records: `Finding ID` (e.g., `DA-001`) · `Package@Version` · `Manifest:Line` · `Severity` · `Class` (CVE / License / Deprecation / Unpinned / Transitive-depth) · `Identifier` (CVE / GHSA / SPDX expression / registry marker) · `Axes` (the seven-axes attestation) · `Rationale` (concrete-driver class) · `Remediation pointer` (the upstream advisory's recommended fix, never the fix itself).
3. **`## §Findings Index`** — table indexed by Finding ID with columns `Package@Version` · `Severity` · `Class` · `Identifier`. Indexed by severity descending.
4. **`## §Severity Distribution`** — count table per severity per class, plus the per-language dependency count for context.
5. **`## §Validation Gate Outcome`** — the Phase 4 fifteen-bar gate attestation block per `rules/pre-emission-gate.md` §2.
6. **`## §Bindings (§0.j five-direction)`** — the artifact's own outward bindings to upstream (the manifest tree) and downstream (remediation surfaces).

Apply incremental generation per `rules/large-file-generation.md` when the artifact exceeds 500 lines. Plan the section structure before authoring; emit the first section via Write; append subsequent sections via Edit; verify transition coherence at every boundary.

### Phase 4 — Validation Gate

Run the fifteen-bar pre-emission gate per `rules/pre-emission-gate.md` against the emitted findings artifact; the canonical per-bar check + Failure→action table lives at `rules/pre-emission-gate-bars.md` §1. Record one `pass | n/a (with reason)` line per bar in the §Validation Gate Outcome section. Dependency-audit-tier deltas:

- **M1 host-discovery** — findings honor the host's discovered language ecosystems and tooling versions; citations match the upstream advisory feeds.
- **M5 authority** — every finding cites a concrete `package@version` + a concrete advisory identifier (CVE / GHSA / OSV / yank marker); zero fabrications; zero unfilled confirmation placeholders.
- **M6 expertise** — the surfaced-gaps section names adjacent dependency-policy gaps beyond the audited scope (e.g., a missing SBOM the supply-chain audit would consume).
- **M7 option annotation** — every severity-triage and license-compatibility call carries `**Recommended**` + concrete-driver rationale.
- **M10 bidirectional binding** — the Findings Index reciprocally cites every per-dependency finding; no orphan Finding IDs.
- **M14 systemicity** — the artifact declares upstream (manifest tree + lockfiles), downstream (remediation surface + `/supply-chain-audit`), peers (sibling fortress artifacts), enforcers (pip-audit + safety + osv-scanner + host accepted-license list).
- **N/A bars (reason recorded):** M11 (single-sprint audit surface) · M13 (no executable code emitted) · M15 (production-ready applies at remediation time) · M9 (unless a non-obvious transitive-dependency graph warrants a diagram, then per `rules/visual-leverage.md`).

**Iterate on failure.** A single bar failure blocks promotion. The failing bar's Failure→action cell names the owning rule; revise, re-run, iterate until every bar passes within the three-round cap of `rules/pre-emission-gate-bars.md` §3 (then BLOCKED), then emit the attestation block.

---

## Critical Rules

- **NEVER author remediation.** The command's surface is diagnostic; remediation routes through `/plan-execute` or operator-initiated edits.
- **NEVER fabricate findings.** Every finding cites a concrete `package@version` and a concrete advisory identifier (CVE / GHSA / OSV / yank marker).
- **NEVER use vague-rationale phrases as the sole justification for a severity assignment.** Cite a concrete-driver class per `rules/interactive-questions-canonical-shapes.md` §3.2.1.
- **NEVER modify source.** The command is read-only against the manifest tree and lockfiles; only the findings artifact is written.
- **NEVER assume.** Invoke the structured-inquiry channel for any ambiguity in scope, severity, or axis attestation per the canonical channel.
- **Per-file destructive-op floor.** Destructive operations are out of scope for this command; were they to surface (e.g., orphan-manifest retirement during a related cycle), each would route through the structured-inquiry channel on a per-file basis per `rules/interactive-questions.md` §6 with the verbatim `no-default: user decision required` marker.

---

## Decision Tree

> Moved to `references/decision-tree.md`. SHOULD read it when a branch, gate failure, or state transition is unclear.

---

## Output

- The findings artifact at the suite's `_inputs/dependency-audit-findings.md` (executive summary + per-dependency findings + findings index + severity distribution + validation-gate attestation + bindings).
- An optional inventory working file at the suite's `_inputs/dependency-audit-inventory.md` (Phase 0 read inventory).
- An optional per-dependency drafts working directory at the suite's `_inputs/dependency-audit-per-dep/` (Phase 1 raw finding drafts before severity triage).

---

## Recommended Next Step

Invoke `/supply-chain-audit` to advance the audit-fortress sequence; `/supply-chain-audit` is the canonical successor per the 11-command audit-fortress canonical sequence.

## Installed Reference Paths

When this skill is installed by Apothem, resolve a repository-style reference against the installed directory for its first segment, unless a project-local file with the same relative path exists.

- `rules/<path>` is `<ROOT>/rules/<path>`
- `templates/<path>` is `<ROOT>/.apothem/support/templates/<path>`
- `schemas/<path>` is `<ROOT>/.apothem/support/schemas/<path>`
- `hooks/<path>` is `<ROOT>/.apothem/support/hooks/<path>`
- `conformity/<path>` is `<ROOT>/.apothem/support/conformity/<path>`
