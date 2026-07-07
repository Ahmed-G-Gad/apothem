<!-- BEGIN APOTHEM MANAGED BLOCK -->
<!-- SPDX-License-Identifier: MIT -->

# Apothem — Codex Bootstrap

This file is the vendor-canonical agent-instructions surface for the
OpenAI Codex CLI (`$CODEX_HOME/AGENTS.md`, default `~/.codex/AGENTS.md`).
It follows the universal AGENTS.md convention adopted across coding-agent
ecosystems. Apothem's governance surface is split between Codex-native
discovery paths and an Apothem-owned support tree for content that is not a
Codex-native primitive.

## Apothem Conventions

The Apothem-managed cohorts are installed as follows:

- `$CODEX_HOME/agents/*.toml` — Codex custom agents converted from Apothem
  Markdown agents.
- `$CODEX_HOME/hooks.json` and `$CODEX_HOME/hooks/` — Codex lifecycle hook
  configuration plus Apothem hook helpers.
- `~/.agents/skills/*/SKILL.md` — Apothem skills plus command prompts wrapped
  as Codex skills.
- `~/.config/apothem/rules/` — Apothem Markdown rules used as reference
  material by this file and the installed skills.
- `~/.config/apothem/templates/` — plan, report, and audit templates.

Do not place Apothem Markdown rules under `$CODEX_HOME/rules/`. Codex
reserves that directory for `.rules` execution-policy files, which use a
different format and purpose.

## Runtime Configuration

Codex CLI's runtime configuration lives at `$CODEX_HOME/config.toml`. Apothem
does not overwrite that operator-owned file; it installs instructions, hooks,
agents, skills, and support content through the vendor-native paths above.

## Operator Surface

Operators may extend project-specific instructions in project-local
`AGENTS.md` files. Re-run `apothem install --harness codex` to refresh this
user-scope bootstrap, converted agents, skills, and support cohorts.

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
