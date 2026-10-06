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
