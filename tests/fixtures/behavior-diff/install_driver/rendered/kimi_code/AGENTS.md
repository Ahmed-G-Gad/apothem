<!-- BEGIN APOTHEM MANAGED BLOCK -->
<!-- SPDX-License-Identifier: MIT -->

# Apothem — Project Instructions

Apothem wrote this block with `apothem install --harness kimi-code`.
`AGENTS.md` is a shared instruction file: any coding tool that follows the
AGENTS.md convention reads it, so this block carries project-wide guidance
only and names no single tool as its reader.

## Apothem reference material

The install placed Apothem's reference material in this project:

- `.kimi-code/.apothem/support/rules/` — Apothem rules.
- `.kimi-code/.apothem/support/skills/` — Apothem skills, plus command prompts
  wrapped as skills.
- `.kimi-code/.apothem/support/agents/` — Apothem helper definitions.
- `.kimi-code/.apothem/support/templates/` — plan, report, and audit
  templates.

Read the matching file there when a task calls for one of those rules, skills,
or templates.

## Maintaining this block

Text outside the Apothem managed block is operator-owned and survives every
re-install. Re-run `apothem install --harness kimi-code --project
<this-project-root>` to refresh the block and the reference material; the
operation is idempotent. `apothem uninstall --harness kimi-code --project
<this-project-root>` removes the block and leaves the rest of this file in
place.

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
