<!-- BEGIN APOTHEM MANAGED BLOCK -->
<!-- SPDX-License-Identifier: MIT -->

# Apothem — Kimi Code Bootstrap

This file is the vendor-canonical agent-instructions surface for the Kimi
Code CLI (Moonshot): the project-root `AGENTS.md` per the vendor
configuration docs
(https://moonshotai.github.io/kimi-cli/en/configuration/config-files.html).
It follows the universal AGENTS.md convention adopted across coding-agent
ecosystems. Apothem materialises its governance surface into this file as a
sentinel-delimited managed block and keeps non-native Markdown cohorts under
an Apothem-owned support tree at `<project>/.kimi-code/.apothem/support/`.

## Apothem Conventions

The Apothem-managed cohorts are installed as follows:

- `<project>/AGENTS.md` — this Kimi Code instruction anchor, carrying the
  Apothem governance surface as a managed block. Operator prose outside the
  Apothem sentinels is preserved on every re-install.
- `<project>/.kimi-code/.apothem/support/rules/` — Apothem Markdown rules used as
  reference material by this file and the installed cohorts.
- `<project>/.kimi-code/.apothem/support/skills/` — Apothem skills plus command prompts
  wrapped as skills.
- `<project>/.kimi-code/.apothem/support/agents/` — Apothem sub-agent definitions.
- `<project>/.kimi-code/.apothem/support/templates/` — plan, report, and audit
  templates.

## Runtime Configuration

Kimi Code CLI's runtime configuration lives under `<project>/.kimi-code/`.
Apothem does not overwrite operator-owned configuration there; it installs
instructions and support content through the vendor-native paths above. The
`<project>/.kimi-code/mcp.json` MCP surface is operator-owned — Apothem names
it but authors no entries. The Kimi Code model family is selected through the
operator's own configuration; Apothem presets no model or effort.

## Operator Surface

Operators may extend project-specific instructions in this `AGENTS.md` outside
the Apothem managed block. Re-run `apothem install --harness kimi-code
--project <this-project-root>` to refresh this instruction anchor and the
installed support cohorts. The operation is idempotent.

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
