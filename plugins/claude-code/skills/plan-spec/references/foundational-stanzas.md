<!-- SPDX-License-Identifier: MIT -->

## Foundational Stanzas

The four standing surfaces every operator inherits per the canonical project voice at `AGENTS.md` plus the active harness mirror — honored inline here, not by cross-reference alone. Both Forge mode and `--quick` mode are bound by these stanzas.

### Refusal & Escalation

REFUSE any task whose scope exceeds this command's mission — Forge mode produces a spec-grade `_spec/spec.md` after multi-phase elicitation; `--quick` mode produces a single project-local lightweight plan file. Refusal is explicit: name what was refused, name the mission boundary crossed, and surface an escalation option through the structured-inquiry channel per `rules/interactive-questions.md` (three-segment annotation; never free-form prose as primary input). When prose elicitation surfaces a contradiction the operator must resolve, halt at G3 (Pre-amendment) and surface it rather than choosing silently.

### Output Surface

Forge mode emits to `{suite}/_spec/spec.md` (the promoted spec), `{suite}/_inputs/forge.md` (pre-promotion draft, deleted at G4), `{suite}/_inputs/extract-chunk-*.md` (extraction lineage), and `{suite}/_inputs/handoff-manifest.yml` (the G5 Manifest) per the suite-locality invariant at `rules/context-management.md` §2.6.1. `--quick` mode emits to `<project-root>/.apothem/plans/<YYYY-MM-DD>--<kebab-slug>.md`. NEVER write to a global plans directory under any harness config root (e.g., `~/.claude/.plans/` on the claude_code harness) from a downstream-project context, and NEVER write to any other global-ecosystem location (`~/.config/`, `/etc/`, vendored language-runtime trees). `--quick` refuses any path resolving under a harness config root or sibling global location; refusal is explicit per §Mode `--quick` Behavior step 2.

### File-Authoring Contract

Plan files — Forge mode's `{suite}/_spec/spec.md` and `--quick` mode's `<project-root>/.apothem/plans/<filename>.md` — are header-exempt per the `.apothem/**` exception class at `src/apothem/schemas/header-exceptions.txt`; the injector at `scripts/inject-header.{sh,py}` is therefore NOT invoked on plan-file emissions. When this command incidentally authors a non-plan file (a fresh or updated `.gitignore` snippet, for example), the file is exempt as a configuration artifact under the same exception list. The contract is explicit: this command never injects banners; all banner-applicable files are out of its emission surface.

### Structured Inquiry on Ambiguity

When uncertain about identity / scope / preference / security / naming / infrastructure / version data — or any branch-point, deletion decision, or judgment call that materially affects the outcome — route the resolution through the structured-inquiry channel with the three-segment annotation per `rules/interactive-questions.md` §3 (rationale / recommendation / default-pointer). Free-form prose questions as primary input are forbidden. NEVER fabricate authoritative data. Forge mode's ten structured-inquiry disciplines D1–D10 across G0–G5 operationalize this stanza at gate granularity; `--quick` mode's project-root inquiry at §Mode `--quick` Behavior step 1 is the lightweight surface.
