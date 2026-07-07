---
name: "interactive-questions"
description: "Canonical discipline for soliciting user input — the harness-neutral structured-inquiry channel is the sanctioned abstraction; every invocation carries a structured option annotation; destructive operations and ambiguity resolution route through this rule; a prose fallback shape covers harnesses that lack a native tool."
pathFilter: ""
alwaysApply: true
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Interactive Questions

## Purpose

Govern every act of soliciting user input. One abstraction, one schema, one fallback.

## Obligations

### 1. Canonical Channel

The structured-inquiry channel is the **sole** sanctioned abstraction. Every surface **MUST** route through its native tool or documented fallback; free-form conversational prompts as primary input are retired. Three narrow exceptions: raw-notes preservation (quote, never reissue); fallback-prose per §5; harness-emitted dialogs outside this rule's scope.

### 2. Structured-Inquiry Shape (Companion Sub-Rule Anchor)

Every invocation carries `question` (one sentence ending `?`), `header` (≤12 chars), `options` (2–4, auto-implicit `Other`), `multiSelect`. Each option carries `label` (1–5 words) and `description` (three-segment body per §3).

(Companion Sub-Rule Anchor) See `rules/interactive-questions-canonical-shapes.md` §1 for worked examples.

### 3. Three-Segment Option Annotation (Companion Sub-Rule Anchor)

Every `description` carries three fixed-order segments: **rationale:** (observable consequence) · **recommendation:** (taxonomy value per §4; driver why-clause when non-neutral) · **default-pointer:** (named default OR `no-default: user decision required`). The label ` (Recommended)` postfix bidirectionally binds the body value `recommended`: single-select carries at most one recommended option; `multiSelect: true` MAY mark several.

(Companion Sub-Rule Anchor) See `rules/interactive-questions-canonical-shapes.md` §2 for the full schema, label-postfix specification, and failure modes.

### 4. Recommendation Taxonomy (Companion Sub-Rule Anchor)

Closed taxonomy `{recommended, acceptable, discouraged, destructive-no-default}`. Non-neutral values **MUST** cite a concrete driver; vague phrases are forbidden as sole justification — downgrade to `acceptable`.

(Companion Sub-Rule Anchor) See `rules/interactive-questions-canonical-shapes.md` §3 for the driver taxonomy, forbid list, downgrade path, and extension protocol.

### 5. Harness Fallback (Companion Sub-Rule Anchor)

When the harness exposes neither direct nor deferred structured inquiry, the prose fallback fires: a prose prompt mirroring the schema, the conversation marker `[FALLBACK — structured-inquiry channel unavailable]`, and a ledger row in `ecosystem-remediation-ledger.md`. Outside this context, free-form prose as primary input is forbidden.

(Companion Sub-Rule Anchor) See `rules/interactive-questions-canonical-shapes.md` §4 for the activation predicate, prose-shape example, and ledger schema.

### 6. Per-File Destructive-Op Confirmation (Companion Sub-Rule Anchor)

Every destructive op (delete, rename, move, overwrite, revert-uncommitted) **MUST** route through the channel per file — never batched. Every option carries `default-pointer: no-default: user decision required`; `multiSelect: true` is non-compliant; ` (Recommended)` **MUST NOT** mark a destructive option.

(Companion Sub-Rule Anchor) See `rules/interactive-questions-canonical-shapes.md` §5 for the canonical option-sets (Delete / Rename / Move / Revert) and invariants.

### 7. Default-Pointer Convention (Companion Sub-Rule Anchor)

Two forms: **named-default** (`<label> — <rationale>`, identical across options) or **no-default** (the verbatim `no-default: user decision required`). Destructive ops universally use no-default per §6.

(Companion Sub-Rule Anchor) See `rules/interactive-questions-canonical-shapes.md` §6 for worked examples.

### 8. Pattern-Detection Heuristics (Companion Sub-Rule Anchor)

The interactive-channel gate sweeps for conversational-prompt patterns and annotation compliance. The H1–H7 matcher catalog lives at `rules/interactive-questions-sweep-matchers.md`; its §3 exempts this rule's §1, §5, §6, Anti-Patterns as definitional. HIGH findings block the airtightness composite. The runtime PreToolUse `AskUserQuestion` validator additionally checks `(Recommended)`-marker well-formedness on the LIVE tool payload at call time (advisory by default; the strict opt-in blocks), closing the previously documented-but-unenforced call-time gap; see `rules/interactive-questions-canonical-shapes.md` §2.1.

### 9. Authoring Discipline (Companion Sub-Rule Anchor)

Write the question first; derive options; annotate; review. (Companion Sub-Rule Anchor) See `rules/interactive-questions-detail.md` §Authoring Discipline for the full five-step procedure.

## Seriousness Scaling

| Level | Discipline |
| ----- | ---------- |
| EXPLORING | Channel active; annotation encouraged; driver advisory |
| PERSONAL_USE | Channel + annotation + driver + per-file destructive confirmation mandatory |
| SHARED | Full; sweep on every change; ledger tagging mandatory |
| PUBLIC_LAUNCH | Zero tolerance; heuristic hits block; sweep is a numbered airtightness gate |

## Anti-Patterns (Companion Sub-Rule Anchor)

Six anti-patterns: schema-bypassing raw prompts, destructive batching, driver-less recommendation, destructive named-default, `(Recommended)` signal violation, silent fallback. (Companion Sub-Rule Anchor) See `rules/interactive-questions-detail.md` §Anti-Patterns for full bodies.

## Enforcement

Always-on. Implements CM-2 extension. Detail-tier at `rules/interactive-questions-canonical-shapes.md`; matchers at `rules/interactive-questions-sweep-matchers.md`.

## Bindings (§0.j five-direction)

- **Drives →** ● Every structured-inquiry invocation across the ecosystem (every command, rule, skill, agent, hook surface that solicits user input routes through the canonical channel). ● The three-segment option-annotation schema (every option's `description` carries `rationale:`, `recommendation:`, `default-pointer:`). ● The per-file destructive-op confirmation floor (§6 — every delete / rename / move / overwrite / revert routes through the structured-inquiry channel per-file). ● The fallback prose shape (§5 — the sole permitted free-form-looking prompt outside the canonical channel). ◐ The `(Recommended)` label postfix bidirectional bind with body `recommendation: recommended`.
- **Satisfies →** ● CM-2 extension (the structured-inquiry surface CM-2 delegates to). ● the rules registry row "Interactive Questions". ● Option Annotation Discipline (the mandate this rule's annotation schema enforces).
- **Established by ↑** ● CM-2 (Zero Assumptions — this rule is the structured-inquiry extension). ● Option Annotation Discipline. ● Authority Hygiene (per-file destructive-op confirmation operationalizes the no-silent-substitution invariant).
- **Gated by ←** ● `CLAUDE.md` always-loaded preamble. ● `rules/operational-mandates.md` (CM-2 inline definition delegates the structured-inquiry surface here).
- **Cross-bound with ↔** ↔ `rules/interactive-questions-canonical-shapes.md` (companion sub-rule carrying §2–§7 worked examples, schema bodies, taxonomy details, canonical option-set templates). ↔ `rules/interactive-questions-sweep-matchers.md` (companion sub-rule carrying the §8 H1–H7 matcher catalog). ↔ `rules/operational-mandates.md` (CM-2 inline anchor delegates here). ↔ `commands/plan-execute.md` + `commands/plan-generate.md` + `commands/plan-spec.md` + `commands/plan-review.md` (every plan-pipeline command's structured-inquiry invocations). ↔ `scripts/dev/validate_ecosystem.py` (the `--check option-annotation` subcommand operationalizes the H4–H7 matchers). ↔ `rules/agent-capability-discipline.md` (§6 destructive-op canonical option sets govern agent-capability invocations). ↔ `rules/agnostic-posture.md` (preference selection routes through the end user under the host-agnostic posture rather than being silently picked). ↔ `rules/interactive-questions-detail.md` (companion sub-rule carrying the §9 authoring-discipline procedure and the anti-pattern catalog moved out of the always-on body). ↔ `rules/authority-inquiry.md` (the canonical structured-inquiry invocation schema, three-segment annotation, recommendation taxonomy, harness fallback, and per-file destructive-op confirmation are owned there; this rule carries the seven-category outward-projection catalog and delegates the structured-inquiry subset). ↔ `rules/authority-inquiry-categories.md` (the canonical-channel routing the parent rule delegates; every §1 inquiry routes through the structured inquiry schema). ↔ `rules/canonical-layout-reporting-tiers.md` (§6.4 destructive-op canonical option set governs §3's orphan-retirement path; §7.3 borderline-tier inquiry routes through the canonical channel). ↔ `rules/operational-mandates-expanded.md` (CM-2 structured-inquiry surface cited in the CM-2 directive). ↔ `rules/option-annotation.md` (the structured-inquiry subset is canonicalized there; this rule extends to prose-and-document option sets without duplicating the schema). ↔ `rules/surgical-manipulation.md` (§6 — destructive mutations route per-file through the canonical destructive-op floor).
