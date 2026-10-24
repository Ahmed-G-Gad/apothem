<!-- SPDX-License-Identifier: MIT -->

## Foundational Stanzas

The four standing surfaces every operator inherits per the canonical project voice at `AGENTS.md` plus the active harness mirror, scoped to the research-ideate domain.

### Refusal & Escalation

REFUSE any task whose scope exceeds this stage's stated mission (producing a framed problem space plus a ranked candidate-question slate). Refusal is explicit: name what was refused, name the mission boundary the request crossed, and surface an escalation option through the structured-inquiry channel per `rules/interactive-questions.md`. REFUSE framing a candidate question that admits no refuting observation — re-frame it until it carries a falsifiable form (R3) or drop it from the slate. REFUSE proposing a candidate that re-tests a hypothesis the invalidated-prior-hypothesis scan shows already refuted, unless the operator explicitly directs a replication.

### Output Surface

This stage emits `{suite}/_inputs/ideation.md` (the framed problem space + ranked slate) and `{suite}/_inputs/handoff-manifest.yml` (the Handoff Manifest) per the suite-locality invariant at `rules/context-management.md` §2.6.1 and the research-suite storage convention. NEVER write to a global plans directory under any harness's config root (e.g., `~/.claude/.plans/` for the claude_code harness) from a downstream-project context, and NEVER write to any other global-ecosystem location (`~/.config/`, `/etc/`, vendored language-runtime trees).

### File-Authoring Contract

The ideation artifact is header-exempt per the `.apothem/**` exception class enumerated at `src/apothem/schemas/header-exceptions.txt`; the injector at `scripts/inject-header.{sh,py}` is therefore NOT invoked on this emission. Every candidate question's prior-art grounding cites its source documentarily (permalinked URL, author or organization, access date); the source itself is never authored or rewritten by this command.

### Structured Inquiry on Ambiguity

When uncertain about the research domain, the theoretical anchor, a ranking criterion, a domain boundary, or whether a candidate's prior-art grounding is real, route the resolution through the structured-inquiry channel with the three-segment option annotation per `rules/interactive-questions.md` §3 (rationale / recommendation / default-pointer). Host-ratified conventions are discovered, not invented, per `rules/host-discovery.md`. Free-form prose questions as primary input are forbidden. NEVER fabricate authoritative data — a prior-art claim, a domain fact, or a citation is grounded in a real source or surfaces as a `USER-CONFIRM` placeholder until the operator supplies it (R1, R4).
