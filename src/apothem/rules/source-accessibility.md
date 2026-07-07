---
name: "source-accessibility"
description: "Source trust outranks source accessibility — reach a trusted but inaccessible source via browser then operator interview; never prefer an untrusted-but-free source over a trusted-but-inaccessible one; record the source-trust decision in the ledger."
pathFilter: ""
alwaysApply: true
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Source Accessibility — Trust Outranks Reachability

## Purpose

Govern source selection when the authoritative source for a claim, convention, API contract, or version pin is hard to reach. Convenience MUST NOT silently demote authority: a paywalled specification, a login-gated vendor doc, or an offline standard stays the source of record even when a free, open, lower-trust page is one click away. This rule fixes the ranking and the escalation path so the agent reaches the trusted source instead of the reachable one.

## Obligations

### 1. Trust outranks accessibility

When candidate sources conflict on trust and on reachability, the higher-trust source wins regardless of how much harder it is to reach. The agent MUST NOT prefer an untrusted-but-accessible source — an SEO blog, a forum answer, a model's own recollection, a mirror of unknown fidelity — over a trusted-but-inaccessible one: the vendor's official doc, the ratified standard, the primary specification, the maintainer's own statement.

### 2. Escalate to reach the trusted source

A trusted source that is not immediately readable MUST be reached through an ordered escalation, not abandoned:

1. Retrieve it directly through the host's browser / fetch capability — declared per-harness in `capabilities.yml` `web_fetch` (the backing dimension per `rules/agent-capability-discipline-matrix.md` §1A). A `no` / `discovery-pending` cell means no capability to invoke; escalate to step 2.
2. Where that capability is absent, or the source sits behind credentials the agent does not hold, interview the operator for the content or for access per `rules/authority-inquiry.md`.

The agent settles for a lower-trust substitute only after both steps are exhausted, and MUST disclose the substitution.

### 3. Record the source-trust decision

Every source-selection decision of meaningful scope MUST record, in the change ledger per `rules/disclosure-ledger.md`: which source was used, its trust tier, whether the first-choice trusted source was reachable, and — when a substitute was used — why the trusted source was not reachable. A claim resting on a lower-trust source carries that provenance with it.

## Seriousness Scaling

(Companion Sub-Rule Anchor) See `rules/source-accessibility-scaling-tells.md` §Seriousness-Scaling for the four-level enforcement table (EXPLORING prefer-trusted → PUBLIC_LAUNCH no-substitute-without-recorded-exhaustion).

## Enforcement

Always-on at every seriousness level, scaling per the table above. Source selection is a discrete behavior that precedes any claim the artifact rests on; the ranking and escalation apply before the claim is committed.

## Failure tells

(Companion Sub-Rule Anchor) See `rules/source-accessibility-scaling-tells.md` §Failure-tells for the enumeration — low-trust page over gated doc, no-browser-attempt justification, forum-sourced version pin or security claim, unrecorded trust downgrade.

## Bindings (§0.j five-direction)

- **Drives →** Every source-selection decision behind a claim, a convention adoption, an API-contract reading, or a version pin across every ecosystem surface; the provenance each lower-trust-sourced claim must carry.
- **Satisfies →** The standing-mandate end-state that authority, not convenience, decides which source a claim rests on.
- **Established by ↑** The operator's standing-mandate set (the inaccessible-source mandate — trust outranks reachability).
- **Gated by ←** The host's browser / fetch capability surface — declared per-harness in `capabilities.yml` `web_fetch` per `rules/agent-capability-discipline-matrix.md` §1A — and the operator-interview channel (the two reachability paths the escalation depends on).
- **Cross-bound with ↔** `rules/source-accessibility-scaling-tells.md` (path-filtered companion carrying the §Seriousness-Scaling table and the §Failure-tells enumeration); `rules/authority-inquiry.md` (M5 — the operator-interview channel this rule escalates to when a trusted source is credential-gated is owned there); `rules/ten-dimension-check.md` (dimension 9 Scholarly / technical referencing — source-trust selection is the upstream behavior that referencing dimension verifies); `rules/disclosure-ledger.md` (M2 — the source-trust decision is recorded as a ledger entry); `rules/authoritative-referencing.md` (the trust-outranks-accessibility ranking decides WHICH source that referencing mandate cites). ↔ `rules/agent-capability-discipline-matrix.md` (the §1A `web_fetch` column is the backing dimension for that rule's step-1 browser/fetch escalation; reciprocal of its `Gated by ←` web-fetch citation). ↔ `rules/authoritative-referencing-quotation.md` (source-trust ranking decides which source is cited; this companion bounds how much of it is reproduced).
