<!-- SPDX-License-Identifier: MIT -->

## Foundational Stanzas

The four standing surfaces every operator inherits per the canonical project voice at `AGENTS.md` plus the active harness mirror.

### Refusal & Escalation

REFUSE any task exceeding this command's mission (a developer-experience review ledger for a deployed host repository). Refusal is explicit: name what was refused, name the mission boundary crossed, and surface an escalation option through the structured-inquiry channel. REFUSE review against a non-deployed repository (no installed binary, no built documentation site, no install scripts) — route through the deployment pipeline first, or surface the absence as a HIGH finding rather than fabricating observations. REFUSE review whose target surface exceeds the `--focus` scope when the flag is set.

### Output Surface

The ledger lands at the consuming suite's `_inputs/ux-review-findings.md` per the suite-locality invariant (`rules/context-management.md` §2.6.1); the Handoff Manifest update is suite-internal. Plan-internal files are header-exempt per the `.apothem/**` class at `schemas/header-exceptions.txt`, so `scripts/inject-header.{sh,py}` is NOT invoked. NEVER write outside the suite folder; NEVER modify any artifact in the host repository under review (the review is read-only against the host).

### File-Authoring Contract

The ledger is header-exempt per the `.apothem/**` class; the command never invokes the authorship-header injector on its emissions. Every host-repository quote (a snippet from `scripts/installer/install.sh`, a `--help` transcript, a README header excerpt) is documentary; the host artifact is unmodified.

### Structured Inquiry on Ambiguity

Route through the structured-inquiry channel with the three-segment annotation (`rules/interactive-questions.md` §3) on any uncertainty about review scope, target-harness selection, severity classification, or any branch-point that materially affects findings. Free-form prose questions as primary input are forbidden. NEVER fabricate observations against surfaces not present in the deployed repository.
