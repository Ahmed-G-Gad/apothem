---
name: "host-discovery"
description: "Discover host-project conventions before emitting any artifact — language, formatter, linter, layout, naming, idioms, sibling-file patterns. Honor discoveries; surface silence as an authoritative inquiry per the canonical channel."
pathFilter: "**/pyproject.toml, **/setup.cfg, **/package.json, **/Cargo.toml, **/go.mod, **/.editorconfig, **/.github/workflows/**, **/CONTRIBUTING.md, **/CLAUDE.md, **/rules/**"
alwaysApply: false
paths:
  - "**/pyproject.toml"
  - "**/setup.cfg"
  - "**/package.json"
  - "**/Cargo.toml"
  - "**/go.mod"
  - "**/.editorconfig"
  - "**/.github/workflows/**"
  - "**/CONTRIBUTING.md"
  - "**/CLAUDE.md"
  - "**/rules/**"
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
- ``[Default — applied: <auto-decision>; class: <carve-out class per `authority-inquiry.md`>]`` for the carve-out class (pure validity, pure rigor, universally-safe security, pure formatting normalization, internal reference repair).

## Derived Project Context Block

(Companion Sub-Rule Anchor) The two blocks whole-repo target-ingest commands derive by this rule's M1 walk — **Derived Project Context** (languages and versions, frameworks, package / dependency manager, build / run / test commands, runtime and platform, architecture, CI surface, priority pain points) and **Derived Constraints** (do-not-touch surfaces, public interfaces, must-preserve behaviors, backward-compatibility, already-configured coding standards, license) — are defined once at `rules/host-discovery-manifests.md` §4, the shared surface `commands/elevate.md` and `commands/fortress.md` cite for their target-ingest derived-block emission; each command keeps its own command-specific output path, and both blocks are surfaced for operator correction without blocking the run (silence on a derived item routes through `rules/authority-inquiry.md`, never a silent default).

## Failure tells

(Companion Sub-Rule Anchor) See `rules/host-discovery-manifests.md` §3 for the failure-tells enumeration (Python / Markdown / pytest / shell / CI / commit / package.json / MCP / file-class drift).
