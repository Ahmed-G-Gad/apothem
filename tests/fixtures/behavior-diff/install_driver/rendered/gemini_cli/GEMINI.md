<!-- BEGIN APOTHEM MANAGED BLOCK -->
<!-- SPDX-License-Identifier: MIT -->

# Apothem — Project Instructions

Apothem wrote this block with `apothem install --harness gemini-cli`.
`GEMINI.md` is a shared instruction file: more than one coding tool reads a
project `GEMINI.md`, so this block carries project-wide guidance only and names
no single tool as its reader.

## Apothem reference material

The install placed Apothem's files in this project:

- `.gemini/commands/*.toml` — slash commands converted from Apothem command prompts.
- `.gemini/agents/*.md` — helper definitions normalized from Apothem agents.
- `.gemini/skills/*/SKILL.md` — Apothem skills.
- `.gemini/.apothem/support/rules/` — Apothem rules used as reference material.
- `.gemini/.apothem/support/templates/` — plan, report, and audit templates.
- `.gemini/.apothem/support/hooks/` — hook messages and helper scripts retained as reference material.

The `.gemini/.apothem/support/` tree is Apothem-owned reference material that
this block, the generated commands, and the installed skills point to; no tool
discovers it on its own.

## Engineering disciplines in force

Apothem's foundational mandates apply in every tool that reads this block:

- **Plans-Locality.** Plan-suite artefacts (PROGRESS.md, PLAN-NOTES.md, PHASE.md, REPORT.md) live under `<project>/.apothem/plans/{suite}/` — the sole canonical home; a legacy `<project>/.plans/` tree upgrades via `apothem migrate-workspace`. They never land in a global plans directory or any other global-ecosystem location.
- **Authority hygiene.** Never fabricate identity, scope, security posture, or version-pin data. Surface ambiguity via the canonical structured-inquiry channel; the operator chooses.
- **Definitiveness.** Hedging vocabulary (`maybe`, `might`, `usually`, `generally`, `typically`, `probably`) is eliminated where binding prescription is possible. Pre / post / failure conditions are stated on every contract.
- **Production-ready discipline.** Every change ships in production-ready form — tests, docs, CHANGELOG entry, conformant commit message, CI green — in the same change-set.
- **Plain-language.** Codebase artefacts and user-facing prose read as natural domain language with zero trace of internal planning structure.
- **Observe-decide-act discipline.** Tool use runs as a loop — observe the current state, decide the next move from what was observed, then act — never an edit before a read or a result asserted before a check. Independent reads and searches run together in one pass, not one per turn; the loop closes on a verifiable condition (a gate green, a read confirmed), never a fixed number of tries. Advisory, never an auto-applied behavior.

## Maintaining this block

Text outside the Apothem managed block is operator-owned and survives every re-install. Re-run `apothem install --harness gemini-cli --project <this-project-root>` to refresh the block, the converted `.gemini/` entries, and the reference material; the operation is idempotent. `apothem uninstall --harness gemini-cli --project <this-project-root>` removes the block, backing the prior file up under the Apothem backup root (`~/.apothem/backups/<timestamp>/gemini_cli/`) first, and removes the file only when nothing but the block remained. `apothem verify --harness gemini-cli --project <this-project-root>` checks that the file is present and non-empty.

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
