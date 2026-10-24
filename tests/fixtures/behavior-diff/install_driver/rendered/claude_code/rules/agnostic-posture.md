---
name: "agnostic-posture"
description: "Default-off, opt-in posture for every shipped behavior; correctness gates stay advisory; every surface is harness-neutral; model, effort, and workflow preference resolve only from an explicit in-conversation choice."
pathFilter: ""
alwaysApply: true
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Agnostic Posture — Default-Off, Opt-In, Harness-Neutral

## Purpose

Govern the shipped posture so a clean install imposes nothing — no workflow ceremony, no model or effort preset, no harness bias auto-applied. Every behavior is reachable, but only the end user turns it on. This rule is the standing frame every other shipped rule and command reads its enforcement defaults through.

## Obligations

### 1. Default-off behaviors

Workflow behaviors — the sprint apparatus, agent-team dispatch, parallel multitasking, continuous multi-step advancement, and continuous-learning capture — ship **default-off**. A clean install MUST run a request with none of them engaged. Each is opt-in through the shared profile's `enforcement` flags (every flag defaults `false`); set a flag `true` to invoke that behavior. Where a sibling rule marks one of these behaviors "always-on", "mandatory", or "required at" a tier, that marking describes the behavior's shape **once the operator opts in** — never an imposition on a clean install.

### 2. Advisory correctness gates

Correctness and quality gates — lint, format, type-check, test, security scan, conformance, the pre-emission gate — stay active but **advisory**. Each MUST emit its findings plus a definitive next step and then yield; none blocks, aborts, or silently mutates the end user's action. The end user decides what to do with a finding.

### 3. Harness neutrality

No shipped surface carries tailoring for one harness. Every rule, command, output-style, statusline, and template MUST render identically across every registered harness. A harness name appears only as one catalog entry among many — never as a tailored default, a privileged path, or an assumed runtime.

### 4. End-user-invoked preference

Model, effort, and workflow preference resolve only from an explicit in-conversation choice. No shipped config pre-determines them; the default state is unset, and the agent asks or waits rather than guessing.

### 5. Machinery preserved

De-enforced behavior MUST NOT be deleted. Each behavior keeps a working invocation path — an opt-in flag, a documented command, a named procedure — so opting in restores it intact. Preservation, not removal, is the discipline.

### 6. Verification

The per-invariant verification checklist for this posture — each of the five obligations restated as a checkable invariant with a concrete verification step — lives at the path-filtered companion `agnostic-posture-checklist.md`. Every phase that changes a shipped surface runs the checklist as its agnosticism definition-of-done gate.
