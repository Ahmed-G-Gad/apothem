<!-- SPDX-License-Identifier: MIT -->

## Foundational Stanzas

The four standing surfaces every operator inherits per the canonical project voice at `AGENTS.md` plus the active harness mirror, scoped to the research-spec domain. Both default mode and `--quick` mode are bound by these stanzas.

### Refusal & Escalation

REFUSE any task whose scope exceeds this stage's stated mission (default mode produces a spec-grade `_spec/research-spec.md`; `--quick` mode produces a single project-local lightweight research brief). Refusal is explicit: name what was refused, name the mission boundary the request crossed, and surface an escalation option through the structured-inquiry channel per `rules/interactive-questions.md`. When framing surfaces a contradiction the operator must resolve — two hypotheses that cannot both hold, a scope that excludes its own success metric — halt and surface the contradiction instead of silently choosing.

### Output Surface

Default mode emits `{suite}/_spec/research-spec.md` (the promoted spec) and `{suite}/_inputs/handoff-manifest.yml` (the Handoff Manifest) per the suite-locality invariant at `rules/context-management.md` §2.6.1 and the research-suite storage convention. `--quick` mode emits `<project-root>/.apothem/plans/<YYYY-MM-DD>--<kebab-slug>.md` (a single project-local lightweight research brief). NEVER write to a global plans directory under any harness's config root (e.g., `~/.claude/.plans/` for the claude_code harness) from a downstream-project context, and NEVER write to any other global-ecosystem location (`~/.config/`, `/etc/`, vendored language-runtime trees). `--quick` refuses any path that resolves under any harness's config root or any sibling global location; refusal is explicit per §Mode `--quick`.

### File-Authoring Contract

Spec and brief files (default mode's `{suite}/_spec/research-spec.md` and `--quick` mode's `<project-root>/.apothem/plans/<filename>.md`) are header-exempt per the `.apothem/**` exception class enumerated at `src/apothem/schemas/header-exceptions.txt`. The injector at `scripts/inject-header.{sh,py}` is NOT invoked on these emissions. When this stage incidentally authors a non-plan file (a fresh or updated `<project-root>/.gitignore` snippet), the file is exempt as a configuration artifact under the same exception list. This stage never injects banners; all banner-applicable files are out of its emission surface.

### Structured Inquiry on Ambiguity

When uncertain about identity / scope / preference / security / naming / infrastructure / version data — or about any hypothesis form, scope boundary, metric threshold, inclusion criterion, or glossary definition that materially affects the spec — route the resolution through the structured-inquiry channel with the three-segment option annotation per `rules/interactive-questions.md` §3 (rationale / recommendation / default-pointer). Free-form prose questions as primary input are forbidden. NEVER fabricate authoritative data; gaps surface as `USER-CONFIRM` placeholders (the canonical `kind=`-tagged form) until the operator supplies them.
