---
name: "option-annotation"
description: "Every multi-option choice carries a Recommended marker plus principle-linked rationale — silent picks and un-annotated option lists are forbidden in authoritative territory. The structured-inquiry subset delegates to the canonical structured inquiry schema; this rule extends the discipline to prose-and-document option sets."
pathFilter: ""
alwaysApply: true
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Option Annotation Discipline

## What this rule enforces

Binds **M7 — Option Annotation Discipline**. Whenever the agent surfaces an option set in any host-project artifact — prose response, ADR, README, PR description, design document, runbook step, code comment, commit-message body, RFC — every option MUST be enumerated, the agent's recommended option(s) MUST carry the canonical `**Recommended**` label, and the rationale MUST be specific and principle-linked. Silent picks and un-annotated option sets are both forbidden in authoritative territory.

The structured-inquiry subset (invocation schema, three-segment option body, closed recommendation taxonomy, harness fallback, per-file destructive-op confirmation, default-pointer convention) is canonicalized at `rules/interactive-questions.md` §2–§7. This rule extends the same discipline to the prose-and-document option sets that channel does not cover.

## Pre-conditions

Applies to every option set surfaced in a host-project artifact of meaningful scope per the trivial-vs-non-trivial threshold. The canonical annotation collapses to a single-line confirmation only when the option set is binary AND the work is trivial-scope AND the user has already implied the answer. Option sets of three or more entries always carry the canonical annotation.

## Required behavior

### Channel routing

Every option-set surface routes through one of two canonical channels:

- **structured-inquiry channel.** When the option set is a decision the user must resolve, the channel is structured inquiry per `rules/interactive-questions.md` §1; the three-segment annotation, recommendation taxonomy, label-postfix bidirectional bind, and destructive-op default floor are owned there.
- **prose-and-document channel.** When the option set surfaces inside an emitted artifact (prose response, ADR, README, PR description, design document, runbook), the annotation is the inline `**Recommended**` marker on the recommended option's heading — canonical example `Option B — <name> — **Recommended**`, followed by a `Rationale:` line citing a concrete driver.

### Companion Sub-Rule Anchor

The full prose-and-document specification — Option A / B / C example block + at-most-one-recommended cardinality + zero-recommended fallback (§1); concrete-driver classes + dimension-9 scholarly bar + vague-rationale forbid list (§2); cross-channel consistency invariant (§3); two-option floor + four-option ceiling + hierarchical split (§4); failure-tells enumeration (§5) — lives at the path-filtered companion [`rules/option-annotation-form.md`](./option-annotation-form.md), demand-loaded on prose-and-document artifact touches.

## Disclosure surface

The annotated option set IS the disclosure surface. When apothem falls back to the recommended option (the user declined to pick, or the option set was an optional inquiry per `rules/authority-inquiry.md`), the fallback is recorded in the disclosure ledger per `rules/disclosure-ledger.md` as `[Inquiry — id: <id>; outcome: fallback-to-recommended]`.

## Bindings (§0.j five-direction)

- **Drives →** Every option set in every emitted host-project artifact (prose, document, commit body, PR description). The `**Recommended**` marker presence at every multi-option choice surfaced inline. The mechanical option-annotation grep at `conformity/option_annotation_grep.py` (the prose-and-document scope of the matcher; the structured-inquiry scope routes through `rules/interactive-questions-sweep-matchers.md` H4–H7).
- **Satisfies →** the fifteen-mandate registry row **M7 — Option Annotation**.
- **Established by ↑** the fifteen-mandate registry (ratifies M7). `rules/interactive-questions.md` (the canonical-channel rule this rule extends; the structured-inquiry subset is canonicalized there, not duplicated here).
- **Gated by ←** `CLAUDE.md` always-loaded preamble. The §8.1 trivial-vs-non-trivial threshold (binary collapsed-confirmation choices on trivial-scope work skip the canonical annotation; option sets of three or more entries always carry it).
- **Cross-bound with ↔** `rules/option-annotation-form.md` (path-filtered companion sub-rule carrying the prose-and-document form, rationale specificity, cross-channel consistency, cardinality bounds, and failure tells). `rules/interactive-questions.md` (the structured-inquiry subset is canonicalized there; this rule extends to prose-and-document option sets without duplicating the schema). `rules/interactive-questions-sweep-matchers.md` (the H4–H7 annotation-compliance heuristics enforce this rule's prose-and-document scope at the pre-emission gate). `rules/disclosure-ledger.md` (M2 — fallback-to-recommended is recorded in the ledger). `rules/ten-dimension-check.md` (M3 — rationale specificity meets dimension 9 scholarly / technical referencing). `rules/authority-inquiry.md` (M5 — optional inquiries fall back to the recommended option per the carved-out catalog). `rules/operational-mandates.md` §CM-2 Zero Assumptions (M7 is the prose-and-document outward-projection form of CM-2's structured-inquiry discipline). `rules/sota-elevation.md` (every recommended-option rationale cites a concrete-exemplar concrete-driver class 6). `rules/recommend-next-step.md` (M7 — multi-action Next Steps blocks carry the Recommended marker plus concrete-driver rationale). `rules/i18n-discipline.md` (M7 — amendment inquiries carry Recommended + driver). `rules/determinism.md` (option-set annotations are rendered deterministically — same inputs yield the same recommended marker and rationale). ↔ `rules/agent-capability-discipline-matrix.md` (the §1B `(Recommended)`-rendering discipline whose per-harness runtime-enforcement wiring this companion catalogs). ↔ `rules/authority-inquiry-categories.md` (M7 — every §1 inquiry's option set carries the recommended marker). ↔ `rules/code-craft-conventions.md` (M7 — recommended-option annotation on inquired conventions). ↔ `rules/host-discovery.md` (M7 — every multi-option inquiry carries the recommended marker). ↔ `rules/i18n-discipline-locale-cohorts.md` (M7 — cohort options carry concrete-driver rationale per §3.2.1). ↔ `rules/pre-emission-gate.md` (↔ reciprocal of the peer's Cross-bound citation). ↔ `rules/pre-emission-gate-bars.md` (this rule is among the M-rules named in the gate's "Failure → action" column; the bar-level catalog cross-binds each). ↔ `rules/production-ready-prs.md` (M7 — every visibility-gap inquiry's option set carries the Recommended marker plus concrete-driver rationale). ↔ `rules/production-ready-prs-surfaces.md` (M7 — every visibility-gap inquiry's option set carries the Recommended marker plus concrete-driver rationale). ↔ `rules/visual-leverage.md` (M7 — every notation choice carries the Recommended marker plus concrete-driver rationale).
