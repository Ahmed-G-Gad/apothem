---
name: "source-accessibility-scaling-tells"
description: "Path-filtered companion to source-accessibility carrying the four-level seriousness-scaling table and the failure-tells enumeration for source-trust-outranks-reachability selection, declared at the parent rule's §Seriousness-Scaling and §Failure-tells anchors; demand-loaded on documentation, site, and research-manuscript surfaces where a claim's source is selected and cited."
pathFilter: "**/docs/**, **/site/**, **/README.md, **/research/**, **/manuscript/**, **/paper/**, **/literature/**, **/*.bib, **/*.tex"
alwaysApply: false
paths:
  - "**/docs/**"
  - "**/site/**"
  - "**/README.md"
  - "**/research/**"
  - "**/manuscript/**"
  - "**/paper/**"
  - "**/literature/**"
  - "**/*.bib"
  - "**/*.tex"
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Source Accessibility — Seriousness Scaling & Failure Tells (Companion Sub-Rule)

## Purpose

Carry the per-level source-discipline scaling and the failure-tells enumeration that `rules/source-accessibility.md` §Seriousness-Scaling and §Failure-tells anchors declare. The parent rule keeps the three standing obligations — trust outranks accessibility, escalate to reach the trusted source, record the source-trust decision; this companion carries the level-by-level enforcement table and the diagnostic tells of the ranking broken, so the parent stays lean while the situational detail loads on the surfaces where a claim's source is actually selected and cited. Path-filtered: it demand-loads on documentation, site, and research-manuscript touches — where a version pin, an API-contract reading, a convention adoption, or a public-surface claim rests on a chosen source.

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

Path-filtered (the nine glob patterns in this rule's `pathFilter` field — docs / site / README / research / manuscript / paper / literature / bibliography and TeX files), always-on at every seriousness level when in scope. Demand-loaded companion to `rules/source-accessibility.md` §Seriousness-Scaling / §Failure-tells. The parent rule carries the §1 trust-outranks-accessibility obligation, the §2 escalation ladder, and the §3 record-the-decision obligation; this companion carries the four-level scaling table and the failure-tells enumeration.
