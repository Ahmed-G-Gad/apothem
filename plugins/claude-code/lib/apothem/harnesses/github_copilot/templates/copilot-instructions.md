<!-- SPDX-License-Identifier: MIT -->

# Apothem — Project Instructions

Apothem wrote this block with `apothem install --harness github-copilot`. It lands at `<project>/.github/copilot-instructions.md`, the repository-wide custom instructions file (https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/add-custom-instructions/add-repository-instructions), which Copilot applies to requests made in this repository, including chat, the cloud agent, and code review. Other coding tools can read the same file, so this block carries project-wide guidance only and names no single tool as its reader. GitHub notes that shorter instruction files are more likely to be processed in full, so the shared-profile section, when the profile sets one, comes first in this block.

The full Apothem rule, skill, command, and agent set lives in the Apothem source under `src/apothem/{rules,skills,commands,agents}/`; consult the matching rule there when generating non-trivial code or prose.

## Engineering disciplines in force

Apothem's foundational mandates apply in every tool that reads this block:

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

## Maintaining this block

Text outside the Apothem managed block is operator-owned and survives every re-install. Re-run `apothem install --harness github-copilot --project <this-project-root>` to refresh the block; the operation is idempotent. `apothem uninstall --harness github-copilot --project <this-project-root>` removes the block, backing the prior file up under the Apothem backup root (`~/.apothem/backups/<timestamp>/github_copilot/`) first, and removes the file only when nothing but the block remained. `apothem verify --harness github-copilot --project <this-project-root>` checks that the file is present and non-empty.
