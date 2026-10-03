---
trigger: always_on
description: "Discover host-project conventions before emitting any artifact — language, formatter, linter, layout, naming, idioms, sibling-file patterns. Honor discoveries; surface silence as an authoritative inquiry per the canonical channel."
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Host-Project Agnosticism & Convention Discovery

## What this rule enforces

This rule binds **M1 — Host-Project Agnosticism & Convention Discovery** (and the discovery half of **M5 — Authority Principle**). Whatever the ecosystem produces in a host project is shaped by what that project already is. Every convention — stack, language, framework, toolchain, formatter, linter, test framework, docs generator, CI platform, branch strategy, commit convention, layout, naming, dependency-pinning policy, release-signing mechanism, versioning scheme, line endings, indentation, quote style, license, copyright header — is **discovered** from the host's ratified source-of-truth (manifests, lock files, config files, sibling files of comparable kind, convention documents) and **honored**. Where the host is silent on a convention the agent must adopt to act, the silence is surfaced as an authoritative inquiry per `rules/authority-inquiry.md` with the recommended option annotated per `rules/option-annotation.md` — never resolved by a silent internal default.

## Pre-conditions

Applies whenever any host-project artifact is authored, modified, retrofitted, extended, or removed. Trivial work (single-file edit ≤ 5 lines AND no public-API change AND no behavioral shift, per the trivial-vs-non-trivial threshold) is exempt from the discovery surface but still honors idioms visible at the touch site. Ecosystem-internal authoring inside the apothem source repo is governed by `CLAUDE.md` user-scope conventions, not this outward-discovery rule.

## Required behavior

### 1. Discover before authoring

Before any artifact is written or edited, the agent MUST walk the host's ratified source-of-truth files for the artifact's class. (Companion Sub-Rule Anchor) See `rules/host-discovery-manifests.md` §1 for the per-language manifest catalog (Python / TypeScript-JavaScript / Rust / Go / Shell / CI / Docs).

### 2. Honor discovered conventions

The artifact MUST be indistinguishable from one a long-tenured contributor of the host project would have written. When editing, the agent MUST preserve the surrounding idioms even where it would idiomatically choose otherwise. When creating a file class the host lacks, the agent MUST surface the choice as an inquiry per `rules/authority-inquiry.md` — never silently install an agent-internal default. The host's own `lint` / `format` / `test` / `type-check` commands MUST pass the artifact unmodified.

### 3. Surface silence

Where the host is silent on a convention the agent must adopt to proceed, the agent MUST route the choice through the canonical inquiry surface at `rules/authority-inquiry.md` with the recommended option annotated per `rules/option-annotation.md`. Required inquiries (identity, scope direction, security, naming-of-public-surfaces) block emission until answered. Optional inquiries fall back to the recommended option and record the fallback as a ledger finding.

### 4. Discovery record

Every discovery and every inquiry-driven choice MUST be recorded with provenance in the artifact's working trace. (Companion Sub-Rule Anchor) See `rules/host-discovery-manifests.md` §2 for the discovery-record provenance schema.

## Disclosure surface

The discovery record and any inquiry-driven choices are disclosed per `rules/disclosure-ledger.md`:

- `[Discovery — source: <path>; value: <discovered>; honored]` for every discovered convention applied.
- `[Inquiry — id: <inquiry-id>; outcome: <user-choice|fallback-to-recommended>]` for every inquiry-resolved choice.
- `[Default — applied: <auto-decision>; class: <carve-out class per `authority-inquiry.md`>]` for the carve-out class (pure validity, pure rigor, universally-safe security, pure formatting normalization, internal reference repair).

## Derived Project Context Block

(Companion Sub-Rule Anchor) The two blocks whole-repo target-ingest commands derive by this rule's M1 walk — **Derived Project Context** (languages and versions, frameworks, package / dependency manager, build / run / test commands, runtime and platform, architecture, CI surface, priority pain points) and **Derived Constraints** (do-not-touch surfaces, public interfaces, must-preserve behaviors, backward-compatibility, already-configured coding standards, license) — are defined once at `rules/host-discovery-manifests.md` §4, the shared surface `commands/elevate.md` and `commands/fortress.md` cite for their target-ingest derived-block emission; each command keeps its own command-specific output path, and both blocks are surfaced for operator correction without blocking the run (silence on a derived item routes through `rules/authority-inquiry.md`, never a silent default).

## Failure tells

(Companion Sub-Rule Anchor) See `rules/host-discovery-manifests.md` §3 for the failure-tells enumeration (Python / Markdown / pytest / shell / CI / commit / package.json / MCP / file-class drift).

## Bindings (§0.j five-direction)

- **Drives →** Every host-project artifact emission across every ecosystem surface (commands, skills, agents, hooks). The discovery sub-phase that opens every `commands/*.md` artifact-emitting workflow per the fifteen-mandate registry row M1. The discover-don't-assume preamble of every `skills/*/SKILL.md` artifact-emitting procedure. The pre-write idiom-divergence checks at `conformity/` mechanical greps. The §Derived Project Context Block shared surface `commands/elevate.md` and `commands/fortress.md` cite for their target-ingest derived-block emission.
- **Satisfies →** the fifteen-mandate registry row **M1 — Host-Project Agnosticism**. `rules/authority-inquiry.md` — the discovery half closes the data side that the inquiry surface complements.
- **Established by ↑** the fifteen-mandate registry (ratifies M1). The host's ratified source-of-truth files (the discovery's primary surface).
- **Gated by ←** `CLAUDE.md` always-loaded preamble. The §8.1 trivial-vs-non-trivial threshold (trivial work is exempt from the discovery surface).
- **Cross-bound with ↔** `rules/host-discovery-manifests.md` (path-filtered companion sub-rule carrying the §1 per-language manifest catalog, §2 discovery-record schema, Failure-tells enumeration, and §4 Derived Project Context Block definition). `rules/authority-inquiry.md` (M5 inquiry half — when discovery encounters silence, route through the inquiry surface). `rules/disclosure-ledger.md` (M2 — every discovery and every inquiry outcome is recorded in the ledger). `rules/option-annotation.md` (M7 — every multi-option inquiry carries the recommended marker). `rules/operational-mandates.md` §CM-2 Zero Assumptions (host-discovery is the outward-projection form of CM-2's inward-facing inquiry discipline). `rules/dynamism.md` (sibling discipline; dynamic source-of-truth surfaces are M1-discovered before rendering is wired). `rules/harness-adapter-shape.md` (sibling discipline; per-harness discovery is the M1 walk for adapter conventions). `rules/i18n-discipline.md` (sibling discipline; locale cohort discovered, not invented). ↔ `rules/agent-capability-discipline-matrix.md` (M1 — per-cell discovery walks the vendor surface per the discovery-record provenance schema). ↔ `rules/authority-inquiry-categories.md` (M5 discovery half — the discovery and inquiry halves form a complete coverage of authority data; §1 categories are the inquiry-half projection of M1's discovery walk). ↔ `rules/canonical-layout.md` (M1 — canonical layout's exact form is host-discovered). ↔ `rules/canonical-layout-reporting-tiers.md` (M1 — §1.1 / §1.2 / §2 honor host-discovered conventions for filenames and prefix schemes). ↔ `rules/code-craft-conventions.md` (M1 — per-language discovery is the M1 walk for code-craft conventions). ↔ `rules/code-craft-shell.md` (M1 — shellcheck and ScriptAnalyzer config discovery walks). ↔ `rules/disclosure-ledger-markers.md` (M1 — `[Discovery — …]` markers). ↔ `rules/expertise-posture.md` (M1 — host idioms are honored before expertise imports a foreign one). ↔ `rules/expertise-posture-elements.md` (M1 — host idioms are honored before sub-element 7 imports a foreign one). ↔ `rules/harness-adapter-shape-schemas.md` (M1 — per-harness discovery walks). ↔ `rules/i18n-discipline-locale-cohorts.md` (M1 — cohort discovery walks the host's existing translated corpus). ↔ `rules/pre-emission-gate.md` (↔ reciprocal of the peer's Cross-bound citation). ↔ `rules/pre-emission-gate-bars.md` (this rule is among the M-rules named in the gate's "Failure → action" column; the bar-level catalog cross-binds each). ↔ `rules/production-ready-prs.md` (M1 — commit-message convention, action-pinning policy, release-signing requirement all discovered). ↔ `rules/production-ready-prs-surfaces.md` (M1 — commit-message convention, action-pinning policy, release-signing requirement all discovered). ↔ `rules/systemic-participation.md` (M1 — sibling-convergence walks the host-discovery surface). ↔ `rules/systemic-participation-relations.md` (M1 — sibling-convergence walks the host-discovery surface). ↔ `rules/visual-leverage.md` (M1 — host's existing notation overrides Mermaid default).
