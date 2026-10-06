<!-- BEGIN APOTHEM MANAGED BLOCK -->
<!-- SPDX-License-Identifier: MIT -->

# Apothem — Qwen Code Bootstrap

This file is the user-scope context anchor installed by Apothem for Qwen Code.
The native JSON settings file remains `~/.qwen/settings.json`; Apothem writes
that file from the shared profile, registers native hook dispatchers, and
installs reusable Apothem cohorts into Qwen Code's native discovery surfaces
where they exist.

## Apothem Cohorts

Resolve Apothem's native Qwen Code cohorts at:

- `~/.qwen/commands/` contains slash commands converted to Qwen Markdown
  command files.
- `~/.qwen/skills/` contains reusable SKILL.md skill directories.
- `~/.qwen/agents/` contains local subagents adapted to Qwen Code's Markdown
  agent frontmatter.

Apothem's behavioral rules, plan and report templates, and the hook messages
and helper scripts the `settings.json` hook commands run are installed as
support files; the Apothem support files section below names their
directories. Use them as reference material when Qwen Code does not expose a
matching file-based primitive. Do not treat them as a vendor-owned
configuration namespace.

## Apothem support files

Apothem's support root is `<ROOT>/.apothem/support`. Apothem rules, skills, commands, and helper definitions cite support files by repository-style paths such as `rules/<name>.md`, `templates/...`, and `hooks/...`. Resolve each citation against the installed directory for its first segment:

- `rules/<path>` is `<ROOT>/.apothem/support/rules/<path>`
- `templates/<path>` is `<ROOT>/.apothem/support/templates/<path>`
- `hooks/<path>` is `<ROOT>/.apothem/support/hooks/<path>`

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
