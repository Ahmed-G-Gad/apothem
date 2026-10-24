<!-- SPDX-License-Identifier: MIT -->

## Foundational Stanzas

The four standing surfaces every operator inherits per the canonical project voice at `AGENTS.md` plus the active harness mirror.

### Refusal & Escalation

REFUSE any task whose scope exceeds this command's stated mission (producing the cross-file forensic findings artifact for a deployed repository). Refusal is explicit: name what was refused, name the mission boundary the request crossed, and surface an escalation option through the structured-inquiry channel. REFUSE audit against a repository whose CI gate has not run (no test-coverage baseline; no lint baseline) at SHARED+ — route through the host's CI pipeline first. REFUSE audit whose forensic surface is per-file craft — route to `/code-review` instead; `/code-audit` is exclusively cross-file forensic. REFUSE audit against a repository larger than the host's discovered audit-scope ratification without operator confirmation through the structured-inquiry channel.

### Output Surface

The findings artifact lands at the consuming suite's `_inputs/code-audit-findings.md` per the suite-locality invariant at `rules/context-management.md` §2.6.1. The Handoff Manifest update at `_inputs/handoff-manifest.yml` is suite-internal. Plan-internal files are header-exempt per the `.apothem/**` exception class enumerated at `src/apothem/schemas/header-exceptions.txt`; the injector at `scripts/inject-header.{sh,py}` is therefore NOT invoked on emission. NEVER write the findings artifact outside the suite folder; NEVER modify files inside the audited repository (the audit is read-only against the target); NEVER write to any global-ecosystem location.

### File-Authoring Contract

The findings artifact is header-exempt per the `.apothem/**` exception class. The command never invokes the authorship-header injector on its own emissions. When the command incidentally references a codebase artifact path (a `src/<package>/<module>.py:NN` finding-citation), that reference is documentary — the audit is read-only and never edits the cited path. Remediation of findings is downstream of this command's terminal position; remediation routes through `/plan-execute` or operator-driven amendment after audit emission.

### Structured Inquiry on Ambiguity

When uncertain about identity / scope / preference / security / naming / infrastructure / version data — or about any branch-point or judgment call that materially affects the audit outcome — route the resolution through the structured-inquiry channel with the three-segment option annotation per `rules/interactive-questions.md` §3. Free-form prose questions as primary input are forbidden. NEVER fabricate authoritative data. The Phase 1 dependency-walk pass is the dominant inquiry surface; every open layer-assignment question surfaces there.
