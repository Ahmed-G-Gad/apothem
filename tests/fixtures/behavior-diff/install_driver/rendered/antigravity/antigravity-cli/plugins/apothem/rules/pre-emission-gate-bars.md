---
trigger: glob
description: "Path-filtered companion rule carrying the full Fifteen-Bars table (M1–M15 detailed Check + Failure→action columns), the Attestation Schema YAML block, and the iteration-on-failure protocol declared at the parent `pre-emission-gate.md` rule's anchor; demand-loaded when the assistant edits any artifact whose emission triggers the fifteen-bar gate."
globs: "**/*.md, **/CLAUDE.md, **/rules/**, **/commands/**, **/skills/**, **/agents/**, **/docs/**"
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Pre-Emission Gate — Fifteen-Bars Detail (Companion Sub-Rule)

## Purpose

Carry the executable detail of the fifteen-bar pre-emission gate the parent `rules/pre-emission-gate.md` anchors: the per-bar Check + Failure→action table, the Attestation Schema YAML block, and the iteration-on-failure protocol. Path-filtered — loads on any artifact-emission surface (Markdown, CLAUDE.md, rules, commands, skills, agents, docs) — so the parent's always-on payload stays lean while full bar-level fidelity lives at the demand-load surface. The parent retains the standing directive, the one-line bar list, the disclosure-surface paragraph, and the failure tells.

## Obligations

### 1. The Fifteen Bars — Full Detail

Every emitted artifact passes each bar individually. Mechanical-fraction bars (M2, M5, M7, M8, M10, M13, M15) carry executable matchers at `conformity/*-grep.py`, run as `PreToolUse` hook checks orchestrated by `conformity/gate.py`. Reasoned bars (M1, M3, M6, M9, M11, M12, M14) are agent-evaluated and recorded in the attestation block.

| # | Bar | Check (mechanical or reasoned) | Failure → action |
|---|---|---|---|
| 1 | M1 — Host agnosticism | Artifact's idioms match sibling-file idioms (formatter / linter / naming / layout). | Revise to match host conventions per `rules/host-discovery.md`. |
| 2 | M2 — Editorial disclosure | Every amendment / extension / refinement is disclosed with cited rationale. | Add disclosure ledger per `rules/disclosure-ledger.md`. |
| 3 | M3 — Ten dimensions | Each of the ten dimensions individually passes. | Revise on the failing dimension(s) per `rules/ten-dimension-check.md`. |
| 4 | M4 — Self-application | Gate attestation block is present in the artifact's working trace. | Record attestation. |
| 5 | M5 — Authority | No `<USER-CONFIRM:…>` placeholders remain unfilled. No invented personal / authoritative data. | Re-route to inquiry surface per `rules/authority-inquiry.md`. |
| 6 | M6 — Expertise | Surfaced-gaps section is present where adjacent gaps exist; refinements cite rationale. | Surface gaps; cite per `rules/expertise-posture.md`. |
| 7 | M7 — Option annotation | Every multi-option choice carries `**Recommended**` + specific rationale. | Annotate per `rules/option-annotation.md`. |
| 8 | M8 — Definitiveness | Hedging vocabulary absent in prescriptive contexts; pre / post / failure conditions stated. | Promote hedging to conditionals; state contracts per `rules/definitiveness.md`. |
| 9 | M9 — Visual leverage | Structural subject matter has a current-reality diagram with provenance + verification date. | Author / refresh diagram per `rules/visual-leverage.md`. |
| 10 | M10 — Bidirectional binding | Substantive elements declare bindings; reciprocity is closed. | Close half-edges per `rules/bidirectional-binding.md`. |
| 11 | M11 — Agile sprints | For non-trivial work: Sprint Goal + Backlog + DoR + DoD + Review + Retrospective populated. | Restructure as sprints per `rules/agile-sprints.md`. |
| 12 | M12 — Phase reporting & layout | For multi-phase work: per-sub-phase reports + phase-level rollup; outputs at canonical layout. | Author rollup; relocate per `rules/canonical-layout.md`. |
| 13 | M13 — Code craft | Code passes host's lint / format / type-check; why-not-what comments; no magic numbers / bare-except / commented-out blocks. | Revise per `rules/code-craft-python.md` and sibling per-language code-craft rules. |
| 14 | M14 — Systemicity | New components declare upstream / downstream / peers / enforcers; indexed in host registries. | Declare; index per `rules/systemic-participation.md`. |
| 15 | M15 — Production-ready | Code change ships with tests + docs + CHANGELOG entry + conformant commit + CI green. | Add missing surfaces per `rules/production-ready-prs.md`. |

### 2. Attestation Schema

The attestation is appended to the artifact's working trace (commit body, PR description, change ledger, dedicated `attestation.yml`):

```yaml
conformity-attestation:
  artifact: <path-or-identifier>
  ecosystem-version: <git-commit-sha-or-equivalent ratifying the rule set in force>
  bars:
    M1-host-agnosticism:        pass | n/a (with reason)
    M2-editorial-disclosure:    pass | n/a
    M3-ten-dimensions:          pass | n/a
    M4-self-application:        pass
    M5-authority:               pass
    M6-expertise:               pass | n/a
    M7-option-annotation:       pass | n/a (no option set)
    M8-definitiveness:          pass
    M9-visual-leverage:         pass | n/a (subject not structural)
    M10-bidirectional-binding:  pass | n/a (subject not structural-multi-element)
    M11-agile-sprints:          pass | n/a (trivial work)
    M12-phase-layout:           pass | n/a (single-artifact emission)
    M13-code-craft:             pass | n/a (not code)
    M14-systemicity:            pass
    M15-production-ready:       pass | n/a (no host-public-surface change)
  surfaced-gaps: []
  unresolved-inquiries: []
  amendments-disclosed: []
  date: <ISO-8601>
```

Every `n/a` is explicit and reasoned — never a silent skip. The `ecosystem-version` field anchors the attestation to a reproducible ecosystem state (the apothem source-repo commit when the gate ran), so a future audit can replay the gate against the same rule bodies.

### 3. Iteration on failure

A single bar failure blocks emission. Revise the artifact per the failing bar's "Failure → action" cell — which names the rule that owns the revision protocol — and re-run the gate. Iterate until every bar passes, then emit with the attestation recorded. The loop is capped at three revision rounds per `rules/planning-techniques.md` §1: when a bar still fails after the third round, do not emit and do not soften the bar. Stop and report BLOCKED with each failing bar, its evidence, and the rule that owns its revision, so the operator decides the next step.

## Enforcement

Path-filtered (the seven glob patterns in this rule's `pathFilter` field), always-on at every seriousness level when in scope. Demand-loaded companion to `rules/pre-emission-gate.md`. The parent carries the standing directive, one-line bar list, disclosure-surface paragraph, and failure tells; this companion carries the bar-level table, the attestation YAML schema, and the iteration-on-failure protocol.

## Bindings (§0.j five-direction)

- **Drives →** ● The per-bar Check + Failure→action enforcement on every emitted artifact under the path-filter. ● The attestation YAML schema's appearance in every artifact's working trace. ● The iteration-on-failure protocol's revise-and-re-run loop, capped at three rounds with a BLOCKED retreat.
- **Satisfies →** ● the fifteen-mandate registry row **M4 — Self-Application** (companion-sub-rule materialization). ● the Pre-Emission Gate Attestation Schema. ● `rules/pre-emission-gate.md` anchor (the parent rule's pointer to this companion's full bar-level catalog).
- **Established by ↑** ● `rules/pre-emission-gate.md` (parent-rule anchor). ● the Pre-Emission Gate. ● the Pre-Emission Gate Attestation Schema.
- **Gated by ←** ● The path-filter (seven glob patterns) — this rule demand-loads only on emission-surface touches. ● `rules/pre-emission-gate.md` always-on baseline (parent rule's anchor must be live for the companion to demand-load coherently).
- **Cross-bound with ↔** ↔ `rules/pre-emission-gate.md` (parent rule; anchor binds this companion). ↔ Every M-rule named in the gate's "Failure → action" column (`rules/host-discovery.md`, `rules/disclosure-ledger.md`, `rules/ten-dimension-check.md`, `rules/authority-inquiry.md`, `rules/expertise-posture.md`, `rules/option-annotation.md`, `rules/definitiveness.md`, `rules/visual-leverage.md`, `rules/bidirectional-binding.md`, `rules/agile-sprints.md`, `rules/canonical-layout.md`, `rules/code-craft-python.md` and sibling per-language code-craft rules, `rules/systemic-participation.md`, `rules/production-ready-prs.md`).
