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
