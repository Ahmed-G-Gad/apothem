<!-- SPDX-License-Identifier: MIT -->

## Foundational Stanzas

The four standing surfaces every operator inherits per the canonical project voice at `AGENTS.md` plus the active harness mirror.

### Refusal & Escalation

REFUSE any task whose scope exceeds this command's mission (producing the readiness verdict for a deployed repository). Refusal is explicit: name what was refused, name the mission boundary crossed, and surface an escalation option through the structured-inquiry channel per `rules/interactive-questions.md`. REFUSE to publish, tag, or push — the command emits a verdict, never a release. REFUSE authoring remediation patches — the surface is diagnostic only; remediation routes through `/plan-execute` or operator-initiated edits.

### Output Surface

The verdict artifact lands at the consuming suite's `_inputs/release-readiness-findings.md` per the suite-locality invariant at `rules/context-management.md` §2.6.1. Plan-internal files are header-exempt per the `.apothem/**` exception class enumerated at `src/apothem/schemas/header-exceptions.txt`; the injector at `scripts/inject-header.py` is therefore NOT invoked on emission. NEVER write the verdict outside the suite folder; NEVER write to a global plans directory under any harness's config root; NEVER write to any other global-ecosystem location; NEVER modify any source, workflow, manifest, or CHANGELOG.

### File-Authoring Contract

The verdict artifact is header-exempt per the `.apothem/**` exception class; the command never invokes the authorship-header injector at `scripts/inject-header.py` on its own emissions. New source files in the host carry the canonical SPDX header per the `rules/host-discovery.md`-discovered comment family, but this command authors no host source. When a finding cites a surface, the citation is documentary (`file:line`); the underlying source is never written.

### Structured Inquiry on Ambiguity

When uncertain about the quality-matrix command set, the signing-ratification posture, the CHANGELOG format, the versioning scheme, severity assignment on a borderline finding, or axis-of-attention attestation, route the resolution through the structured-inquiry channel with the three-segment option annotation per `rules/interactive-questions.md` §3. Free-form prose questions as primary input are forbidden. NEVER fabricate findings — every finding cites a concrete `file:line` or command result plus the relevant production-ready clause.
