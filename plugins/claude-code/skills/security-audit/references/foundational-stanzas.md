<!-- SPDX-License-Identifier: MIT -->

## Foundational Stanzas

The four standing surfaces every operator inherits per the canonical project voice at `AGENTS.md` plus the active harness mirror.

### Refusal & Escalation

REFUSE any task whose scope exceeds this command's stated mission (producing the security-audit findings artifact for a host repository). Refusal is explicit: name what was refused, name the mission boundary the request crossed, and surface an escalation option through the structured-inquiry channel. REFUSE audit execution against a repository whose ownership / scope / authorized-tester boundary is unclear — security audits against unauthorised systems are out-of-mission. REFUSE to publish findings whose disclosure timing exceeds the coordinated-disclosure window the operator has ratified — surface the disclosure-timing question as an inquiry.

### Output Surface

The findings artifact lands at the consuming suite's `_inputs/security-audit-findings.md` per the suite-locality invariant at `rules/context-management.md` §2.6.1, or at the operator-named path when invoked outside a plan-suite context. Plan-internal files are header-exempt per the `.apothem/**` exception class enumerated at `src/apothem/schemas/header-exceptions.txt`; the injector at `scripts/inject-header.{sh,py}` is therefore NOT invoked on emission. NEVER write the findings artifact outside the operator-ratified output surface; NEVER commit secret-bearing evidence (raw token values, private-key bodies) into the artifact — redact per `rules/code-craft-python.md` §4.1 secret-hygiene discipline.

### File-Authoring Contract

The findings artifact is header-exempt per the `.apothem/**` exception class. The command never invokes the authorship-header injector on its own emissions. When the command incidentally references a host codebase artifact path (a vulnerable `src/<package>/<module>.py` the audit cites), that reference is documentary; remediation patches are authored later by the operator and route through the injector then per the host's discovered authorship-header policy at `rules/host-discovery.md`.

### Structured Inquiry on Ambiguity

When uncertain about identity / scope / preference / security / naming / infrastructure / version data — or about any branch-point or judgment call that materially affects the audit outcome — route the resolution through the structured-inquiry channel with the three-segment option annotation per `rules/interactive-questions.md` §3. Free-form prose questions as primary input are forbidden. NEVER fabricate authoritative data. The Phase 0 input-ingest is the dominant inquiry surface; every authority-bearing audit assumption surfaces there.
