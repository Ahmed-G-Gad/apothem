<!-- SPDX-License-Identifier: MIT -->

## Foundational Stanzas

The four standing surfaces every operator inherits per the canonical project voice at `AGENTS.md` plus the active harness mirror. Spelled out inline here so this command honors them at the surface, not via cross-reference alone.

### Refusal & Escalation

REFUSE any task whose scope exceeds this command's stated mission (assembling the nine-section manuscript from the synthesis, study design, and analysis, with every citation verified). Refusal is explicit: name what was refused, name the mission boundary the request crossed, and surface an escalation option through the structured-inquiry channel per `rules/interactive-questions.md`. REFUSE writing the paper when the analysis, synthesis, or study design is absent or the predecessor Sequence Gate is unsatisfied — route back to `/research-analysis` first. REFUSE claiming a result the analysis marked `fragile` or `unverified` as a confirmed finding: only `confirmed` results from the analysis anchor the paper's claims, and a fragile effect is reported in the limitations section with the perturbation that breaks it named. REFUSE citing a source that does not resolve: a citation whose target the fact-checker cannot retrieve is a phantom citation and never lands (R4).

### Output Surface

The manuscript lands at the host-natural location discovered per `rules/host-discovery.md` (`paper/`, e.g. `paper/manuscript.md` or the host's ratified manuscript format and path), never inside `.apothem/plans/`. The verification attestation and reference-resolution record land at `{suite}/_outputs/paper-attestation.md` and `{suite}/_inputs/reference-ledger.md` per the suite-locality invariant at `rules/context-management.md` §2.6.1. Host-natural manuscript source files honor the host's authorship-header convention per `rules/host-discovery.md`; the suite-internal attestation and ledger files are header-exempt per the `.apothem/**` exception class enumerated at `src/apothem/schemas/header-exceptions.txt`. NEVER write the manuscript outside the discovered host-natural deliverable location; NEVER write to a global plans directory under any harness's config root from a downstream-project context; NEVER write to any other global-ecosystem location.

### File-Authoring Contract

The suite-internal attestation (`{suite}/_outputs/paper-attestation.md`) and reference ledger (`{suite}/_inputs/reference-ledger.md`) are header-exempt per the `.apothem/**` exception class; the command never invokes the authorship-header injector at `scripts/inject-header.{sh,py}` on its own suite-internal emissions. The manuscript and any figure/table assets authored at the host-natural location are subject to the host's discovered file-header, prose, and code-craft conventions per `rules/host-discovery.md`, `rules/code-craft-markdown.md`, and `rules/code-craft-python.md` (or the host's per-language sibling), and pass the host's lint / format / prose-lint unmodified. Every claim traces to its evidence: a results claim links to the `_outputs/analysis.md` result that earned it, and a related-work claim links to the resolvable reference in the reference ledger (R1, R4). Exemptions are enumerated at `src/apothem/schemas/header-exceptions.txt`.

### Structured Inquiry on Ambiguity

When uncertain about the venue or citation style the host carries no convention for, the manuscript's authorship identity, whether a synthesis claim has a resolvable source, or whether a result the operator wants foregrounded was actually confirmed by the analysis, route the resolution through the structured-inquiry channel with the three-segment option annotation per `rules/interactive-questions.md` §3. Host-ratified conventions (the manuscript format, the citation style, the reference-manager format) are discovered, not invented, per `rules/host-discovery.md`. Free-form prose questions as primary input are forbidden. NEVER fabricate a citation, an author, an affiliation, or a result — every reference traces to a real retrievable source, every author traces to operator-supplied identity, and every reported result traces to a `confirmed` entry in `_outputs/analysis.md` (R1, R4, R6).
