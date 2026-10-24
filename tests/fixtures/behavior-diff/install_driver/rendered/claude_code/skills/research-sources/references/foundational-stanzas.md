<!-- SPDX-License-Identifier: MIT -->

## Foundational Stanzas

The four standing surfaces every operator inherits per the canonical project voice at `AGENTS.md` plus the active harness mirror. Spelled out here so this command honors them inline, not by cross-reference alone.

### Refusal & Escalation

REFUSE any task whose scope exceeds this command's stated mission (assemble, dedup, rank, screen, and extract the source base for a spec-bearing research suite). Refusal is explicit: name what was refused, name the mission boundary the request crossed, and surface an escalation option through the structured-inquiry channel per `rules/interactive-questions.md` (canonical channel; three-segment option annotation; never free-form prose as primary input). Synthesis, claim combination, and the SOTA/gap map are out of scope — they route to `/research-synthesis`. When discovery surfaces a candidate that defeats the spec's scope boundary, halt and surface the boundary instead of silently widening the search.

### Output Surface

This command emits `{suite}/sources/<id>.md` (per-source extractions) and `{suite}/_inputs/source-ledger.md` (the ranked, screened ledger) per the suite-locality invariant at `rules/context-management.md` §2.6.1. Discovery scratch (raw candidate dumps, dedup working notes) lands at `{suite}/_inputs/notes.md` and is deleted or distilled at stage exit. NEVER write to a global plans directory under any harness's config root (e.g., `~/.claude/.plans/` for the claude_code harness) and NEVER write to any other global-ecosystem location (`~/.config/`, `/etc/`, vendored language-runtime trees). Raw fetched source bodies that exceed the extraction surface are not committed; the extraction record carries the permalink, the access date, and the extracted load-bearing content.

### File-Authoring Contract

Research-suite state files under `{suite}/` (the source ledger, the per-source extractions, the discovery scratch) are header-exempt per the `.apothem/**` exception class enumerated at `src/apothem/schemas/header-exceptions.txt`. The injector at `scripts/inject-header.{sh,py}` is therefore NOT invoked on these emissions. When this command incidentally authors a non-state file at a host-natural location, that file is subject to the canonical header discipline. The contract is explicit: this command never injects banners on suite-state emissions; all banner-applicable files are out of its emission surface.

### Structured Inquiry on Ambiguity

When uncertain about scope direction / screening criteria / source-budget ceiling / authority-ranking weights — or about any branch-point, inclusion decision, or judgment call that materially affects which sources survive — route the resolution through the structured-inquiry channel with the three-segment option annotation per `rules/interactive-questions.md` §3 (rationale / recommendation / default-pointer). Free-form prose questions as primary input are forbidden. NEVER fabricate a source, a URL, a DOI, an author, or a publication date (R1, R4); a candidate whose provenance cannot be verified is screened out and recorded as unverifiable, never invented into legitimacy.
