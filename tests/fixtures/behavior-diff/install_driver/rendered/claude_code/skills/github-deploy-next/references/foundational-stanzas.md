<!-- SPDX-License-Identifier: MIT -->

## Foundational Stanzas

The four standing surfaces every operator inherits per the canonical project voice at `AGENTS.md` plus the active harness mirror.

### Refusal & Escalation

REFUSE any task whose scope exceeds this command's mission (running one subsequent-release cycle plus the deployment report) — name what was refused, name the boundary crossed, and surface an escalation option through the structured-inquiry channel per `rules/interactive-questions.md`. REFUSE the merge or publish step when its per-action confirmation has not cleared. REFUSE a version bump that contradicts the change set unless the `--bump` override is explicit and its rationale is recorded. REFUSE to produce the fresh first release — that is the sibling `github-deploy-fresh.md`, not this command.

### Output Surface

The merged tree is pushed to `origin/main`; the new release is published to the host's release surface under its confirmation gate. The deployment report lands at the consuming suite's `_outputs/github-deploy-next-report.md` per the suite-locality invariant at `rules/canonical-layout.md` §2.2; an optional cycle inventory lands at `_inputs/github-deploy-next-inventory.md`. Plan-internal files are header-exempt per the `.apothem/**` exception class at `src/apothem/schemas/header-exceptions.txt`, so the injector at `scripts/inject-header.py` is NOT invoked on the report. NEVER write the report outside the suite folder, to a global plans directory under any harness's config root, or to any other global-ecosystem location.

### File-Authoring Contract

When the command edits a host source file in place — the manifest version, the CHANGELOG — it preserves the host's ratified idioms per `rules/host-discovery.md` and the canonical SPDX header per the discovered comment family. The deployment report is header-exempt per the `.apothem/**` exception class. The merge-commit and tag-annotation messages name human contributors only per `rules/production-ready-prs.md` §6 — the agent is never attributed. When the report cites a GitHub surface, the citation is documentary (PR number, issue number, tag name, run id).

### Structured Inquiry on Ambiguity

When uncertain about the ready-PR set, the issue set the release addresses, the derived bump, the signing requirement, or whether a pull request is ready to merge, route the resolution through the structured-inquiry channel with the three-segment option annotation per `rules/interactive-questions.md` §3. Free-form prose questions as primary input are forbidden. NEVER fabricate a merge or a release — every merge cites a concrete PR number, every resolved issue cites its issue number, and the merge and publish steps each clear their per-action confirmation first.
