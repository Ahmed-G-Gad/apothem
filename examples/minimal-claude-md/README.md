<!-- SPDX-License-Identifier: MIT -->

# minimal-claude-md

The smallest useful project-level `CLAUDE.md`.

> **Scope.** `CLAUDE.md` is the Claude Code harness's project-config format. Each
> harness has its own — `AGENTS.md` for Codex, `GEMINI.md` for Gemini CLI,
> `.cursor/rules/*.mdc` for Cursor, `.github/copilot-instructions.md` for GitHub
> Copilot, and so on. This example demonstrates the Claude Code form specifically; see
> [`site/content/docs/harnesses/`](../../site/content/docs/harnesses/) for each adapter's equivalent.

## What it demonstrates

- The minimum content that gives Claude Code enough context to be helpful in a new project.
- Three sections that consistently pay off: project context (one paragraph), conventions (bullet list), and useful commands (bullet list).

## How to use it

1. Copy `CLAUDE.md` from this folder to the root of your project.
2. Adapt the three sections to your project (replace the conventions, commands, and directory layout with your own).
3. Open Claude Code in the project directory — `CLAUDE.md` is auto-loaded.

## Expected effect

Claude Code starts the session already knowing the project's language version, test command, and directory layout. You skip the warm-up questions and go straight to productive work.

## Next steps

When the project grows, expand `CLAUDE.md` with sections for architecture, contribution flow, and pointers to deeper documentation. Keep it concise — large `CLAUDE.md` files burn the context budget.
