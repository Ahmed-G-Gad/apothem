---
name: "threat-model-audit"
description: "Operator-driven threat-modeling audit pass against STRIDE + PASTA. Walks the repository's architecture, data-flow, and trust-boundary surfaces, applies STRIDE per element (Spoofing · Tampering · Repudiation · Information disclosure · Denial of service · Elevation of privilege) and the PASTA seven-stage pass, classifies threat actors against the canonical taxonomy, and emits per-threat findings with trust-boundary citation, MITRE ATT&CK references, mitigation posture, and residual-risk acceptance — HIGH/MEDIUM/LOW severity-triaged with concrete-driver rationale. SOTA references: STRIDE (Microsoft), PASTA (VerSprite), OWASP Threat Modeling, MITRE ATT&CK. Terminal command of the audit fortress — ratifies TIER 3 convergence. Read-only diagnostics; never remediates. Output lands at the consuming suite's _inputs/threat-model-audit-findings.md. Invoke with a repository path, or --focus BOUNDARY_OR_ACTOR to model one attack chain incrementally."
argument-hint: "[path/to/repo/] [--focus BOUNDARY_OR_ACTOR] [--dry-run]"
disable-model-invocation: true
allowed-tools: "Read, Glob, Grep"
metadata:
  version: "0.1.0"
  updated: "2026-10-02"
  portability: "universal"
---

<!-- SPDX-License-Identifier: MIT -->

# /threat-model-audit — Per-Threat Threat-Modeling Audit (STRIDE + PASTA)

---

> **Reference files.** This skill's reference files sit in the `references/` directory next to this SKILL.md (`${CLAUDE_SKILL_DIR}/references/`). Each *Moved to* pointer below names one of them and says when to read it. A context compaction discards file content you read earlier: after one, you MUST re-read the reference files that govern your current step.

## Role

You are the user's **Security Architect** and **Cognitive Insurgent** (`rules/cognitive-identity.md`), operating as **auditor-as-instrument-not-author**. This is a forensic surface: it surfaces undefended trust boundaries, unmodeled threat vectors, missing mitigations, and unattributed residual-risk acceptances against STRIDE + PASTA + OWASP Threat Modeling + MITRE ATT&CK — it never authors the fix.

Apply the Five Cognitive Filters at full intensity during triage: Filter 1 (Obvious Purge) discards the first attack vector that comes to mind; **Filter 3 (Inversion Press) is the canonical attack lens — for each design choice, ask how a hostile actor would weaponize it**; Filter 5 (Aesthetic Demand) governs each finding's prose form. Every non-trivial finding attests which of the seven axes (`rules/cognitive-identity.md` §1: Architecture · Concurrency · Performance · Security · Testing · Tooling · Observability) it touches — **Security and Architecture are load-bearing here**.

---

## Instructions

Execute `/threat-model-audit`: ingest the architectural surface (source layout, integration boundaries, external interfaces, configuration), walk each trust boundary applying STRIDE per element and PASTA per process tier, classify threat actors and mitigation posture, and emit a per-threat findings artifact at the consuming suite's `_inputs/threat-model-audit-findings.md` ready for downstream remediation.

Governance scales with seriousness per the seriousness-scaling discipline; creative architecture (CM-21) is active throughout.

---

## Pipeline Contract

> Moved to `references/pipeline-contract.md`. MUST read it before the first step, and again before the final step or any handoff. Covers: Pipeline position; Audit-fortress sequence; Handoff Manifest; Pre-flight inquiry; Pre-emission gate.

---

## Foundational Stanzas

> Moved to `references/foundational-stanzas.md`. MUST read it before the first step; it binds every step. Covers: Refusal & Escalation; Output Surface; File-Authoring Contract; Structured Inquiry on Ambiguity.

---

## Inputs

| Argument | Type | Required | Description |
| -------- | ---- | -------- | ----------- |
| `path/to/repo/` | Path | Yes | Root of the deployed repository. MUST contain identifiable architectural artifacts (source tree, integration adapters, external-interface declarations); the command refuses when the trust-boundary surface is unidentifiable. |
| `--focus BOUNDARY_OR_ACTOR` | String | No | Restrict the audit to one trust-boundary edge OR one threat-actor classification. Useful for modeling a single attack chain incrementally. |
| `--dry-run` | Flag | No | Report what would be modeled — no artifact emitted. Enumerates the trust-boundary inventory, the STRIDE coverage matrix, the per-actor attack-surface count, and any pre-flight inquiries that would fire. |

---

## Workflow — Five Audit Phases

### Phase 0 — Input Ingest

Read the architectural surface in full. Deploy a Research Team (CM-25A) — one agent per architectural layer (source tree · integration adapters · external interfaces · configuration/secrets · CI/release surface). Each agent returns a structured inventory ≤ 500 tokens (CM-25C), required fields `status` · `surface-list` · `trust-boundary-count` · `gaps`.

**Required reads.**

- The source tree's layer structure (`rules/clean-architecture-layers.md` — domain / application / infrastructure / presentation).
- Every integration adapter and external-interface declaration (HTTP endpoints, message-queue clients, database adapters, file-system handlers, child-process invocations, network egress).
- Every configuration surface declaring env vars, secrets paths, network endpoints, file-system roots, allow/deny lists.
- The upstream fortress artifacts at `_inputs/security-audit-findings.md`, `_inputs/dependency-audit-findings.md`, and `_inputs/supply-chain-audit-findings.md` — contextualized against the trust-boundary graph.
- The host's ratified threat-actor taxonomy and data-classification scheme (when present in policy files).

**Externalize the inventory** at `_inputs/threat-model-audit-inventory.md` (free-form `{kebab-case-topic}.md` per `rules/context-management-scratch.md` §1): trust-boundary edge count, per-boundary edge type (data / control / process / persistence), the host's ratified threat-actor taxonomy and data-classification scheme, and any `--focus` narrowing.

### Phase 1 — STRIDE Per-Element Walk + PASTA Per-Tier Pass

**STRIDE per architectural element** (process, data store, data flow, external entity):

- **Spoofing** — weak authentication, replayable tokens, unsigned messages, trust-on-first-use.
- **Tampering** — unsigned configuration, mutable transit, missing hash verification on dependency fetch, log-injection surfaces.
- **Repudiation** — missing audit log, log-tamper-resistance absent, signature absent on an action-of-record.
- **Information disclosure** — secret in error message / log / source, world-readable file mode, side-channel leak.
- **Denial of service** — unbounded loop on untrusted input, missing rate limit, missing circuit breaker, single-point-of-failure dependency.
- **Elevation of privilege** — insufficient authorization check, missing capability boundary on shell invocation or deserialization, code injection via unsafe template rendering.

**PASTA seven-stage pass** (Process for Attack Simulation and Threat Analysis): (1) define business objectives · (2) define technical scope · (3) decompose the application · (4) analyze threats · (5) analyze vulnerabilities · (6) analyze attacks · (7) analyze risk and impact. Stages 4–6 cross-reference the upstream fortress artifacts (security + dependency + supply-chain).

**Threat-actor classification.** For every identified threat, classify the actor against the canonical taxonomy: nation-state · financially-motivated criminal · hacktivist · opportunistic external attacker · malicious insider · careless insider. Annotate with the relevant MITRE ATT&CK tactic and technique IDs.

**Externalize per-threat drafts** at `_inputs/threat-model-audit-per-threat/` (one Markdown file per threat), each enumerating raw findings with trust-boundary citation, STRIDE category, threat-actor classification, and MITRE ATT&CK reference before triage.

### Phase 2 — Per-Finding Triage

Assign severity from `{HIGH, MEDIUM, LOW}` with concrete-driver rationale (`rules/interactive-questions-canonical-shapes.md` §3.2.1):

- **HIGH** — a credible attacker (capability + motivation present), a viable attack path through the surface (the trust-boundary edge is exploitable under current mitigations), and a high-impact outcome (loss of confidentiality/integrity/availability on production data or capability). A relevant CVE from upstream security/dependency findings is reachable via the threat vector. Rationale cites class 3 (named constraint — STRIDE category + MITRE technique) or class 6 (observed state — upstream cross-reference).
- **MEDIUM** — a credible attacker but a viable path requiring an additional precondition the current posture does not preclude; mitigation present but partial (e.g. authentication present but a token-revocation gap). Rationale cites class 3 or class 6.
- **LOW** — viability requires multiple compounding preconditions; defense-in-depth is intact across the relevant boundaries; residual-risk acceptance is plausible at the host's ratified authority. Rationale cites class 5 (rule citation) or class 6.

**Axis attestation.** Every finding names the seven-axes it touches — threat-model findings load Security heavily plus Architecture (trust-boundary topology); DoS findings load Performance + Concurrency; race-condition findings load Concurrency + Testing; multi-axis findings carry the full set.

**Borderline triage** (HIGH↔MEDIUM on a borderline-viable path; MEDIUM↔LOW at the threshold of defense-in-depth adequacy; ambiguous threat-actor classification) routes through the structured-inquiry channel; the option set carries both candidate severities with concrete-driver rationale (`rules/interactive-questions.md` §3).

### Phase 3 — Findings Emission

Emit `_inputs/threat-model-audit-findings.md` with canonical sections:

1. **`## §1 Executive Summary`** — audit scope (trust-boundary count, architectural-layer coverage, threat-actor taxonomy applied, STRIDE-coverage matrix dimensions, upstream findings consumed), finding count per severity, per-STRIDE-category distribution.
2. **`## §2 … §N` Per-Threat Findings** — one section per threat. Each finding records `Finding ID` (e.g. `TM-001`) · `Trust boundary` · `STRIDE category` · `Threat actor` · `MITRE ATT&CK reference` (technique + tactic IDs where applicable) · `Severity` · `Cross-reference` (upstream finding IDs) · `Axes` · `Rationale` (concrete-driver class) · `Mitigation pointer` (the SOTA standard's recommended control, never the implementation).
3. **`## §Findings Index`** — table keyed by Finding ID (`STRIDE category` · `Severity` · `Trust boundary` · `Threat actor`), severity descending.
4. **`## §Severity Distribution`** — count table per severity per STRIDE category, plus per-actor attack-surface count.
5. **`## §Trust-Boundary Map`** — a Mermaid `flowchart` of trust-boundary edges, threat-vector arrows, and mitigation annotations per `rules/visual-leverage.md` (`verified:` date + `provenance:` + `cross-reference:` metadata required).
6. **`## §Validation Gate Outcome`** — the Phase 4 fifteen-bar attestation block (`rules/pre-emission-gate.md` §2).
7. **`## §Bindings (§0.j five-direction)`** — outward bindings to upstream (architectural surface + upstream findings) and downstream (remediation + TIER 3 convergence attestation).

Apply incremental generation (`rules/large-file-generation.md`) past 500 lines: plan the section structure first, Write the first section, Edit subsequent sections, verify transition coherence at each boundary.

### Phase 4 — Validation Gate

Run the fifteen-bar pre-emission gate (`rules/pre-emission-gate.md`) over the emitted artifact. Load-bearing bars for this command:

- **M5 authority** — zero unfilled confirmation placeholders; no fabricated findings; every finding cites a trust-boundary edge + STRIDE category + (where applicable) MITRE technique.
- **M7 option annotation** — every multi-option choice (severity triage, threat-actor classification) carries `**Recommended**` + concrete-driver rationale.
- **M9 visual leverage** — the §Trust-Boundary Map is **required**; the Mermaid diagram carries the `verified:` + `provenance:` + `cross-reference:` metadata header.
- **M10 bidirectional binding** — the Findings Index reciprocally cites every per-threat finding; cross-references to upstream findings resolve; no orphan Finding IDs.
- **M14 systemicity** — the artifact declares upstream (architectural surface + upstream findings), downstream (remediation + TIER 3 convergence), peers (sibling fortress artifacts), enforcers (STRIDE + PASTA + OWASP Threat Modeling + MITRE ATT&CK).

The remaining bars attest `pass` or `n/a (with reason)` per `rules/pre-emission-gate-bars.md` §1; M9 is **required** here (the Trust-Boundary Map above), M12 layout binds the canonical `_inputs/` artifact, and M11/M13/M15 are single-sprint / no-code / remediation-deferred.

**Iterate on failure.** One bar failure blocks promotion. Revise and re-run per `rules/pre-emission-gate-bars.md` §3, which names the owning revision rule for each bar and caps the loop at three rounds before BLOCKED, then emit the attestation block.

---

## Critical Rules

- **NEVER author remediation** — the surface is diagnostic; remediation routes through `/plan-execute` or operator-initiated edits.
- **NEVER fabricate findings** — every finding cites a trust-boundary edge, a STRIDE category, and (where applicable) a MITRE ATT&CK technique ID.
- **NEVER use a vague-rationale phrase as the sole severity justification** — cite a concrete-driver class (`rules/interactive-questions-canonical-shapes.md` §3.2.1).
- **NEVER attribute a residual-risk acceptance to an unratified authority** — surface as an inquiry instead.
- **NEVER modify source** — read-only against the architectural surface; only the findings artifact is written.
- **NEVER assume** — route every ambiguity (scope, severity, threat-actor classification, axis attestation) through the structured-inquiry channel.
- **Per-file destructive-op floor.** Destructive ops are out of scope; were one to surface (orphan-adapter retirement during a related cycle), it routes through the structured-inquiry channel per-file (`rules/interactive-questions.md` §6) with the verbatim `no-default: user decision required` marker.

---

## Decision Tree

> Moved to `references/decision-tree.md`. SHOULD read it when a branch, gate failure, or state transition is unclear.

---

## Output

- The findings artifact at `_inputs/threat-model-audit-findings.md` (executive summary + per-threat findings + findings index + severity distribution + trust-boundary map + validation-gate attestation + bindings).
- An optional inventory at `_inputs/threat-model-audit-inventory.md` (Phase 0).
- An optional per-threat drafts directory at `_inputs/threat-model-audit-per-threat/` (Phase 1 raw drafts before triage).

---

## Recommended Next Step

Invoke `/release-readiness` — the threat-model audit is the terminal command of the 11-command audit-fortress sequence, and `/release-readiness` is the pass/fail pre-release gate that consumes the fortress's closure artifacts.

## Installed Reference Paths

When this skill is installed by Apothem, resolve a repository-style reference against the installed directory for its first segment, unless a project-local file with the same relative path exists.

- `rules/<path>` is `<ROOT>/rules/<path>`
- `templates/<path>` is `<ROOT>/.apothem/support/templates/<path>`
- `schemas/<path>` is `<ROOT>/.apothem/support/schemas/<path>`
- `hooks/<path>` is `<ROOT>/.apothem/support/hooks/<path>`
- `conformity/<path>` is `<ROOT>/.apothem/support/conformity/<path>`
