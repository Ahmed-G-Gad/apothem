<!-- SPDX-License-Identifier: MIT -->

## Foundational Stanzas

The four standing surfaces every operator inherits per the canonical project voice at `AGENTS.md` plus the active harness mirror.

### Refusal & Escalation

REFUSE any task whose scope exceeds this command's mission (producing the architectural-design artifact for a reviewed plan suite). Refusal is explicit: name what was refused, name the mission boundary crossed, and surface an escalation option through the structured-inquiry channel. REFUSE design authoring against an un-reviewed suite (no Review Scorecards in PLAN-NOTES.md) at SHARED+ — route through `/plan-review` first. REFUSE design authoring whose architectural surface exceeds the spec's ratified scope — surface the scope drift as an inquiry.

### Output Surface

The design artifact lands at the consuming suite's `_inputs/design.md` per the suite-locality invariant at `rules/context-management.md` §2.6.1. The Manifest update at `_inputs/handoff-manifest.yml` is suite-internal. Plan-internal files are header-exempt per the `.apothem/**` exception class at `src/apothem/schemas/header-exceptions.txt`; the injector at `scripts/inject-header.{sh,py}` is therefore NOT invoked on emission. NEVER write the design artifact outside the suite folder; NEVER write to a global plans directory under any harness config root from a downstream-project context; NEVER write to any other global-ecosystem location.

### File-Authoring Contract

The design artifact is header-exempt per the `.apothem/**` exception class. The command never invokes the authorship-header injector on its own emissions. When the command incidentally references a codebase artifact path (a future `src/<package>/<module>.py` the design specifies), that reference is documentary; the artifact is authored later at `/plan-execute` time and routes through the injector then.

### Structured Inquiry on Ambiguity

When uncertain about identity / scope / preference / security / naming / infrastructure / version data — or any branch-point or judgment call that materially affects the architectural outcome — route the resolution through the structured-inquiry channel with the three-segment annotation per `rules/interactive-questions.md` §3. Free-form prose questions as primary input are forbidden. NEVER fabricate authoritative data. The Phase 1 architectural-decomposition pass is the dominant inquiry surface; every open architectural question surfaces there.
