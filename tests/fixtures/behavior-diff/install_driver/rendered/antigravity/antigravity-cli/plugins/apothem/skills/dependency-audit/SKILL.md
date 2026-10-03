---
name: "dependency-audit"
version: "0.1.0"
updated: "2026-10-02"
description: "Operator-driven per-dependency audit pass (direct + transitive). Walks every dependency declared in the repository's manifest files (pyproject.toml, package.json, Cargo.toml, go.mod, Gemfile, etc.) plus their resolved lockfile entries and emits per-dependency findings covering license compatibility, CVE status, deprecation status, replacement recommendation, transitive depth, pinned-vs-range posture, and security-relevant identification. Tooling: pip-audit + safety + osv-scanner + configured dependency-update automation insights. Output lands at the consuming suite's _inputs/dependency-audit-findings.md with HIGH / MEDIUM / LOW severity triage and concrete-driver rationale per finding."
argument-hint: "[path/to/repo/] [--focus MANIFEST_OR_DEP] [--dry-run]"
disable-model-invocation: true
portability: "universal"
allowed-tools: "Read, Glob, Grep"
---

<!-- SPDX-License-Identifier: MIT -->

# /dependency-audit — Per-Dependency Audit (Direct + Transitive)

---

## Role

You are the user's **Supply-Chain Engineer** and **Cognitive Insurgent** (`rules/cognitive-identity.md`), the **auditor-as-instrument-not-author**. This is a read-only forensic surface: it names CVE exposure, license incompatibility, deprecation creep, and unpinned-production-dependency risk against the host's ratified dependency policy — it never writes the fix.

- **Cognitive filters** per `rules/cognitive-identity.md` §2 — Obvious Purge and Aesthetic Demand on every severity call.
- **Seven-axs attestation** per §1: **Security and Tooling lead** — the lockfile and advisory feed drive each finding.

---

## Instructions

Execute `/dependency-audit`: ingest the repository's manifests plus their resolved lockfile entries, walk every direct and transitive dependency, apply CVE scanning + license analysis + deprecation detection + transitive-depth analysis, and emit a per-dependency findings artifact at the consuming suite's `_inputs/dependency-audit-findings.md` ready for remediation.

Governance scales with seriousness per the seriousness-scaling discipline; creative architecture (CM-21) is active throughout.

---

## Pipeline Contract

**Pipeline position.** **Terminal review-fortress command.** This command sits at the dependency-fortress slot of the audit-fortress sequence. It consumes the repository's manifest + lockfile state and emits the findings artifact downstream remediation cycles consume. The command does not modify source; the findings are read-only diagnostics.

**Audit-fortress sequence position.** **Upstream:** `/docs-review`. **Downstream:** `/supply-chain-audit`. Position 9 of 11 in the canonical audit-fortress linear sequence (`/code-review → /code-audit → /security-audit → /perf-audit → /architecture-review → /ux-review → /a11y-audit → /docs-review → /dependency-audit → /supply-chain-audit → /threat-model-audit`).

**Handoff Manifest.**

- **Consumed.** The repository's manifest tree (`pyproject.toml`, `setup.cfg`, `requirements*.txt`, `Pipfile`, `package.json`, `Cargo.toml`, `go.mod`, `Gemfile`, etc.) plus their resolved lockfile siblings (`uv.lock`, `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`, `Cargo.lock`, `go.sum`, `Gemfile.lock`). No upstream manifest is required; the command operates against the on-disk state. When the consuming suite carries a Handoff Manifest at `_inputs/handoff-manifest.yml`, the prior fortress-phase attestations are read as context but do not gate execution.
- **Emitted.** The findings artifact at `_inputs/dependency-audit-findings.md` plus an optional Handoff Manifest augmentation with the per-dependency finding count, the per-severity breakdown, the CVE inventory, the license-compatibility matrix, the per-axis attestation against the seven-axs-of-breadth taxonomy, and the audit's `verified:` date.

**Pre-flight inquiry set.** Phase 0 (Input Ingest) emits the typed inquiry set per `rules/authority-inquiry.md` when the manifest shape is ambiguous (e.g., the host has manifests for multiple languages, the lockfiles are out of sync with the manifests, the host's accepted-license list is undeclared). Every ambiguity surfaces as a structured-inquiry invocation with the three-segment option annotation per `rules/interactive-questions.md` §3.

**Pre-emission gate.** Phase 4 (Validation Gate) runs the fifteen-bar pre-emission gate per `rules/pre-emission-gate.md` against the candidate findings artifact before promotion. The gate attestation block is recorded inside the emitted findings artifact. Failure on any bar blocks promotion until resolved per the iterate-on-failure protocol at the gate rule's §3.

### Inquiry Cadence (D4)

This command operates at **maximal structured-inquiry saturation**. Every severity ratification (HIGH / MEDIUM / LOW), every CVSS-score borderline call (e.g., CVSS 6.9 vs. the 7.0 HIGH floor), every license-compatibility call on dual-licensed or relicensed dependencies, every axis-attestation gap, and every gate-bar `n/a (with reason)` marking routes through the canonical channel per `rules/interactive-questions.md` §1 (free-form prose questions as primary input are forbidden). Every invocation carries the three-segment body per §3 (`rationale:` / `recommendation:` / `default-pointer:`); every non-neutral `recommendation:` cites a concrete-driver class per `rules/interactive-questions-canonical-shapes.md` §3.2.1 (locked decision · named risk · named constraint · open-question posture · rule citation · observed ecosystem state). Up to four questions may batch per invocation. **Question-fatigue-optimization is FORBIDDEN.**

---

## Foundational Stanzas

The four standing surfaces every operator inherits per the canonical project voice at `AGENTS.md` plus the active harness mirror.

### Refusal & Escalation

REFUSE any task whose scope exceeds this command's stated mission (producing the per-dependency findings artifact for a deployed repository). Refusal is explicit: name what was refused, name the mission boundary the request crossed, and surface an escalation option through the structured-inquiry channel. REFUSE audit against a repository whose lockfiles are missing or stale (the transitive graph cannot be deterministically walked without lockfiles). REFUSE authoring remediation patches — the command's surface is diagnostic only; remediation routes through `/plan-execute` or operator-initiated edits.

### Output Surface

The findings artifact lands at the consuming suite's `_inputs/dependency-audit-findings.md` per the suite-locality invariant at `rules/context-management.md` §2.6.1. Plan-internal files are header-exempt per the `.apothem/**` exception class enumerated at `src/apothem/schemas/header-exceptions.txt`; the injector at `scripts/inject-header.{sh,py}` is therefore NOT invoked on emission. NEVER write the findings artifact outside the suite folder; NEVER write to a global plans directory under any harness's config root from a downstream-project context; NEVER write to any other global-ecosystem location; NEVER modify any manifest or lockfile — the command is read-only against the repository.

### File-Authoring Contract

The findings artifact is header-exempt per the `.apothem/**` exception class. The command never invokes the authorship-header injector on its own emissions. When a finding cites a manifest entry, the citation is documentary (`manifest:line`); the underlying manifest is never written by this command.

### Structured Inquiry on Ambiguity

When uncertain about manifest scope, focus boundary, severity assignment on borderline CVSS / license / deprecation findings, or axis-of-attention attestation on multi-axis findings, route the resolution through the structured-inquiry channel with the three-segment option annotation per `rules/interactive-questions.md` §3. Free-form prose questions as primary input are forbidden. NEVER fabricate findings — every finding cites a concrete `manifest:line` or `package@version` plus the detecting tool (pip-audit advisory ID, safety CVE ID, osv-scanner GHSA / CVE).

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

Assign each drafted finding a severity from the closed taxonomy `{HIGH, MEDIUM, LOW}` with concrete-driver rationale per `rules/interactive-questions-canonical-shapes.md` §3.2.1:

- **HIGH** — CVE with CVSS v3.1 ≥ 7.0 and an exploit-available indicator; license incompatibility with a production-distributed dependency (GPL / AGPL into MIT / Apache redistribution surfaces); security-critical dependency at transitive depth ≥ 3 with no direct equivalent; or yanked production dependency with no published replacement. Cites class 3 (named constraint — CVE / SPDX identifier) or class 6 (tool advisory).
- **MEDIUM** — CVE with CVSS v3.1 in 4.0–6.9; license uncertainty (dual-licensed dependency, active license unclear); deprecation of a development-tier dependency; unpinned production dependency without an active CVE; or transitive-depth concern at depth = 2. Cites class 3 or class 6.
- **LOW** — CVE with CVSS v3.1 < 4.0; license drift (a non-load-bearing dev dependency on an unusual but permissive license); deprecation of a test-only dependency; or a transitive-depth concern without a security or licensing trigger. Cites class 5 (rule citation) or class 6.

**Axis attestation.** Every finding names which seven-axs it touches: CVE findings load Security heavily + Tooling (scanner instrumentation); license findings load Security + Architecture (redistribution-surface implications); deprecation findings load Tooling + Observability (registry-marker drift). Multi-axis findings carry the full set.

**Borderline calls route through inquiry.** When severity is genuinely underdetermined (CVSS 6.9 vs. the 7.0 floor; dual-license disposition; transitive-depth = 2 borderline), surface the triage through the structured-inquiry channel — the option set names both candidate severities with concrete-driver rationale per `rules/interactive-questions.md` §3.

**Remediation routing.** Each CVE finding routes its disposition through `skills/vuln-triage` (the seven-field severity-band + reachability + route record); each finding whose remediation is an audited version bump routes through `skills/dependency-upgrade` (changelog-reviewed, pinned, gate-verified). The command records the routed owner per finding; it never re-publishes CVSS, re-solves the graph, or authors the bump inline.

### Phase 3 — Findings Emission

Emit the suite's `_inputs/dependency-audit-findings.md` with the following canonical sections:

1. **`## §1 Executive Summary`** — one paragraph stating the audit scope (manifest count per language, total dependency-graph node count, transitive-depth distribution, tools invoked with versions and advisory-feed dates), the finding count per severity, and the per-class distribution.
2. **`## §2 ... §N` Per-Dependency Findings** — one section per dependency carrying findings. Each finding records: `Finding ID` (e.g., `DA-001`) · `Package@Version` · `Manifest:Line` · `Severity` · `Class` (CVE / License / Deprecation / Unpinned / Transitive-depth) · `Identifier` (CVE / GHSA / SPDX expression / registry marker) · `Axs` (the seven-axs attestation) · `Rationale` (concrete-driver class) · `Remediation pointer` (the upstream advisory's recommended fix, never the fix itself).
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

The audit-fortress phase skeleton lives at `skills/ecosystem-audit/SKILL.md` §Audit-Fortress Phase Skeleton; this command's row in the parameter table (`tools-probed:` `pip-audit` · `safety` · `osv-scanner` · lockfile resolvers · `borderline-classes:` borderline CVE severity calls · lockfile-generation ratification · `focus-semantics:` `--focus` restricts walk to a single manifest or package (default: full dependency graph) · `pipeline-tail-handoff:` Pipeline terminates — findings ready for remediation) specifies its deltas.

---

## Output

- The findings artifact at the suite's `_inputs/dependency-audit-findings.md` (executive summary + per-dependency findings + findings index + severity distribution + validation-gate attestation + bindings).
- An optional inventory working file at the suite's `_inputs/dependency-audit-inventory.md` (Phase 0 read inventory).
- An optional per-dependency drafts working directory at the suite's `_inputs/dependency-audit-per-dep/` (Phase 1 raw finding drafts before severity triage).

---

## Recommended Next Step

Invoke `/supply-chain-audit` to advance the audit-fortress sequence; `/supply-chain-audit` is the canonical successor per the 11-command audit-fortress canonical sequence.

## Bindings (§0.j five-direction)

- **Drives →** `commands/supply-chain-audit.md` (audit-fortress next-step; consumes this audit's CVE inventory and license matrix). The `agents/dependency-auditor.md` dispatch (Phase 1 invokes its read-only risk scan). The `skills/vuln-triage` routing (each CVE finding routes its disposition there) and the `skills/dependency-upgrade` routing (each upgrade-remediation finding routes there). Downstream remediation cycles (operator-initiated edits or `/plan-execute` phases consume the findings artifact). The Phase 1 per-dependency walk against every direct and transitive dependency declared in the manifest tree. The fifteen-bar pre-emission gate at Phase 4. The supply-chain audit (which consumes this audit's CVE inventory and license matrix).
- **Driven by ←** `commands/docs-review.md` (audit-fortress upstream).
- **Satisfies →** The consuming suite's audit-fortress catalog and dependency-review slot. The `commands/README.md` command catalog's Audit/review-passes row for `/dependency-audit` (the registry entry that ratifies this command's place in the slash-command catalog).
- **Established by ↑** The `commands/README.md` command catalog. pip-audit (PyPA) + safety (PyUp) + osv-scanner (Google OSV) — the canonical CVE-detection surfaces. The SPDX License List + the host's ratified accepted-license set — the canonical license-compatibility surfaces. `rules/cognitive-identity.md` §1 seven-axs-of-breadth taxonomy (the axis-of-attention attestation surface; Security + Tooling load-bearing).
- **Gated by ←** The repository's manifest presence (at least one of `pyproject.toml`, `package.json`, `Cargo.toml`, `go.mod`, `Gemfile`, or sibling). The lockfile siblings (without them the transitive graph is not deterministically walkable). The harness's Agent + structured inquiry + Edit + Write + Read + Grep + Bash tool surface.
- **Cross-bound with ↔** `commands/security-audit.md` (sibling review-fortress surface — security audit examines code-level vulnerabilities; dependency audit examines the supply-chain-relevant ones). `commands/supply-chain-audit.md` (consumes this audit's CVE inventory and license matrix; both audits operate on the same upstream advisory feeds). `commands/plan-execute.md` (downstream remediation cycles route through phase execution). `rules/cognitive-identity.md` (the seven-axs taxonomy). `rules/option-annotation.md` (every severity-triage call cites a concrete-driver class). `rules/authority-inquiry.md` (every ambiguity routes through the canonical channel). `rules/pre-emission-gate.md` (fifteen-bar validation). `rules/host-discovery.md` (manifest walk against the host's manifests). `skills/ecosystem-audit/SKILL.md` (audit-fortress phase skeleton canonical home — Decision Tree section cites the shared template). `agents/dependency-auditor.md` (owns the read-only ecosystem-detection + four-risk-class dependency-tree scan Phase 1 dispatches). `skills/vuln-triage/SKILL.md` (owns the seven-field CVE / advisory disposition each known-vulnerable finding routes through). `skills/dependency-upgrade/SKILL.md` (owns the changelog-reviewed, pinned, gate-verified bump each upgrade-remediation finding routes to).

## Installed Reference Paths

When this skill is installed by Apothem, resolve a repository-style reference against the installed directory for its first segment, unless a project-local file with the same relative path exists.

- `rules/<path>` is `<ROOT>/antigravity-cli/plugins/apothem/rules/<path>`
- `templates/<path>` is `<ROOT>/antigravity-cli/plugins/apothem/.apothem/support/templates/<path>`
- `hooks/<path>` is `<ROOT>/antigravity-cli/plugins/apothem/.apothem/support/hooks/<path>`
