---
description: 'Effect of the always-on rule interactive-questions: the same prompt and graders with the
  rule''s runtime text appended to the system prompt (on in this case). Plugin eval runs load no rules,
  so the pair isolates the rule''s effect.'
tags: [rule-effect, 'rule:interactive-questions', 'arm:rule-on', r12-regression]
expected_outcome: The ambiguity (which database, where, which schema) is routed through the AskUserQuestion
  tool.
max_turns: 6
timeout_seconds: 300
allowed_tools: [Read, Glob, Grep, AskUserQuestion]
append_system_prompt: |
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
---

<!-- SPDX-License-Identifier: MIT -->

Set up the database for this service.
