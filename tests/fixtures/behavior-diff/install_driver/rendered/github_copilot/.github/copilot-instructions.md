<!-- BEGIN APOTHEM MANAGED BLOCK -->
<!-- SPDX-License-Identifier: MIT -->

# GitHub Copilot — Apothem Bootstrap

This file is materialised by `apothem install --harness github-copilot --project <path>` and lands at `<project>/.github/copilot-instructions.md`, the GA repo-wide instructions surface per https://docs.github.com/en/copilot/customizing-copilot/adding-custom-instructions-for-github-copilot. The first 4,000 characters are parsed by Copilot's code-review agent; the remaining body is consumed by chat / completions in this project.

## Project Context

GitHub Copilot operates against the apothem governance and convention surface in this project. Apothem propagates a shared engineering discipline across every supported AI harness; inside Copilot, the surface manifests as this repo-wide instructions file.

The full apothem rule / skill / command / agent cohort lives at the apothem source repository under `src/apothem/{rules,skills,commands,agents}/`. This file is the Copilot-facing anchor; consult the apothem rule tree for the per-rule body when generating non-trivial code or prose.

## Engineering disciplines in force

The apothem governance contract binds the following disciplines uniformly across every harness, including GitHub Copilot:

- **Plans-Locality.** Plan-suite artefacts (PROGRESS.md, PLAN-NOTES.md, PHASE.md, REPORT.md) live under `<project>/.apothem/plans/{suite}/` — the sole canonical home; a legacy `<project>/.plans/` tree upgrades via `apothem migrate-workspace`. They never land in a global plans directory or any other global-ecosystem location.
- **Authority hygiene.** Never fabricate identity, scope, security posture, or version-pin data. When generation requires data the operator has not supplied, surface the ambiguity through a question instead of inventing a plausible-looking value.
- **Definitiveness.** Hedging vocabulary (`maybe`, `might`, `usually`, `generally`, `typically`, `probably`) is eliminated where binding prescription is possible. Pre / post / failure conditions are stated on every contract.
- **Production-ready discipline.** Every change ships in production-ready form — tests, docs, CHANGELOG entry, conformant commit message, CI green — in the same change-set.
- **Plain-language.** Codebase artefacts and user-facing prose read as natural domain language with zero trace of internal planning structure. Generated code uses domain-native names (`calculate_portfolio_risk`, not `process_data`).
- **Human-only authorship.** Git commit messages, PR descriptions, branch names, and tag annotations carry human contributors only — never name the underlying language model, the runtime, the IDE extension, or any automated tool as a co-author.
- **Lean-context delegation.** Where the host provides delegated-worker dispatch, broad reads and heavy workloads route to a spawned worker by default so the main working context stays lean. The heavy parallel apparatus stays opt-in; routing delegable work away from the main thread is the standing posture once dispatch is available.
- **Observe-decide-act discipline.** Tool use runs as a loop — observe the current state, decide the next move from what was observed, then act — never an edit before a read or a result asserted before a check. Independent reads and searches run together in one pass, not one per turn; the loop closes on a verifiable condition (a gate green, a read confirmed), never a fixed number of tries. Advisory, never an auto-applied behavior.
- **Source accessibility.** When the authoritative source for a claim, convention, or version pin is closed, paywalled, login-gated, or otherwise unreachable, ask the operator for it in full rather than substituting a lower-trust open page. Trust outranks reachability.

## Modal hierarchy

When the operator's request conflicts with an apothem rule, the rule wins; surface the conflict and propose the rule-conformant alternative. When two apothem surfaces conflict, the most specific path-filtered rule wins over the always-on rule. Always-on rules are listed at `<apothem-src>/src/apothem/rules/` with `alwaysApply: true` in their frontmatter.

## Refreshing the file

Re-run `apothem install --harness github-copilot --project <this-project-root>` to refresh the Apothem managed block in this file with the latest template. The install folds Apothem's content into a sentinel-delimited managed block and preserves any operator prose outside the sentinels verbatim; it is idempotent. The companion `apothem uninstall --harness github-copilot --project <this-project-root>` strips the managed block (leaving operator prose in place; the file is removed only when nothing but the block remained), backing the prior file up under the Apothem backup root (`~/.apothem/backups/<timestamp>/github_copilot/`) first. `apothem verify --harness github-copilot --project <this-project-root>` checks the file is present and non-empty.

# Apothem Shared Profile

Managed by Apothem from the shared profile. Edits inside the sentinels are overwritten on the next `apothem install`; change the shared profile instead.

## Operator

- **Name:** Golden-Corpus-Operator
- **Role:** release engineer
- **Email:** golden@corpus.invalid
- **Website:** https://golden.corpus.invalid
- **GitHub:** @golden-corpus-operator

## Preferences

- **Primary language:** python
- **Response style:** concise
- **Governance seriousness:** PUBLIC_LAUNCH

## Custom Rules

- golden-corpus-validate-input-before-write

## Opted-in Behaviors

- Sprint apparatus for non-trivial multi-step work

## MCP Servers

Configured MCP servers (materialized into the harnesses with a native MCP config surface; named here as reference for the rest):
- golden-corpus-srv
<!-- END APOTHEM MANAGED BLOCK -->
