---
name: "production-ready-prs"
description: "Every change the agent makes in a host project is delivered in production-ready form — tests + docs + CHANGELOG entry + conformant commit message + CI green in the same change-set. The seven visibility surfaces (what-is-this / how-to-install / is-it-alive / is-it-safe / how-to-contribute / can-I-trust / what-changed) are honored; gaps surface as findings rather than silently entrenched."
pathFilter: ""
alwaysApply: true
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Production-Ready Discipline on Host-Project Artifacts

## What this rule enforces

This rule binds **M15 — Production-Ready Discipline on Host-Project Artifacts**. Every change the agent makes in a host project **MUST** ship in **production-ready form** in one change-set: tests, docs, CHANGELOG entry, conformant commit message, CI green, supply-chain posture preserved, release-engineering invariants preserved. Where the host is not yet production-ready (missing LICENSE / CONTRIBUTING / CHANGELOG / CI / tests / examples), the agent **MUST NOT** silently entrench the gap — it surfaces the gap as an inquiry per §5 and proceeds under the user's choice.

## Pre-conditions

Applies to software-project work (a versioned project with a build / package / release surface) whenever a change affects a user-facing surface (public API, CLI, configuration, documentation, behavior, build / package / release); a non-software session — plain chat, cowork, research, or writing with no code, build, or release artifact — is outside its scope. Trivial-scope edits per the trivial-vs-non-trivial threshold are exempt from the full discipline; the commit-message-conformity and CI-green sub-clauses still bind.

## Required behavior

### 1. The Same-Change-Set Discipline

A code change **MUST** ship **all** of the following in **one** change-set:

| Element | Ships when |
|---|---|
| **Tests** | Code touched or new public surface introduced |
| **Documentation** | Any user-facing surface touched |
| **CHANGELOG entry** | User-facing change, per host format (Keep-a-Changelog `[Unreleased]` baseline) |
| **Conformant commit message** | Every commit, per the host's ratified convention |
| **CI green** | Change-set passes the host's full CI gate |
| **CODEOWNERS reviewers** | Host has CODEOWNERS and the change touches owned paths |
| **License header** | Host policy requires headers on new source files |
| **Migration guide** | The change is breaking |
| **Deprecation notice** | The change deprecates surface |
| **Example** | A new feature is introduced — runnable and CI-tested |

Deferred follow-ups ("I'll add tests / docs / CHANGELOG later") are forbidden: they never land, and production-readiness is violated at the merge boundary.

### 2. The Seven Visibility Surfaces (Companion Sub-Rule Anchor)

The seven visibility surfaces — what-is-this, how-to-install, is-it-alive, is-it-safe, how-to-contribute, can-I-trust, what-changed-and-when — are kept current on every change; gaps route to §5. (Companion Sub-Rule Anchor) See `rules/production-ready-prs-surfaces.md` §1.

### 3. Supply-Chain Posture Preservation (Companion Sub-Rule Anchor)

Every change preserves supply-chain posture: no unpinned dependency, no secret literal, no permission escalation, no unpinned GitHub Actions, no unsigned release artifact where signing is ratified. (Companion Sub-Rule Anchor) See `rules/production-ready-prs-surfaces.md` §2.

### 4. Release-Engineering Invariants (Companion Sub-Rule Anchor)

Versioning honored, tag-to-version consistency, tag signing where ratified. (Companion Sub-Rule Anchor) See `rules/production-ready-prs-surfaces.md` §3.

### 5. Gap-Surfacing Discipline

When the host is missing a production-ready surface (LICENSE, CONTRIBUTING, CHANGELOG, CI, tests, examples), the agent **MUST NOT** silently install it — it surfaces the gap as an inquiry per `rules/authority-inquiry.md` with options annotated per `rules/option-annotation.md`. Silent installation of long-lived ratifications is forbidden per the required-category inquiries at `rules/authority-inquiry-categories.md` §1.

### 6. Commit-Message Discipline (Companion Sub-Rule Anchor)

Every commit message honors the host's ratified convention discovered per `rules/host-discovery.md`, and the **human-only authorship** invariant binds every git surface — the agent never attributes itself or the underlying model / harness / vendor to any commit, trailer, branch, tag, or PR field. (Companion Sub-Rule Anchor) See `rules/production-ready-prs-surfaces.md` §4.

**Version-Control Safety.** Beyond message shape, the change-set's version-control mechanics bind: dedicated-branch default (never landing on `main` / a shared branch), atomic one-concern-per-commit granularity, no proactive rewrite of shared history, and preserved provenance. (Companion Sub-Rule Anchor) See `rules/production-ready-prs-surfaces.md` §4 for the full clause.

### 7. CI-Green Discipline (Companion Sub-Rule Anchor)

The change-set is CI-green before the change is considered complete: lint / format / type-check / test pass, coverage holds, security scans clean, build succeeds, docs build clean. CI failures are diagnosed and fixed in the same change-set, never deferred or marked flaky without root-cause. (Companion Sub-Rule Anchor) See `rules/production-ready-prs-surfaces.md` §5.

### 8. Modern Project Surface (Companion Sub-Rule Anchor)

Every host project — and apothem itself, by self-application — ships a modern project surface: paired multi-OS install scripts (`scripts/installer/install.sh` + `install.ps1`), an update / auto-update path (read-only by default), paired uninstall scripts (timestamped-backup default, unsafe-target refusal), a logo asset at `assets/logo.svg`, a modern centered README header, and an `## Install` section with one-shot / manual / verify sub-paths. (Companion Sub-Rule Anchor) See `rules/production-ready-prs-surfaces.md` §6 for the full §6.1–§6.7 specification.

## Disclosure surface

Outcomes are recorded in the disclosure ledger per `rules/disclosure-ledger.md` using the canonical `[Production-Ready — …]` / `[Visibility-Gap — …]` / `[Supply-Chain — …]` / `[Release-Engineering — …]` / `[Modern-Surface — …]` marker shapes. (Companion Sub-Rule Anchor) See `rules/production-ready-prs-surfaces.md` §1–§6.

## Failure tells

Same-change-set violations: "I'll add tests in a follow-up"; a breaking change with no migration guide; an `[Unreleased]` CHANGELOG lagging the codebase; a CI failure marked flaky without diagnosis; lint findings persisting into the merge. The visibility / supply-chain / release-engineering / modern-surface failure tells are enumerated alongside the moved sections. (Companion Sub-Rule Anchor) See `rules/production-ready-prs-surfaces.md` §1–§6.

## Bindings (§0.j five-direction)

- **Drives →** ● Every change the agent makes in a host project (the same-change-set discipline is the production-readiness floor). ● Every CHANGELOG entry, every commit message, every CI invocation across the host. ● The seven visibility surfaces' continuous maintenance across the host's lifecycle. ● The `production-ready-pr-grep` mechanical matcher at `conformity/production_ready_pr_grep.py` — operationalizes the §1 same-change-set discipline. ● The `secret-leak-grep` and `unpinned-action-grep` mechanical matchers at `conformity/` — operationalize the §3 supply-chain posture preservation.
- **Satisfies →** ● the fifteen-mandate registry row **M15 — Production-Ready**. ● the Pre-Emission Gate row 15 (M15 production-ready check).
- **Established by ↑** ● the fifteen-mandate registry (ratifies M15). ● the Pre-Emission Gate row 15. ● Keep-a-Changelog convention (the upstream changelog standard this rule projects). ● Conventional Commits specification (the upstream commit-message convention this rule honors per host-discovery).
- **Gated by ←** ● The trivial-vs-non-trivial threshold (trivial-scope edits run an abbreviated check covering commit-conformity and CI-green only). ● `CLAUDE.md` always-loaded preamble.
- **Cross-bound with ↔** ↔ `rules/production-ready-prs-surfaces.md` (path-filtered companion sub-rule carrying the §2 visibility surfaces, §3 supply-chain catalog, §4 release-engineering invariants, §6 commit-message discipline detail, §7 CI-green catalog, and §8 modern-project-surface specification). ↔ `rules/agile-sprints.md` (M11 — the DoD's `production-ready` criterion delegates here; the same-change-set discipline IS the DoD's production-ready clause materialized). ↔ `rules/disclosure-ledger.md` (M2 — production-ready outcomes recorded in the ledger). ↔ `rules/authority-inquiry.md` (M5 — visibility-gap inquiries route through the canonical channel; long-lived ratifications like LICENSE / CHANGELOG-format / CI-platform never silently installed). ↔ `rules/option-annotation.md` (M7 — every visibility-gap inquiry's option set carries the Recommended marker plus concrete-driver rationale). ↔ `rules/code-craft-python.md` + `rules/code-craft-shell.md` + `rules/code-craft-markdown.md` (M13 — code-craft sub-elements feed into the same-change-set tests / docs requirements). ↔ `rules/systemic-participation.md` (M14 — new components introduced via change-sets honor both the four-relations declaration and the production-ready discipline). ↔ `rules/host-discovery.md` (M1 — commit-message convention, action-pinning policy, release-signing requirement all discovered). ↔ `rules/refactoring-discipline.md` (§6 Version-Control Safety cites §2 as the refactor analogue — refactor-scoped workspace isolation under the same one-concern-per-unit granularity). ↔ `rules/sota-elevation.md` (production-ready is the floor; SOTA lifts the ceiling). ↔ `rules/i18n-discipline.md` (M15 — ≥80% review completion gate). ↔ `rules/freshness-facade.md` (M15 — the current-version-only release facade this rule's release-engineering discipline upholds). ↔ `rules/living-docs.md` (M15 — the production-ready same-change-set discipline this documentation analogue projects onto the docs surface). ↔ `rules/agile-sprints-elements.md` (M15 — DoD's `production-ready` criterion). ↔ `rules/i18n-discipline-locale-cohorts.md` (M15 — full authored-page-set coverage per cohort locale gates production-ready). ↔ `rules/pre-emission-gate.md` (↔ reciprocal of the peer's Cross-bound citation). ↔ `rules/pre-emission-gate-bars.md` (this rule is among the M-rules named in the gate's "Failure → action" column; the bar-level catalog cross-binds each).
