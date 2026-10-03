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
- `$CODEX_HOME/hooks.json` — Codex lifecycle hook configuration; the hook
  helpers it runs are listed under Apothem support files below.
- `~/.agents/skills/*/SKILL.md` — Apothem skills plus command prompts wrapped
  as Codex skills.

Apothem's Markdown rules and templates are reference material for this file
and the installed skills; the Apothem support files section below names the
directories they were installed to.

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
