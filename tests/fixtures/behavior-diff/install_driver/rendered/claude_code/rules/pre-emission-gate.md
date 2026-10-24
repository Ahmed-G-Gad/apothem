---
name: "pre-emission-gate"
description: "Fifteen-bar pre-emission gate — every host-project artifact passes M1 through M15 before emission, with a recorded YAML attestation and explicit n/a reasoning where a bar does not apply."
pathFilter: "**/CLAUDE.md, **/AGENTS.md, **/rules/**/*.md, **/commands/**/*.md, **/skills/**/*.md, **/agents/**/*.md, **/hooks/**/*.md, **/output-styles/**/*.md"
alwaysApply: false
paths:
  - "**/CLAUDE.md"
  - "**/AGENTS.md"
  - "**/rules/**/*.md"
  - "**/commands/**/*.md"
  - "**/skills/**/*.md"
  - "**/agents/**/*.md"
  - "**/hooks/**/*.md"
  - "**/output-styles/**/*.md"
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Pre-Emission Gate — Fifteen-Bar Self-application

## What this rule enforces

This rule binds **M4 — Self-application: Every Artifact Passes the Same Bar Before Emission**. Every artifact the ecosystem emits in a host project — commit, diff, file, PR description, comment, response, doc page, diagram, test, example, migration script, config entry — MUST itself clear all fifteen mandates. Quality is a pre-emission concern, never a downstream "the user can revise it" concern. The bar is **fifteen**: M1 through M15, where M3 is itself the ten-dimension check. An artifact that fails any single bar MUST be revised before it leaves the agent's hands.

## Pre-conditions

Applies before any meaningful-scope emission per the trivial-vs-non-trivial threshold. Trivial emissions (single-file edit ≤ 5 lines AND no public-API change AND no behavioral shift) run an abbreviated gate covering **M4** (attestation present) and **M5** (no `<USER-CONFIRM:…>` placeholders) only.

## Required behavior

### The Fifteen Bars (one-line summary)

Each bar MUST pass individually before emission:

- **M1** Host agnosticism · **M2** Editorial disclosure · **M3** Ten dimensions · **M4** Self-application · **M5** Authority · **M6** Expertise · **M7** Option annotation · **M8** Definitiveness · **M9** Visual leverage · **M10** Bidirectional binding · **M11** Agile sprints · **M12** Phase reporting & layout · **M13** Code craft · **M14** Systemicity · **M15** Production-ready.

Mechanical bars (M5, M7, M8, M10, M13) carry executable matchers at `conformity/*-grep.py` orchestrated by `conformity/gate.py`. Mechanical-and-reasoned bars (M3, M9, M12, M14, M15) have matchers that cover one named part of the bar; the agent evaluates the rest. Reasoned bars (M1, M2, M4, M6, M11) have no matcher and are agent-evaluated and recorded in the attestation.

(Companion Sub-Rule Anchor) See `rules/pre-emission-gate-bars.md` §1 for the per-bar Check + Failure→action table.

### Attestation Schema

The attestation is appended to the artifact's working trace (commit body, PR description, change ledger, or a dedicated `attestation.yml`): one `pass | n/a (with reason)` line per bar, plus the `surfaced-gaps`, `unresolved-inquiries`, and `amendments-disclosed` arrays, an `artifact` identifier, an `ecosystem-version` SHA, and an ISO-8601 `date`. Every `n/a` MUST carry a reason — silent skips are non-conformant. (Companion Sub-Rule Anchor) See `rules/pre-emission-gate-bars.md` §2 for the YAML schema.

### Iteration on failure

A single bar failure blocks emission. Revise per that bar's "Failure → action" rule, then re-run the gate; repeat until every bar passes, for at most three revision rounds. A bar still failing after the third round stops the run as BLOCKED with the failing bars and their evidence, never a softened pass. (Companion Sub-Rule Anchor) See `rules/pre-emission-gate-bars.md` §3.

## Disclosure surface

The attestation block IS the disclosure surface. Surfaced gaps (M6), unresolved inquiries (M5), and disclosed amendments (M2) populate three named arrays; empty arrays are written explicitly (`surfaced-gaps: []`), never elided.

## Failure tells

A commit that breaks the host's lint. A PR description with a dead link. A doc page citing a phantom URL. A diagram describing a flow the code does not implement. An attestation marked `pass` while a checked condition demonstrably fails. A bar marked `n/a` with no reason. An attestation missing the `date` or `ecosystem-version` field. A `pass` attestation on an artifact a mechanical `conformity/*-grep.py` flags as failing.
