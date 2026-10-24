<!-- SPDX-License-Identifier: MIT -->

## Foundational Stanzas

The four standing surfaces every operator inherits per the canonical project voice at `AGENTS.md` plus the active harness mirror. Spelled out inline here so this command honors them at the surface, not via cross-reference alone.

### Refusal & Escalation

REFUSE any task whose scope exceeds this command's stated mission (building the SMART aims hierarchy, the feasibility assessment, the resource / timeline / risk register, the impact pathway, the preregistration plan, and the reporting-guideline pre-selection from the synthesis and theory). Refusal is explicit: name what was refused, name the mission boundary the request crossed, and surface an escalation option through the structured-inquiry channel per `rules/interactive-questions.md`. REFUSE building the proposal when the synthesis or theory is absent or the predecessor Sequence Gate is unsatisfied — route back to `/research-synthesis` first. REFUSE committing an aim whose achievability the feasibility assessment cannot support — an infeasible aim is re-scoped or surfaced as a risk, never carried as a SMART aim. REFUSE fabricating an ethics fact, a resource cost, or a registry name — these are gathered from the suite or operator inquiry (R6).

### Output Surface

The proposal artifact lands at `{suite}/_inputs/proposal.md` per the suite-locality invariant at `rules/context-management.md` §2.6.1. Plan-internal files are header-exempt per the `.apothem/**` exception class enumerated at `src/apothem/schemas/header-exceptions.txt`; the injector at `scripts/inject-header.{sh,py}` is therefore NOT invoked on emission. NEVER write the proposal outside the suite folder; NEVER write to a global plans directory under any harness's config root from a downstream-project context; NEVER write to any other global-ecosystem location.

### File-Authoring Contract

The proposal artifact is header-exempt per the `.apothem/**` exception class; the command never invokes the authorship-header injector at `scripts/inject-header.{sh,py}` on its own emissions. Every aim traces to the explicit gap statement, every risk to a named constraint, every impact-pathway link to the theory of change; the preregistration plan names the registry it will be deposited to. Exemptions are enumerated at `src/apothem/schemas/header-exceptions.txt`.

### Structured Inquiry on Ambiguity

When uncertain about an aim's achievability, a resource estimate, the preregistration registry, the EQUATOR guideline selection, or an ethics-feasibility fact, route the resolution through the structured-inquiry channel with the three-segment option annotation per `rules/interactive-questions.md` §3. Host-ratified conventions are discovered, not invented, per `rules/host-discovery.md`. Free-form prose questions as primary input are forbidden. NEVER fabricate an authoritative datum — a resource cost, an ethics-approval pathway, a registry name, or a funding figure is discovered from the suite or inquired from the operator, never guessed (R6, and the authority-before-invention floor at `rules/authority-inquiry.md`).
