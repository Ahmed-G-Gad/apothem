---
description: 'Effect of the always-on rule option-annotation: the same prompt and graders with the rule''s
  runtime text appended to the system prompt (on in this case). Plugin eval runs load no rules, so the
  pair isolates the rule''s effect.'
tags: [rule-effect, 'rule:option-annotation', 'arm:rule-on', rule-scoping-regression]
expected_outcome: One option carries a (Recommended) marker with a reason.
max_turns: 6
timeout_seconds: 300
allowed_tools: [Read, Glob, Grep, AskUserQuestion]
append_system_prompt: |
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
---

<!-- SPDX-License-Identifier: MIT -->

List three options for storing session data in a small Flask app, with the trade-offs of each.
