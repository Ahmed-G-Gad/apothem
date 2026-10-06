---
name: "disclosure-ledger-markers"
description: "Path-filtered companion rule carrying the full marker-class enumeration, ledger-completeness detail, rationale-specificity detail, and failure-tells body declared at the parent `disclosure-ledger.md` rule's anchor; demand-loaded on disclosure-bearing artifact touches."
pathFilter: "**/*.md, **/CLAUDE.md, **/rules/**, **/commands/**, **/skills/**, **/agents/**, **/docs/**, **/.github/**"
alwaysApply: false
paths:
  - "**/*.md"
  - "**/CLAUDE.md"
  - "**/rules/**"
  - "**/commands/**"
  - "**/skills/**"
  - "**/agents/**"
  - "**/docs/**"
  - "**/.github/**"
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Disclosure-Ledger Markers (Companion Sub-Rule)

## Purpose

Specify the marker-class enumeration, ledger-completeness detail, rationale-specificity detail, and failure-tells body that the parent rule `rules/disclosure-ledger.md` anchors. This companion is path-filtered: it loads when the assistant edits any artifact that may carry a disclosure ledger (Markdown, rule, command, skill, agent, doc, or CI surface), keeping the parent's always-on payload lean while preserving full marker fidelity at the demand-load surface. The parent rule remains the canonical home for the M2 standing directive, the marker-class one-line list, the §2 ledger-placement paragraph, and the parent-side bindings; this companion carries the full marker-class bodies and the failure-catalog.

## Obligations

### 1. Marker-Class Enumeration (Full Bodies)

Every disclosure ledger carries the following marker classes inline at the change's hand-off surface (commit message body, PR description, response prose, or the artifact's working-trace section):

- `[Amendment — rationale: <cited rationale per ten-dimension-check.md dimension 9>]` — a deliberate change to the literal request because the literal would have left a known defect (idiom drift, security gap, correctness bug, performance trap). The rationale cites a primary source (RFC, vendor documentation, host-project sibling-file precedent, scholarly reference).
- `[Extension — adjacent gap surfaced: <description>]` — a widening of the change's scope to address an adjacent gap revealed during execution. The extension is either folded into the change with explicit justification, or surfaced as a finding for the user's decision and deferred.
- `[Refinement — improvement: <named property>]` — a structural / aesthetic / craft improvement applied alongside the request, with the improved property named (clarity, correctness, performance, maintainability, testability, security, expressiveness).
- `[Deferral — out-of-scope: <description>; tracking: <where the deferral is tracked>]` — adjacent work intentionally left for a separate change, with the tracking location named (issue tracker entry, follow-up task, watch-item).
- `[Discovery — source: <path>; value: <discovered>; honored]` — every host-discovered convention applied per `rules/host-discovery.md`.
- `[Inquiry — id: <inquiry-id>; outcome: <user-choice|fallback-to-recommended>]` — every inquiry-resolved choice per `rules/authority-inquiry.md`.
- `[Default — applied: <auto-decision>; class: <carve-out class>]` — every auto-decision applied per the carve-out catalog at `rules/authority-inquiry.md` (pure validity, pure rigor, universally-safe security, pure formatting normalization, internal reference repair).

### 2. Ledger Completeness

Every amendment, extension, refinement, deferral, and default the change carries MUST be enumerated. Non-conformant: a change that touches files the user did not name without comment; a change that elides edge cases the user did not specify but a senior engineer would have addressed, with no surfacing of the elision; a "fix" that papers over a deeper bug rather than naming the deeper bug for the user's decision.

### 3. Rationale Specificity

Rationales cite **specific** evidence — never platitudinous (`"this is widely adopted"`), never opinion-only (`"this is better"`), never an appeal to consensus without a named source. Rationale specificity matches the citation form at `rules/ten-dimension-check.md` dimension 9 (scholarly / technical referencing) and the concrete-driver classes at `rules/interactive-questions-canonical-shapes.md` §3.2.1.

### 4. Operator Comprehension — The Ledger Is for Understanding, Not Bookkeeping

A disclosure exists so the operator can **understand** the change, not merely record that it happened. The marker is a comprehension surface, not a receipt: it answers "what changed, why, and what should the operator look at to verify it" — never "a change occurred; details omitted". The proportionality rule: the disclosure's specificity scales with the change's surface area and risk. A one-line ledger entry standing behind a large or non-obvious diff leaves the operator unable to evaluate what they are accepting — the gap between what was changed and what the operator can comprehend from the ledger is **comprehension debt**, and it compounds the way unreviewed loop-generated output compounds.

Closing comprehension debt is the disclosing party's obligation, not the operator's burden: a substantial change names its load-bearing decisions, the surfaces it touched, and the verification the operator can run to confirm it — enough that the operator forms an accurate mental model of the change from the ledger alone, without re-deriving it from the raw diff. A disclosure that records the *fact* of a change while leaving its *substance* opaque has recorded without disclosing.

### 5. Failure Tells

A diff that touches files the user did not name without comment. A response that elides edge cases the user did not specify but a senior engineer would have addressed, with no surfacing that the elision happened. A "fix" that papers over a deeper bug rather than naming the deeper bug. A commit message that says only "fix bug" with a 200-line diff. A PR that widens scope ("while I was here, I also …") with no `[Extension]` marker. A response that says "done" without listing what was done, what was amended, and what was deferred. An `[Amendment]` marker whose rationale is `"this is widely adopted"` without a named source. **Comprehension debt** — a large or non-obvious diff landed behind a one-line ledger entry the operator cannot evaluate without reconstructing the change from the raw diff themselves; the disclosure recorded that something happened without surfacing enough substance for the operator to understand what.

## Enforcement

Path-filtered (the eight glob patterns in this rule's `pathFilter` field), always-on at every seriousness level when in scope. Demand-loaded companion to `rules/disclosure-ledger.md`. The parent rule carries the M2 standing directive, the one-line marker-class list, the §2 ledger-placement paragraph, and the parent-side bindings; this companion carries the full marker-class bodies, the ledger-completeness detail, the rationale-specificity detail, and the failure-tells catalog.

## Bindings (§0.j five-direction)

- **Drives →** ● Every disclosure-ledger emission across every host-project artifact (the seven marker classes are the complete vocabulary). ● Every commit body, PR description, response prose, and phase rollup report's Disclosure Surface section. ● The completeness invariant at every change hand-off (§2 — every amendment / extension / refinement / deferral / default enumerated). ◐ The pre-emission gate's M2 row at `rules/pre-emission-gate.md`.
- **Satisfies →** ● the fifteen-mandate registry row **M2 — Editorial Discipline** (companion-tier). ● `rules/disclosure-ledger.md` parent-rule anchor (the parent's pointer to this companion's full marker-class bodies and failure catalog).
- **Established by ↑** ● `rules/disclosure-ledger.md` (parent-rule anchor). ● the fifteen-mandate registry (ratifies M2).
- **Gated by ←** ● The path-filter (the eight glob patterns) — this rule demand-loads only on disclosure-bearing artifact touches. ● `rules/disclosure-ledger.md` always-on baseline (parent rule must be live for the anchor to surface).
- **Cross-bound with ↔** ↔ `rules/disclosure-ledger.md` (parent rule; the anchor binds this companion). ↔ `rules/host-discovery.md` (M1 — `[Discovery — …]` markers). ↔ `rules/authority-inquiry.md` (M5 — `[Inquiry — …]` and `[Default — …]` markers). ↔ `rules/expertise-posture.md` (M6 — `[Amendment]` / `[Extension]` / `[Refinement]` markers driven by expertise). ↔ `rules/ten-dimension-check.md` (M3 — rationale citations meet dimension 9). ↔ `rules/pre-emission-gate.md` (M4 — `amendments-disclosed` array population).
