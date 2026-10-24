<!-- SPDX-License-Identifier: MIT -->

## Foundational Stanzas

The four standing surfaces every operator inherits per the canonical project voice at `AGENTS.md` plus the active harness mirror.

### Refusal & Escalation

REFUSE any task whose scope exceeds this command's mission (producing a single fresh first-version GitHub deployment plus the deployment report) — name what was refused, name the boundary crossed, and surface an escalation option through the structured-inquiry channel per `rules/interactive-questions.md`. REFUSE any irreversible GitHub-side action that has not cleared its per-action confirmation. REFUSE the repository delete-and-recreate unless its explicit `MAY`-gated confirmation is selected AND the current repository metadata is captured for full-fidelity recreation. REFUSE to re-implement the agnostic freshening core — it is inherited from `/freshify`, never duplicated.

### Output Surface

The deployed tree is modified in place by default and pushed as the single `release: <repo-name> v0.1.0` commit to `origin/main`. The deployment report lands at the consuming suite's `_outputs/github-deploy-fresh-report.md` per the suite-locality invariant at `rules/canonical-layout.md` §2.2; an optional trace inventory lands at `_inputs/github-deploy-fresh-inventory.md`. Plan-internal files are header-exempt per the `.apothem/**` exception class at `src/apothem/schemas/header-exceptions.txt`, so the injector at `scripts/inject-header.py` is NOT invoked on the report. NEVER write the report outside the suite folder, to a global plans directory under any harness's config root, or to any other global-ecosystem location.

### File-Authoring Contract

When the command edits a host source file in place, it preserves the host's ratified idioms per `rules/host-discovery.md` and the canonical SPDX header per the discovered comment family. The deployment report is header-exempt per the `.apothem/**` exception class. The `release: <repo-name> v0.1.0` commit message names human contributors only per `rules/production-ready-prs.md` §6 — the agent is never attributed. Every removal cites its GitHub surface documentarily (run id, release tag, branch name, `file:line`) and is named before it is deleted.

### Structured Inquiry on Ambiguity

When uncertain about the `<repo-name>` token, the sub-package set, the OpenSSF Scorecard applicability, the registry-coordinate set, the signing requirement, whether a GitHub artifact is a residual trace or a current-product surface, or any destructive-step target, route the resolution through the structured-inquiry channel with the three-segment option annotation per `rules/interactive-questions.md` §3. Free-form prose questions as primary input are forbidden. NEVER fabricate a removal — every removal cites a concrete GitHub identifier (run id, release tag, branch name, package version) plus the freshening rationale, and every irreversible removal clears its per-action confirmation first.
