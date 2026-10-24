<!-- SPDX-License-Identifier: MIT -->

## Foundational Stanzas

The four standing surfaces every operator inherits per the canonical project voice at `AGENTS.md` plus the active harness mirror.

### Refusal & Escalation

REFUSE any task whose scope exceeds this command's stated mission (producing the per-dependency findings artifact for a deployed repository). Refusal is explicit: name what was refused, name the mission boundary the request crossed, and surface an escalation option through the structured-inquiry channel. REFUSE audit against a repository whose lockfiles are missing or stale (the transitive graph cannot be deterministically walked without lockfiles). REFUSE authoring remediation patches — the command's surface is diagnostic only; remediation routes through `/plan-execute` or operator-initiated edits.

### Output Surface

The findings artifact lands at the consuming suite's `_inputs/dependency-audit-findings.md` per the suite-locality invariant at `rules/context-management.md` §2.6.1. Plan-internal files are header-exempt per the `.apothem/**` exception class enumerated at `src/apothem/schemas/header-exceptions.txt`; the injector at `scripts/inject-header.{sh,py}` is therefore NOT invoked on emission. NEVER write the findings artifact outside the suite folder; NEVER write to a global plans directory under any harness's config root from a downstream-project context; NEVER write to any other global-ecosystem location; NEVER modify any manifest or lockfile — the command is read-only against the repository.

### File-Authoring Contract

The findings artifact is header-exempt per the `.apothem/**` exception class. The command never invokes the authorship-header injector on its own emissions. When a finding cites a manifest entry, the citation is documentary (`manifest:line`); the underlying manifest is never written by this command.

### Structured Inquiry on Ambiguity

When uncertain about manifest scope, focus boundary, severity assignment on borderline CVSS / license / deprecation findings, or axis-of-attention attestation on multi-axis findings, route the resolution through the structured-inquiry channel with the three-segment option annotation per `rules/interactive-questions.md` §3. Free-form prose questions as primary input are forbidden. NEVER fabricate findings — every finding cites a concrete `manifest:line` or `package@version` plus the detecting tool (pip-audit advisory ID, safety CVE ID, osv-scanner GHSA / CVE).
