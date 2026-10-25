---
alwaysApply: true
description: "Apothem governance and convention surface for the CodeBuddy harness — applied every session to honour project-wide engineering discipline."
---
<!-- BEGIN APOTHEM MANAGED BLOCK -->
<!-- SPDX-License-Identifier: MIT -->

# Apothem — CodeBuddy Bootstrap

This file is materialised by `apothem install --harness codebuddy --project <path>` and lands at `<project>/.codebuddy/rules/apothem-rules.md`, the current CodeBuddy project rules surface per <https://www.codebuddy.ai/docs/ide/Rules>. It is a dedicated apothem rules file: it never clobbers operator-authored rules in the same directory.

## What Apothem governs in this project

Apothem propagates a shared governance and convention surface across every supported AI harness in this project's host environment. Inside CodeBuddy, the surface manifests as this always-applied rule file:

- **Rules** — engineering rules applied on every interaction (`alwaysApply: true`). This install writes this one rules file in the project; the disciplines below are the rule text in force here, and the full rule and template files are installed in `~/.config/apothem/` (the Apothem support files section below names them).
- **Skills and commands** — Apothem's skills and slash-style command prompts are installed as skills in `~/.codebuddy/skills/`, in your user home. That folder is one copy for every project and for every tool that reads it, so it is not part of this project. Open the `SKILL.md` of a skill there when a task calls for it.
- **Agents and hooks** — Apothem's sub-agent definitions and hook helpers are not installed by the CodeBuddy adapter.
- **Memory** — CodeBuddy's project memory file (`CODEBUDDY.md`) is operator-owned, not apothem-managed.
- **Settings** — CodeBuddy's MCP servers (`.mcp.json` at the project root) and settings (`.codebuddy/settings.json`) are operator-owned, not apothem-managed.

## Engineering disciplines in force

Apothem's foundational mandates apply uniformly across every harness, including CodeBuddy:

- **Plans-Locality.** Plan-suite artefacts (PROGRESS.md, PLAN-NOTES.md, PHASE.md, REPORT.md) live under `<project>/.apothem/plans/{suite}/` — the sole canonical home; a legacy `<project>/.plans/` tree upgrades via `apothem migrate-workspace`. They never land in a global plans directory or any other global-ecosystem location.
- **Authority hygiene.** Never fabricate identity, scope, security posture, or version-pin data. Surface ambiguity through a question instead of inventing a plausible-looking value.
- **Definitiveness.** Hedging vocabulary (`maybe`, `might`, `usually`, `generally`, `typically`, `probably`) is eliminated where binding prescription is possible. Pre / post / failure conditions are stated on every contract.
- **Production-ready discipline.** Every change ships in production-ready form — tests, docs, CHANGELOG entry, conformant commit message, CI green — in the same change-set.
- **Plain-language.** Codebase artefacts and user-facing prose read as natural domain language with zero trace of internal planning structure.
- **Human-only authorship.** Git commit messages, PR descriptions, branch names, and tag annotations carry human contributors only — never the underlying language model, runtime, IDE extension, or any automated tool as a co-author.
- **Lean-context delegation.** Where the host provides delegated-worker dispatch, broad reads and heavy workloads route to a spawned worker by default so the main working context stays lean. The heavy parallel apparatus stays opt-in; routing delegable work away from the main thread is the standing posture once dispatch is available.
- **Observe-decide-act discipline.** Tool use runs as a loop — observe the current state, decide the next move from what was observed, then act — never an edit before a read or a result asserted before a check. Independent reads and searches run together in one pass, not one per turn; the loop closes on a verifiable condition (a gate green, a read confirmed), never a fixed number of tries. Advisory, never an auto-applied behavior.
- **Source accessibility.** When the authoritative source for a claim, convention, or version pin is closed, paywalled, login-gated, or otherwise unreachable, ask the operator for it in full rather than substituting a lower-trust open page. Trust outranks reachability.

## Refreshing the file

Re-run `apothem install --harness codebuddy --project <this-project-root>` to refresh the Apothem managed block in this file with the latest template. The install folds Apothem's content into a sentinel-delimited managed block and preserves any operator prose outside the sentinels verbatim; it is idempotent. `apothem uninstall --harness codebuddy --project <this-project-root>` strips the managed block (leaving operator prose in place; the file is removed only when nothing but the block remained), backing the prior file up under the Apothem backup root (`~/.apothem/backups/<timestamp>/codebuddy/`) first. `apothem verify --harness codebuddy --project <this-project-root>` checks the file is present and non-empty, and that every Apothem skill folder is in place. The skills and support folders in your user home are shared by every Apothem install that uses them, so `apothem uninstall` removes them only when no other install still lists them.

## Apothem support files

Apothem's support root is `~/.config/apothem`. Apothem rules, skills, commands, and helper definitions cite support files by repository-style paths such as `rules/<name>.md`, and `templates/...`. Resolve each citation against the installed directory for its first segment:

- `rules/<path>` is `~/.config/apothem/rules/<path>`
- `templates/<path>` is `~/.config/apothem/templates/<path>`

Start with the rule index at `~/.config/apothem/rules/apothem-rule-index.md`: it names every rule and when to read it.

A cited path whose first segment is not listed here is not installed.

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
