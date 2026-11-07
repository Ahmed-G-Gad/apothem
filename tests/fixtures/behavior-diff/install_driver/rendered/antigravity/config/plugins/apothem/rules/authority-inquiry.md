---
trigger: always_on
description: "Inquire, do not invent — names, emails, handles, hostnames, organizations, scope, security, naming, infrastructure, and version pins are discovered or asked, never fabricated. Routes through the canonical structured-inquiry channel."
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Authoritative Inquiry — Inquire, Do Not Invent

## What this rule enforces

This rule binds **M5 — Authority Principle** (inquiry half; the discovery half lives at `rules/host-discovery.md`). The ecosystem MUST NOT fabricate personal, authoritative, or otherwise user-bound data. Names, emails, handles, hostnames, organizations, tenants, endpoints, credentials, scope direction, host-unratified naming choices, retention policies, version pins on host-mutable surfaces, and undeclared infrastructure decisions — none is invented. Each is either (i) **discovered** from a ratified host source of truth with provenance recorded per `rules/host-discovery.md`, or (ii) **inquired** from the user via the typed inquiry surface at `rules/interactive-questions.md`. A plausible-looking guess is never an acceptable substitute for either path.

## Pre-conditions

The rule applies whenever any host-project artifact about to be emitted depends on data in one of the seven inquiry categories below. Required-category inquiries (Identity, Scope direction, Security, Naming-of-public-surfaces) MUST block emission until answered; optional-category inquiries fall back to the recommended option per `rules/option-annotation.md` and record the fallback as a finding.

## Required behavior

### The Seven Inquiry Categories (Companion Sub-Rule Anchor)

The seven categories are: **Identity**, **Scope direction**, **Preference**, **Security**, **Naming**, **Infrastructure**, **Version pins**. Required-category inquiries (Identity, Scope direction, Security, Naming-of-public-surfaces) block emission via `<USER-CONFIRM:id=<id>>` placeholders rejected at pre-emission gate row 5; optional-category inquiries fall back to the **Recommended** option per `rules/option-annotation.md` and record the fallback as a finding. Full per-category "Forbidden to invent" / "Inquire because" columns and the required-vs-optional explanatory paragraph live at `rules/authority-inquiry-categories.md` §1 (Companion Sub-Rule Anchor).

### Inquiry surface — canonical channel

Every inquiry MUST route through the canonical structured-inquiry schema at `rules/interactive-questions.md` §2 Structured-Inquiry Shape. The structured-inquiry subset (the `questions` array, the option-set shape, the three-segment annotation, the recommendation taxonomy, the per-file destructive-op confirmation) is owned there; this rule carries the **outward-projection form** — the seven-category catalog naming *what* must be inquired, *when*, and *which* categories are required versus optional.

Where the host runtime exposes no structured inquiry, the structured prose fallback at `rules/interactive-questions.md` §5 replaces the tool invocation. Every fallback use MUST be logged in the change ledger per `rules/disclosure-ledger.md` so the degradation is never silent.

### Carved-Out Auto-Decisions (Companion Sub-Rule Anchor)

To prevent inquiry fatigue, a closed catalog of carve-out classes (pure validity, pure rigor, universally-safe security, pure formatting normalization, internal reference repair) is decided **without inquiry** — disclosed in the change ledger as `[Default — applied: <decision>; class: <carve-out>]`. Anything outside the carve-out goes through the inquiry surface. The full bulleted carve-out catalog lives at `rules/authority-inquiry-categories.md` §2 (Companion Sub-Rule Anchor).

## Disclosure surface

Inquiry outcomes are recorded in the disclosure ledger per `rules/disclosure-ledger.md`:

- `[Inquiry — id: <inquiry-id>; category: <category>; outcome: <user-choice|fallback-to-recommended>]` for every inquired-and-resolved choice.
- `[Default — applied: <auto-decision>; class: <carve-out class>]` for every carve-out auto-decision.
- `<USER-CONFIRM:id=<id>>` placeholders for unresolved required inquiries (these block emission per the pre-emission gate row 5 at `rules/pre-emission-gate.md`; the mechanical matcher at `conformity/user_confirm_grep.py` enforces the placeholder absence at hook level).

## Failure tells (Companion Sub-Rule Anchor)

The full failure-tells enumeration — invented identity / endpoint / handle data, unverified `mailto:` fields, guessed CODEOWNERS handles, host-mutable version pins without ratification, unfilled `<USER-CONFIRM:…>` placeholders, silently-resolved required-category decisions — lives at `rules/authority-inquiry-categories.md` §3 (Companion Sub-Rule Anchor).

## Bindings (§0.j five-direction)

- **Drives →** Every authoritative-data emission across every ecosystem surface. The pre-flight inquiry set every `commands/*.md` Step 1 emits per `rules/authority-inquiry.md`. The inquiry surface every `agents/*.md` return format carries. The mechanical `<USER-CONFIRM:…>`-placeholder grep at `conformity/user_confirm_grep.py`.
- **Satisfies →** the fifteen-mandate registry row **M5 — Authority Principle**. `rules/authority-inquiry.md` — Required Categories (the seven-row catalog this rule canonicalizes). `rules/authority-inquiry.md` Carved-Out Auto-Decisions (the carve-out catalog this rule reproduces).
- **Established by ↑** the fifteen-mandate registry (ratifies M5). `rules/authority-inquiry.md` (the seven-category catalog this rule reproduces with operational depth). `rules/authority-inquiry.md` Carved-Out Auto-Decisions.
- **Gated by ←** The §8.1 trivial-vs-non-trivial threshold (trivial work runs the abbreviated check covering only the placeholder-presence sweep). `CLAUDE.md` always-loaded preamble.
- **Cross-bound with ↔** `rules/authority-inquiry-categories.md` (path-filtered companion sub-rule carrying the §1 seven-category catalog, §2 carve-out auto-decisions, and §3 failure-tells enumeration). `rules/interactive-questions.md` (the canonical structured-inquiry invocation schema, three-segment annotation, recommendation taxonomy, harness fallback, and per-file destructive-op confirmation are owned there; this rule carries the seven-category outward-projection catalog and delegates the structured-inquiry subset). `rules/host-discovery.md` (M5 discovery half — the discovery and inquiry halves form a complete coverage of authority data). `rules/disclosure-ledger.md` (M2 — every inquiry outcome and carve-out default is recorded in the ledger). `rules/option-annotation.md` (M7 — every inquiry's option set carries the recommended marker). `rules/operational-mandates.md` §CM-2 Zero Assumptions (M5 is the outward-projection form of CM-2's structured-inquiry discipline). `rules/pre-emission-gate.md` (M4 — bar 5 of the gate enforces this rule's `<USER-CONFIRM:…>`-placeholder absence and unresolved-inquiry array population). `rules/i18n-discipline.md` (M5 — cohort amendments routed via the structured-inquiry channel). `rules/source-accessibility.md` (M5 — the inaccessible-source escalation reaches a trusted source through the operator-interview channel owned here). ↔ `rules/authoritative-referencing-quotation.md` (M5 — a reproduction whose scope is in genuine doubt surfaces as an open question rather than a self-issued legal opinion). ↔ `rules/code-craft-conventions.md` (M5 — silence-routed choices). ↔ `rules/definitiveness.md` (M5 — removed-prescription cases route to the inquiry surface). ↔ `rules/definitiveness-virtues.md` (M5 — removed-prescription cases route to the inquiry surface). ↔ `rules/disclosure-ledger-markers.md` (M5 — `[Inquiry — …]` and `[Default — …]` markers). ↔ `rules/expertise-posture.md` (M5 — expert certainty never overrides authoritative-data inquiry). ↔ `rules/expertise-posture-elements.md` (M5 — expert certainty never overrides authoritative-data inquiry). ↔ `rules/host-discovery-manifests.md` (M5 inquiry half — when discovery encounters silence, route through the inquiry surface). ↔ `rules/i18n-discipline-locale-cohorts.md` (M5 — cohort amendments route through the structured-inquiry channel). ↔ `rules/option-annotation-form.md` (M5 — zero-recommended option sets route through the inquiry surface). ↔ `rules/pre-emission-gate-bars.md` (this rule is among the M-rules named in the gate's "Failure → action" column; the bar-level catalog cross-binds each). ↔ `rules/production-ready-prs.md` (M5 — visibility-gap inquiries route through the canonical channel; long-lived ratifications like LICENSE / CHANGELOG-format / CI-platform never silently installed). ↔ `rules/production-ready-prs-surfaces.md` (M5 — visibility-gap inquiries route through the canonical channel). ↔ `rules/source-accessibility-scaling-tells.md` (M5 — the operator-interview escalation step whose absence the no-interview-logged tell betrays). ↔ `rules/visual-leverage.md` (M5 — silent host on notation routes through inquiry surface).
