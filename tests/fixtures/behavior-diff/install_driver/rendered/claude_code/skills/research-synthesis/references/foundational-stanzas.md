<!-- SPDX-License-Identifier: MIT -->

## Foundational Stanzas

The four standing surfaces every operator inherits per the canonical project voice at `AGENTS.md` plus the active harness mirror. Spelled out inline here so this command honors them at the surface, not via cross-reference alone.

### Refusal & Escalation

REFUSE any task whose scope exceeds this command's stated mission (producing a SOTA map, a literature matrix, and an explicit gap statement from the collected source corpus). Refusal is explicit: name what was refused, name the mission boundary the request crossed, and surface an escalation option through the structured-inquiry channel per `rules/interactive-questions.md`. REFUSE running synthesis when the source ledger is empty or the predecessor Sequence Gate is unsatisfied — route back to `/research-sources` first. REFUSE asserting a finding as established SOTA when adversarial verification leaves it contested — contested findings land in the contested-findings ledger with both positions and their evidence, never collapsed into a false consensus.

### Output Surface

The synthesis artifact lands at `{suite}/_inputs/synthesis.md` per the suite-locality invariant at `rules/context-management.md` §2.6.1. Plan-internal files are header-exempt per the `.apothem/**` exception class enumerated at `src/apothem/schemas/header-exceptions.txt`; the injector at `scripts/inject-header.{sh,py}` is therefore NOT invoked on emission. NEVER write the synthesis outside the suite folder; NEVER write to a global plans directory under any harness's config root from a downstream-project context; NEVER write to any other global-ecosystem location.

### File-Authoring Contract

The synthesis artifact is header-exempt per the `.apothem/**` exception class; the command never invokes the authorship-header injector at `scripts/inject-header.{sh,py}` on its own emissions. Every map entry and matrix cell cites its source by ledger ID; the citation is documentary (the ledger's permalinked URL, author or organization, access date), and the source itself is never authored or rewritten by this command. Exemptions are enumerated at `src/apothem/schemas/header-exceptions.txt`.

### Structured Inquiry on Ambiguity

When uncertain about the literature-matrix comparison dimensions, the resolution of a contested finding, the operative scope of the gap statement, or whether a borderline claim is corroborated or contested, route the resolution through the structured-inquiry channel with the three-segment option annotation per `rules/interactive-questions.md` §3. Host-ratified conventions are discovered, not invented, per `rules/host-discovery.md`. Free-form prose questions as primary input are forbidden. NEVER fabricate a citation — every synthesized claim traces to a real source ID in the ledger or is marked unverified in the contested-findings ledger (R1, R4).
