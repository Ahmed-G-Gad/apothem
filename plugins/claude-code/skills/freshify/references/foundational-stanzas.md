<!-- SPDX-License-Identifier: MIT -->

## Foundational Stanzas

The four standing surfaces every operator inherits per the canonical project voice at `AGENTS.md` plus the active harness mirror.

### Refusal & Escalation

REFUSE any task whose scope exceeds this command's mission (freshening a target repository and emitting the freshening report). Refusal is explicit: name what was refused, name the mission boundary crossed, and surface an escalation option through the structured-inquiry channel per `rules/interactive-questions.md`. REFUSE to publish, tag, or push — the command freshens a working tree, it does not release. REFUSE any irreversible action that has not cleared its per-target confirmation. REFUSE to name a forge, registry, or continuous-integration vendor in any emitted artifact — the agnostic boundary is non-negotiable.

### Output Surface

The freshened tree is modified in place by default. The freshening report lands at the consuming suite's `_outputs/freshify-report.md` per the suite-locality invariant at `rules/canonical-layout.md` §2.2; an optional sweep inventory lands at `_inputs/freshify-inventory.md`. Plan-internal files are header-exempt per the `.apothem/**` exception class enumerated at `src/apothem/schemas/header-exceptions.txt`; the injector at `scripts/inject-header.py` is therefore NOT invoked on the report. Host source files the command freshens retain or receive the canonical SPDX header per the `rules/host-discovery.md`-discovered comment family. NEVER write the report outside the suite folder; NEVER write to a global plans directory under any harness's config root; NEVER write to any other global-ecosystem location.

### File-Authoring Contract

When the command edits a host source file in place, it preserves the host's ratified idioms per `rules/host-discovery.md` and the canonical SPDX header per the discovered comment family. The freshening report is header-exempt per the `.apothem/**` exception class; the command never invokes the authorship-header injector on its own emissions. When a removal cites a surface, the citation is documentary (`file:line`); a removed back-reference is named before deletion.

### Structured Inquiry on Ambiguity

When uncertain about the ignore manifest's contents, the quality-gate command set, the changelog format, the versioning scheme, whether a narrative passage is legacy-and-removable or current-and-load-bearing, or any destructive-step target, route the resolution through the structured-inquiry channel with the three-segment option annotation per `rules/interactive-questions.md` §3. Free-form prose questions as primary input are forbidden. NEVER fabricate a removal — every removal cites a concrete `file:line` plus the freshening rationale, and every irreversible removal clears its per-target confirmation first.
