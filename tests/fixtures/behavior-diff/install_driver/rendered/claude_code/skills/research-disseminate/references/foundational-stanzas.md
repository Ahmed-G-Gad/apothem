<!-- SPDX-License-Identifier: MIT -->

## Foundational Stanzas

The four standing surfaces every operator inherits per the canonical project voice at `AGENTS.md` plus the active harness mirror. Spelled out inline here so this command honors them at the surface, not via cross-reference alone.

### Refusal & Escalation

REFUSE any task whose scope exceeds this command's stated mission (planning the preprint announcement, the public artifacts, the FAIR archival deposit, the impact tracking, the rebuttal / revision loop, and the registered-report stage-2 path from the publication record). Refusal is explicit: name what was refused, name the mission boundary the request crossed, and surface an escalation option through the structured-inquiry channel per `rules/interactive-questions.md`. REFUSE planning dissemination when the publication record is absent or the predecessor Sequence Gate is unsatisfied — route back to `/research-publish` first. REFUSE altering any scientific claim during dissemination: a public artifact restates the published paper, it never edits a result or invents a new conclusion. REFUSE fabricating an archival identifier, an accession, or an impact metric — a DOI, a repository accession, or an altmetric figure the deposit has not minted surfaces as a required inquiry and blocks the plan line, never ships as an invented value (R8, R10). REFUSE performing the public actions on the operator's behalf — the stage produces a ready plan and stops; the operator posts the preprint, deposits the archive, and publishes the artifacts.

### Output Surface

The dissemination-and-impact record lands at `{suite}/_outputs/dissemination-plan.md` per the suite-locality invariant at `rules/context-management.md` §2.6.1. Plan-internal files are header-exempt per the `.apothem/**` exception class enumerated at `src/apothem/schemas/header-exceptions.txt`; the injector at `scripts/inject-header.{sh,py}` is therefore NOT invoked on the dissemination plan. Host-natural public-artifact source files (a blog draft, a talk script, a poster source) honor the host's document conventions per `rules/host-discovery.md`. NEVER write the plan outside the suite folder or its discovered host-natural deliverable locations; NEVER write to a global plans directory under any harness's config root from a downstream-project context; NEVER write to any other global-ecosystem location.

### File-Authoring Contract

The dissemination plan is header-exempt per the `.apothem/**` exception class; the command never invokes the authorship-header injector at `scripts/inject-header.{sh,py}` on its own `_outputs/` emissions. Public-artifact documents authored at the host-natural location are subject to the host's discovered file-header, document-format, and code-craft conventions per `rules/host-discovery.md`, `rules/code-craft-markdown.md`, and `rules/code-craft-python.md` (or the host's per-language sibling). Every plan line traces to its source: the preprint announcement to the publish stage's reserved DOI, the archival deposit to the actual data and code locations the experiment and analysis stages recorded (R2, R8), the impact-tracking plan to the proposal's impact pathway (R10). Exemptions are enumerated at `src/apothem/schemas/header-exceptions.txt`.

### Structured Inquiry on Ambiguity

When uncertain about the archival repository, the preprint server, the data/code-availability basis, an impact-tracking authority, or a public-artifact venue, route the resolution through the structured-inquiry channel with the three-segment option annotation per `rules/interactive-questions.md` §3. Host-ratified conventions are discovered, not invented, per `rules/host-discovery.md`. Free-form prose questions as primary input are forbidden. NEVER fabricate an authoritative datum — an archival accession, a persistent identifier, an altmetric figure, or a repository name is discovered from the suite or inquired from the operator, never guessed (R8, R10, and the authority-before-invention floor at `rules/authority-inquiry.md`).
