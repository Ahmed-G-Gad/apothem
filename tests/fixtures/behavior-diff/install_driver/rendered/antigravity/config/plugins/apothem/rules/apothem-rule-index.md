---
trigger: always_on
description: "The always-on index of the rule corpus — names the four rules that apply in every session, says how every other rule loads (path match, citation, or a read you make yourself), and groups all of them by the situation that calls for each, so a path-scoped rule is never missed for want of knowing it exists."
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Rule Index — Which Rule to Read When

## What loads

Four rules apply in every session: `agnostic-posture`, `authority-inquiry`, `session-closure`, `context-management`. A harness that loads rule files at launch has put them in your context with this index. Where yours did not, you MUST read them now. Every other rule is installed under `rules/` and scoped to the files it governs. A harness that scopes rules by path loads a scoped rule when a matching file is read or edited. A harness that does not scope by path loads none of them, so you MUST read the rule yourself. A companion (`<parent>-<aspect>`) is opened from the anchor line in its parent.

After a context compaction, a scoped rule is no longer in context. Read again any rule you were applying.

## When to read

A step that cites a rule as its procedure (`per rules/<name>.md`) MUST have that rule read first. A citation in a `## Bindings` section is navigation, not procedure. Otherwise read the rule whose situation holds.

- **Any tool call, or reading any request.** `tool-use-discipline`, `etc-extension`.
- **Writing or changing code.** `code-craft-python`, `code-craft-shell`, `code-craft-ui`, `code-craft-conventions`, `clean-architecture-layers`, `refactoring-discipline`, `surgical-manipulation`, `performance-discipline`, `large-file-generation`, `large-file-reading`.
- **Before emitting any artifact into a host project.** `host-discovery`, `systemic-participation`, `propagation`, `production-ready-prs`, `clean-room-generation`, `own-voice-reimplementation`, `pre-emission-gate`, `ten-dimension-check`, `disclosure-ledger`.
- **Judging output, wording prose, setting depth.** `operational-mandates`, `cognitive-identity`, `expertise-posture`, `definitiveness`, `code-craft-markdown`, `visual-leverage`, `token-efficiency-rewrite`.
- **Asking the user, or closing a turn.** `interactive-questions`, `option-annotation`, `recommend-next-step`, `determinism`.
- **Planning or executing phases.** `planning-techniques`, `agile-sprints`, `canonical-layout`.
- **Spawning agents, or touching a harness adapter.** `agent-orchestration`, `multi-agent-workflow`, `agent-capability-discipline`, `harness-adapter-shape`.
- **Editing docs, README, AGENTS.md, site, or other public surfaces.** `living-docs`, `agents-md-convention`, `freshness-facade`, `plain-language`, `dynamism`, `sota-elevation`, `i18n-discipline`.
- **Citing a claim, or choosing a source.** `authoritative-referencing`, `source-accessibility`.
- **Writing memory, or editing the rule corpus.** `auto-memory`, `persistent-conventions-vigilance`, `bidirectional-binding`, `token-budget-discipline`.

## Bindings (§0.j five-direction)

- **Drives →** ● The choice of which rule to read for a situation no path match covered. ● The re-read of a rule still in force after a context compaction.
- **Satisfies →** ● The small always-on set: four rules plus this index are the whole standing context, and every other rule costs context only where it applies.
- **Established by ↑** ● The operator decision to hold the always-on set to four rules plus this index. ● `rules/agnostic-posture.md` (the harness-neutral wording: no harness, tool, or loader is named here).
- **Gated by ←** ● The rule corpus under `rules/` (a new rule is named here in the same change-set; the index coverage test fails when one is not). ● The harness's own path scoping, which decides whether a scoped rule loads on a touch.
- **Cross-bound with ↔** ↔ `rules/token-budget-discipline.md` (the byte ceiling on the always-on set and on this index; this is the one always-on file that ceiling names).
