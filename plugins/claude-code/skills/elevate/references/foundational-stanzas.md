<!-- SPDX-License-Identifier: MIT -->

## Foundational Stanzas

The standing surfaces every operator inherits per the canonical project voice at `AGENTS.md` plus the active harness mirror.

### Refusal & Escalation

REFUSE any task whose scope exceeds this command's mission (elevating a target repository and handing off to `/freshify`). Refusal is explicit: name what was refused, name the mission boundary crossed, and surface an escalation option through the structured-inquiry channel per `rules/interactive-questions.md`. REFUSE to reimplement an audit/review pass — dispatch the first-class command through `/audit` and consume its findings. REFUSE to publish, tag, or push — `/elevate` elevates a working tree, it does not release. REFUSE any destructive remediation that has not cleared its per-target confirmation. REFUSE an unbounded open loop — the `--max-passes` cap and its bounded retreat are mandatory per `rules/planning-techniques.md` §1. REFUSE silent reconciliation of contradictory verification verdicts — surface both with evidence. REFUSE to preset a model or effort in any emitted artifact — the agnostic boundary is non-negotiable.

### Output Surface

The elevated tree is modified in place by default. The elevation report lands at the consuming suite's `_outputs/elevate-report.md` per the suite-locality invariant at `rules/canonical-layout.md` §2.2; an optional nuance inventory lands at `_inputs/elevate-inventory.md`. Plan-internal files are header-exempt per the `.apothem/**` exception class enumerated at `src/apothem/schemas/header-exceptions.txt`. Host source files the command elevates retain or receive the canonical SPDX header per the `rules/host-discovery.md`-discovered comment family. NEVER write the report outside the suite folder; NEVER write to a global plans directory under any harness's config root; NEVER write to any other global-ecosystem location.

### File-Authoring Contract

When the command edits a host source file in place, it preserves the host's ratified idioms per `rules/host-discovery.md` and the canonical SPDX header per the discovered comment family, and lands the change as a minimal, anchor-bounded diff through the `surgical-guard` skill per `rules/surgical-manipulation.md` — never a blunt whole-file overwrite where a scoped edit suffices. A rewrite-from-scratch re-derives the surface clean-room from its extracted intent per `rules/clean-room-generation.md` §3, preserving behavior (green-before / green-after per `rules/refactoring-discipline.md`). Every remediation cites the surface it touches (`file:line`) and the authoritative source backing the change; a removed surface is named before elimination. The command emits no sign of automated authorship, no backward or placeholder narrative, and no reference to obsolete, legacy, or retired artifacts. No host surface is edited before it is read in full context.

### Structured Inquiry on Ambiguity

When uncertain about the dimension scope, the SOTA exemplar for a surface, whether a nuance is load-bearing or eliminable, the most appropriate remediation action, or any destructive-remediation target, route the resolution through the structured-inquiry channel with the three-segment option annotation per `rules/interactive-questions.md` §3. Free-form prose questions as primary input are forbidden. NEVER fabricate a remediation — every change cites a concrete `file:line`, an authoritative source, and the elevation rationale, and every destructive change clears its per-target confirmation first.
