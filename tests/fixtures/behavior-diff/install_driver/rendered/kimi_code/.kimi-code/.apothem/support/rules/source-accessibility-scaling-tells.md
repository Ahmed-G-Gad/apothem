---
name: "source-accessibility-scaling-tells"
description: "Path-filtered companion to source-accessibility carrying the four-level seriousness-scaling table and the failure-tells enumeration for source-trust-outranks-reachability selection, declared at the parent rule's §Seriousness-Scaling and §Failure-tells anchors; demand-loaded on documentation, site, and configuration-manifest surfaces where a claim's source is selected and cited."
pathFilter: "**/*.md, **/*.mdx, **/docs/**, **/site/**, **/*.toml, **/*.cfg, **/package.json"
alwaysApply: false
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Source Accessibility — Seriousness Scaling & Failure Tells (Companion Sub-Rule)

## Purpose

Carry the per-level source-discipline scaling and the failure-tells enumeration that `rules/source-accessibility.md` §Seriousness-Scaling and §Failure-tells anchors declare. The parent rule keeps the three standing obligations — trust outranks accessibility, escalate to reach the trusted source, record the source-trust decision; this companion carries the level-by-level enforcement table and the diagnostic tells of the ranking broken, so the always-on parent stays lean while the situational detail loads on the surfaces where a claim's source is actually selected and cited. Path-filtered: it demand-loads on documentation, site, and configuration-manifest touches — where a version pin, an API-contract reading, a convention adoption, or a public-surface claim rests on a chosen source.

## Seriousness Scaling (Parent §Seriousness-Scaling Detail)

| Level | Source discipline |
| ----- | ----------------- |
| EXPLORING | Prefer the trusted source; substitution disclosure optional. |
| PERSONAL_USE | Reach the trusted source via browser; disclose substitutions. |
| SHARED | Full escalation (browser then operator interview) before any substitution; every source-trust decision recorded. |
| PUBLIC_LAUNCH | No lower-trust substitute on a public-surface claim without recorded exhaustion of the escalation and an explicit operator-confirmed fallback. |

## Failure tells (Parent §Failure-tells Detail)

A free low-trust page cited where the vendor's gated doc is the real source of record; "it was not accessible" offered as justification with no browser attempt and no operator interview logged; a version pin or a security claim resting on a forum post; a substituted source used with no ledger record of the trust downgrade.

## Enforcement

Path-filtered (the glob patterns in this rule's `pathFilter` field — Markdown / MDX / docs / site / TOML / cfg / package.json), always-on at every seriousness level when in scope. Demand-loaded companion to `rules/source-accessibility.md` §Seriousness-Scaling / §Failure-tells. The parent rule carries the §1 trust-outranks-accessibility obligation, the §2 escalation ladder, and the §3 record-the-decision obligation; this companion carries the four-level scaling table and the failure-tells enumeration.

## Bindings (§0.j five-direction)

- **Drives →** ● The per-level enforcement calibration every source-selection decision applies (advisory at EXPLORING through blocking at PUBLIC_LAUNCH). ● The self-check and reviewer read of a landed claim for the low-trust-page, no-browser-attempt, forum-sourced-pin, and unrecorded-downgrade tells.
- **Satisfies →** ● the rules registry row "Source Accessibility Scaling & Tells". ● `rules/source-accessibility.md` §Seriousness-Scaling / §Failure-tells anchors (the parent rule's pointers to this companion's table and enumeration).
- **Established by ↑** ● `rules/source-accessibility.md` §1 / §2 / §3 (the three obligations this companion scales and diagnoses). ● The operator's standing-mandate set (the inaccessible-source mandate the parent binds).
- **Gated by ←** ● The path-filter (the glob patterns) — this rule demand-loads only on documentation / site / configuration-manifest touches where a source is selected and cited. ● `rules/source-accessibility.md` always-on baseline (the parent's three obligations must be live for the scaling and tells to apply coherently).
- **Cross-bound with ↔** ↔ `rules/source-accessibility.md` (parent rule; §1 / §2 / §3 / §Seriousness-Scaling / §Failure-tells anchors bind this companion). ↔ `rules/authoritative-referencing.md` (the trust-outranks-accessibility ranking decides which source the referencing mandate cites — the scaling calibrates how strictly). ↔ `rules/disclosure-ledger.md` (M2 — the unrecorded-trust-downgrade tell is a ledger omission). ↔ `rules/authority-inquiry.md` (M5 — the operator-interview escalation step whose absence the no-interview-logged tell betrays).
