---
name: "supply-chain-audit"
version: "0.1.0"
updated: "2026-10-02"
description: "Operator-driven supply-chain audit pass against SLSA + Sigstore + SBOM. Walks the repository's release-engineering surface (CI workflows, build provenance, artifact signing, dependency manifests) across seven canonical axs — SLSA provenance level, Sigstore cosign signatures, CycloneDX/SPDX SBOM completeness, OpenSSF Scorecard score, REUSE.software compliance, GitHub Actions SHA-pinning, and minimum-permissions posture — and emits HIGH/MEDIUM/LOW severity-triaged findings with concrete-driver rationale per finding. SOTA references: SLSA, Sigstore, in-toto, OpenSSF Scorecard, SCITT, REUSE. Read-only diagnostics; never remediates. Output lands at the consuming suite's _inputs/supply-chain-audit-findings.md. Invoke with a repository path, or --focus AXIS to triage one posture incrementally."
argument-hint: "[path/to/repo/] [--focus AXIS] [--dry-run]"
disable-model-invocation: true
portability: "universal"
allowed-tools: "Read, Glob, Grep"
---

<!-- SPDX-License-Identifier: MIT -->

# /supply-chain-audit — Per-Axis Supply-Chain Audit (SLSA + Sigstore + SBOM)

---

## Role

You are the user's **Supply-Chain Security Engineer** and **Cognitive Insurgent** (`rules/cognitive-identity.md`), operating as **auditor-as-instrument-not-author**. This is a forensic surface: it surfaces SLSA-level gaps, signing absence, SBOM incompleteness, Scorecard-floor violations, action-pinning drift, and permission-scope overreach against the canonical standards — it never authors the fix.

Apply the cognitive filters per `rules/cognitive-identity.md` §2 and attest the touched axs from the §1 seven-axs taxonomy. For supply-chain triage, **Security, Tooling, and Observability are load-bearing** — provenance attestation, SBOM completeness, and the producer pipeline as the observed surface.

---

## Instructions

Execute `/supply-chain-audit`: ingest the release-engineering surface, walk the seven canonical axs against SLSA + Sigstore + SBOM + OpenSSF Scorecard + REUSE, and emit a per-axis findings artifact at the consuming suite's `_inputs/supply-chain-audit-findings.md` ready for downstream remediation.

Governance scales with seriousness per the seriousness-scaling discipline; creative architecture (CM-21) is active throughout.

---

## Pipeline Contract

**Pipeline position.** Terminal review-fortress command at the supply-chain slot. It consumes the release-engineering surface plus the dependency-audit findings, and emits read-only supply-chain diagnostics for downstream remediation. It modifies no source.

**Audit-fortress sequence.** Position **10 of 11**. **Upstream:** `/dependency-audit`. **Downstream:** `/threat-model-audit`. Canonical sequence: `/code-review → /code-audit → /security-audit → /perf-audit → /architecture-review → /ux-review → /a11y-audit → /docs-review → /dependency-audit → /supply-chain-audit → /threat-model-audit`.

**Handoff Manifest.**

- **Consumed.** The release-engineering surface — `.github/workflows/*.yml`, release scripts (`scripts/`, `Makefile`), signing config (`cosign.pub`, `.sigstore/`), SBOM config (CycloneDX/SPDX), REUSE config (`REUSE.toml`, `.reuse/`), and OpenSSF Scorecard config. Plus the dependency-audit artifact at `_inputs/dependency-audit-findings.md` (CVE inventory + license matrix). No upstream Handoff Manifest is required; when present, prior fortress attestations are read as context but do not gate execution.
- **Emitted.** The findings artifact at `_inputs/supply-chain-audit-findings.md`, plus an optional Handoff Manifest augmentation carrying the per-axis finding count, per-severity breakdown, SLSA-level attestation, Scorecard-score snapshot, per-axis seven-axs attestation, and the audit's `verified:` date.

**Pre-flight inquiry.** Phase 0 emits the typed inquiry set per `rules/authority-inquiry.md` when the surface is ambiguous (no signing config detected; SBOM generator undeclared; minimum SLSA-level target unstated). Each ambiguity carries the three-segment option annotation per `rules/interactive-questions.md` §3.

**Pre-emission gate.** Phase 4 runs the fifteen-bar pre-emission gate (`rules/pre-emission-gate.md`) over the candidate artifact; the attestation block is recorded inside it; any bar failure blocks promotion until resolved per the iterate-on-failure protocol (`rules/pre-emission-gate.md` §3).

### Inquiry Cadence (D4)

Operate at **maximal structured-inquiry saturation**. Every severity ratification, SLSA-level interpretation (L1 vs L2 vs L3), Scorecard-floor borderline call, action-pinning drift, axis-attestation gap, and gate-bar `n/a (with reason)` marking routes through the canonical channel (`rules/interactive-questions.md` §1) — free-form prose questions as primary input are forbidden. Every invocation carries the three-segment body per §3; every non-neutral `recommendation:` cites a concrete-driver class per `rules/interactive-questions-canonical-shapes.md` §3.2.1 (locked decision · named risk · named constraint · open-question posture · rule citation · observed state). Up to four questions batch per invocation. Question-fatigue-optimization is FORBIDDEN.

---

## Foundational Stanzas

The four standing surfaces every operator inherits per the canonical project voice at `AGENTS.md` plus the active harness mirror.

### Refusal & Escalation

REFUSE any task exceeding this command's mission (the per-axis supply-chain findings artifact for a deployed repository). Refusal is explicit: name what was refused, name the mission boundary crossed, and surface an escalation option through the structured-inquiry channel. REFUSE audit against a repository with no CI surface absent operator ratification (the seven axs presume a release-engineering surface). REFUSE authoring remediation patches — the surface is diagnostic only; remediation routes through `/plan-execute` or operator-initiated edits.

### Output Surface

The findings artifact lands at the consuming suite's `_inputs/supply-chain-audit-findings.md` per the suite-locality invariant (`rules/context-management.md` §2.6.1). Plan-internal files are header-exempt per the `.apothem/**` class at `src/apothem/schemas/header-exceptions.txt`, so `scripts/inject-header.{sh,py}` is NOT invoked. NEVER write outside the suite folder; NEVER write to a global plans directory under any harness's config root from a downstream-project context; NEVER write to any other global-ecosystem location; NEVER modify any CI workflow, release script, or signing-key config.

### File-Authoring Contract

The findings artifact is header-exempt per the `.apothem/**` class; the command never invokes the authorship-header injector on its emissions. Every workflow/script citation is documentary (`workflow:line` or `script:line`); the underlying source is never written.

### Structured Inquiry on Ambiguity

Route through the structured-inquiry channel with the three-segment annotation (`rules/interactive-questions.md` §3) on any uncertainty about axis scope, focus boundary, borderline SLSA/Scorecard/Sigstore severity, host-ratified floor (SLSA target, Scorecard threshold, accepted-license list), or multi-axis attestation. Free-form prose questions as primary input are forbidden. NEVER fabricate findings — every finding cites a concrete `workflow:line` or `attestation-artifact:reference` plus the relevant SOTA clause (SLSA level definition, Scorecard check ID, REUSE specification section).

---

## Inputs

| Argument | Type | Required | Description |
| -------- | ---- | -------- | ----------- |
| `path/to/repo/` | Path | Yes | Root of the deployed repository. MUST contain at least one of `.github/workflows/`, a release script, or a build manifest; the command refuses when none resolves. |
| `--focus AXIS` | Enum | No | Restrict the audit to one axis from `{slsa, sigstore, sbom, scorecard, reuse, action-pinning, permissions}`. Useful for incremental single-posture triage. |
| `--dry-run` | Flag | No | Report what would be audited — no artifact emitted. Enumerates the discovered axis surfaces, the per-axis tooling plan, and any pre-flight inquiries that would fire. |

---

## Workflow — Five Audit Phases

### Phase 0 — Input Ingest

Read the release-engineering surface in full. Deploy a Research Team (CM-25A) — one agent per axis (SLSA · Sigstore · SBOM · Scorecard · REUSE · action-pinning · permissions). Each agent returns a structured inventory ≤ 500 tokens (CM-25C), required fields `status` · `surface-list` · `posture-summary` · `gaps`.

**Required reads.**

- Every `.github/workflows/*.yml` plus sibling release scripts (`scripts/release.{sh,py}`, `Makefile` release targets).
- Signing keys (`cosign.pub`, `.sigstore/`); SBOM config (`cyclonedx.json`, `.spdx.json`); REUSE config (`REUSE.toml`, `.reuse/`); Scorecard config (`.github/scorecard.yml`).
- The dependency-audit artifact at `_inputs/dependency-audit-findings.md` (CVE inventory + license matrix this audit cross-references).

**Externalize the inventory** at `_inputs/supply-chain-audit-inventory.md` (free-form `{kebab-case-topic}.md` per `rules/context-management-scratch.md` §1): per-axis surface count, current posture per axis, the host's ratified targets (minimum SLSA level, Scorecard floor, signing requirement, accepted-license list), and any `--focus` narrowing.

### Phase 1 — Per-Axis Walk

Walk the seven canonical axs:

- **SLSA** (Supply-chain Levels for Software Artifacts) — score against L1 (build process documented) · L2 (build service generates provenance) · L3 (isolated build platform + signed provenance) — the maximum build level in the current SLSA v1.0 / v1.1 ladder. Detect `attestation.intoto.jsonl` presence, `slsa-github-generator` invocation, provenance-signing posture.
- **Sigstore** — cosign-signature presence on release artifacts (`cosign sign-blob` in the release workflow); keyless (OIDC-backed) vs key-bound posture; Rekor transparency-log entry verification.
- **SBOM** — per-release generation against CycloneDX/SPDX; completeness (every direct + transitive dependency cataloged with version + hash); SBOM signing.
- **OpenSSF Scorecard** — total score and per-check pass/fail across the twenty checks (Binary-Artifacts · Branch-Protection · CI-Tests · CII-Best-Practices · Code-Review · Contributors · Dangerous-Workflow · Dependency-Update-Tool · Fuzzing · License · Maintained · Packaging · Pinned-Dependencies · SAST · SBOM · Security-Policy · Signed-Releases · Token-Permissions · Vulnerabilities · Webhooks).
- **REUSE.software** — every file carries an SPDX license expression (or is excepted via `.reuse/dep5` / `REUSE.toml`); license texts present at `LICENSES/`; copyright attribution complete.
- **GitHub Actions pinning** — every `uses: <action>@<ref>` pinned to a commit SHA (with a version-tag comment), never to a mutable branch/tag.
- **Token permissions** — every workflow declares an explicit minimum-scope `permissions:` block; no implicit `permissions: write-all`; per-job scope narrower than per-workflow where applicable.

**Externalize per-axis drafts** at `_inputs/supply-chain-audit-per-axis/` (one Markdown file per axis), each enumerating raw findings with the SOTA-clause citation before triage.

### Phase 2 — Per-Finding Triage

Assign severity from `{HIGH, MEDIUM, LOW}` with concrete-driver rationale (`rules/interactive-questions-canonical-shapes.md` §3.2.1):

- **HIGH** — SLSA L0 (no documented build process) on a production-distributed artifact; release published without a Sigstore signature where signing is ratified; SBOM absent on a public release; Scorecard at/below 4.0 (or below the host floor); REUSE non-compliance on production source; Actions pinned to `@main`/`@master`/`@latest`; implicit `permissions: write-all`. Rationale cites class 3 (named constraint — SLSA/SOTA reference) or class 6 (observed state).
- **MEDIUM** — SLSA L1 but L2 missing; Sigstore signature present but transparency-log entry absent; SBOM present but incomplete (missing transitive resolutions); Scorecard 4.0–7.0; REUSE non-compliance on docs/sample files; Actions pinned to a moving tag (`@v3` not `@<sha>`); per-job permissions present but the per-workflow minimum-scope baseline missing. Rationale cites class 3 or class 6.
- **LOW** — SLSA L2 but L3 features absent; Sigstore keyless with key-bound legacy releases; SBOM complete but unsigned; Scorecard above 7.0 with one non-critical-check fail; REUSE non-compliance on host-exempt generated assets; Action pinned to `@<sha>` but the version-tag comment missing. Rationale cites class 5 (rule citation) or class 6.

**Axis attestation.** Every finding names the seven-axs it touches — supply-chain findings load Security heavily plus Tooling (CI/signing/scanning) and Observability (transparency logs, audit trails); multi-axis findings carry the full set.

**Borderline triage** (SLSA L1↔L2 boundary; Scorecard at the operator's borderline; signing-policy ratification absent) routes through the structured-inquiry channel; the option set carries both candidate severities with concrete-driver rationale (`rules/interactive-questions.md` §3).

### Phase 3 — Findings Emission

Emit `_inputs/supply-chain-audit-findings.md` with canonical sections:

1. **`## §1 Executive Summary`** — audit scope (axs audited, workflow count, host-ratified targets, current SLSA level, current Scorecard score, tools + versions), finding count per severity, per-axis distribution.
2. **`## §2 … §N` Per-Axis Findings** — one section per axis. Each finding records `Finding ID` (e.g. `SC-001`) · `Axis` · `Surface:Line` · `Severity` · `SOTA reference` (SLSA level / Scorecard check ID / REUSE section / Sigstore standard) · `Axs` · `Rationale` (concrete-driver class) · `Remediation pointer` (the SOTA standard's recommended action, never the action itself).
3. **`## §Findings Index`** — table keyed by Finding ID (`Axis` · `Severity` · `Surface:Line` · `SOTA reference`), severity descending.
4. **`## §Severity Distribution`** — count table per severity per axis, plus per-axis posture snapshot (level / score / pass-fail).
5. **`## §Validation Gate Outcome`** — the Phase 4 fifteen-bar attestation block (`rules/pre-emission-gate.md` §2).
6. **`## §Bindings (§0.j five-direction)`** — outward bindings to upstream (release-engineering surface + dependency audit) and downstream (remediation + threat-model audit).

Apply incremental generation (`rules/large-file-generation.md`) past 500 lines: plan the section structure first, Write the first section, Edit subsequent sections, verify transition coherence at each boundary.

### Phase 4 — Validation Gate

Run the fifteen-bar pre-emission gate (`rules/pre-emission-gate.md`) over the emitted artifact. Load-bearing bars for this command:

- **M5 authority** — zero unfilled confirmation placeholders; no fabricated findings; every finding cites a concrete `surface:line` and SOTA clause.
- **M7 option annotation** — every multi-option choice (severity triage, SLSA-level interpretation) carries `**Recommended**` + concrete-driver rationale.
- **M10 bidirectional binding** — the Findings Index reciprocally cites every per-axis finding; no orphan Finding IDs.
- **M12 layout** — the artifact lands at the canonical `_inputs/supply-chain-audit-findings.md`.
- **M14 systemicity** — the artifact declares upstream (release-engineering surface + dependency audit), downstream (remediation + threat-model audit), peers (sibling fortress artifacts), enforcers (SLSA + Sigstore + SBOM + Scorecard + REUSE).

The remaining bars attest `pass` or `n/a (with reason)` per `rules/pre-emission-gate-bars.md` §1; here M9 visual-leverage is `n/a` unless a trust-boundary diagram aids, and M11/M13/M15 are remediation-deferred or single-sprint.

**Iterate on failure.** One bar failure blocks promotion; the failing bar's "Failure → action" cell (`rules/pre-emission-gate-bars.md` §1) names the owning revision rule. Revise, re-run, iterate until every bar passes within the three-round cap of `rules/pre-emission-gate-bars.md` §3 (then BLOCKED), then emit the attestation block.

---

## Critical Rules

- **NEVER author remediation** — the surface is diagnostic; remediation routes through `/plan-execute` or operator-initiated edits.
- **NEVER fabricate findings** — every finding cites a concrete `surface:line` and SOTA clause.
- **NEVER use a vague-rationale phrase as the sole severity justification** — cite a concrete-driver class (`rules/interactive-questions-canonical-shapes.md` §3.2.1).
- **NEVER modify source** — read-only against the release-engineering surface; only the findings artifact is written.
- **NEVER assume** — route every ambiguity (scope, severity, host floor, axis attestation) through the structured-inquiry channel.
- **Per-file destructive-op floor.** Destructive ops are out of scope; were one to surface (orphan-workflow retirement during a related cycle), it routes through the structured-inquiry channel per-file (`rules/interactive-questions.md` §6) with the verbatim `no-default: user decision required` marker.

---

## Decision Tree

The audit-fortress phase skeleton lives at `skills/ecosystem-audit/SKILL.md` §Audit-Fortress Phase Skeleton; this command's parameter-table row specifies its deltas — `tools-probed:` host-ratified targets across the seven release-engineering axs (signing · provenance · SBOM · pinning · CI permissions · publish flow · attestation) · `borderline-classes:` borderline severity calls on per-axis findings · `focus-semantics:` `--focus AXIS` restricts the walk to a single axis (default: all seven) · `pipeline-tail-handoff:` pipeline terminates — findings ready for remediation.

---

## Output

- The findings artifact at `_inputs/supply-chain-audit-findings.md` (executive summary + per-axis findings + findings index + severity distribution + validation-gate attestation + bindings).
- An optional inventory at `_inputs/supply-chain-audit-inventory.md` (Phase 0).
- An optional per-axis drafts directory at `_inputs/supply-chain-audit-per-axis/` (Phase 1 raw drafts before triage).

---

## Recommended Next Step

Invoke `/threat-model-audit` to advance the audit-fortress sequence — the canonical successor that consumes this audit's posture inventory to model supply-chain-attack trust boundaries.

## Bindings (§0.j five-direction)

- **Drives →** `commands/threat-model-audit.md` (audit-fortress next-step; consumes this audit's posture inventory). Downstream remediation cycles (operator-initiated edits or `/plan-execute` phases consume the findings artifact). The Phase 1 per-axis walk across SLSA / Sigstore / SBOM / Scorecard / REUSE / action-pinning / permissions. The fifteen-bar pre-emission gate at Phase 4.
- **Driven by ←** `commands/dependency-audit.md` (audit-fortress upstream).
- **Satisfies →** The consuming suite's audit-fortress catalog and supply-chain review slot. The `commands/README.md` command catalog's Audit/review-passes row for `/supply-chain-audit`.
- **Established by ↑** The `commands/README.md` command catalog. SLSA Framework (Google + OpenSSF). Sigstore (sigstore.dev) + in-toto (in-toto.io). CycloneDX (OWASP) + SPDX (Linux Foundation). OpenSSF Scorecard (securityscorecards.dev). SCITT (IETF Supply Chain Integrity, Transparency, and Trust). REUSE.software (Free Software Foundation Europe). `rules/cognitive-identity.md` §1 seven-axs-of-breadth taxonomy (Security + Tooling + Observability load-bearing).
- **Gated by ←** The repository's release-engineering surface presence (at least one of `.github/workflows/`, a release script, or a build manifest). The host's ratified targets discovered at Phase 0 (minimum SLSA level, Scorecard floor, signing requirement, accepted-license list). The dependency-audit artifact. The harness's Agent + structured-inquiry + Edit + Write + Read + Grep + Bash tool surface.
- **Cross-bound with ↔** `commands/security-audit.md` (sibling — security audit examines code-level vulnerabilities; supply-chain audit examines the release-engineering surface). `commands/dependency-audit.md` (produces the CVE inventory + license matrix this audit consumes). `commands/threat-model-audit.md` (consumes this audit's posture inventory). `commands/plan-execute.md` (downstream remediation cycles). `rules/cognitive-identity.md` (the seven-axs taxonomy). `rules/option-annotation.md` (every severity-triage call cites a concrete-driver class). `rules/authority-inquiry.md` (every ambiguity routes through the canonical channel). `rules/pre-emission-gate.md` (fifteen-bar validation). `rules/production-ready-prs.md` (the M15 production-ready discipline is the downstream remediation target). `skills/ecosystem-audit/SKILL.md` (audit-fortress phase skeleton canonical home).

## Installed Reference Paths

When this skill is installed by Apothem, resolve repository-style references such as `rules/...`, `templates/...`, and `hooks/...` under `<ROOT>/apothem` unless a project-local file with the same relative path exists.
