<!-- SPDX-License-Identifier: MIT -->

<!-- REUSE-IgnoreStart -->
# MCP — Templates Only

> **Role.** Scaffold for Model Context Protocol (MCP) server configurations an operator registers through a coding tool's native MCP surface. This directory holds **templates only** — no live secrets, no user-specific endpoints. Operator-specific wiring lives at `*.local.json` paths (gitignored) the operator authors from these templates. MCP servers are operator-owned; Apothem syncs the inventory from the shared profile but authors no entries.

## Files

| File | Purpose | Header |
|------|---------|--------|
| `README.md` | This document — operator instructions for populating local MCP configs from the templates. | Carries the canonical `SPDX-License-Identifier: MIT` header line. |
| `NOTICE.md` | Records the authorship and license provenance for the `*.json` templates and the JSON header-exemption rationale. | Carries the canonical `SPDX-License-Identifier: MIT` header line. |
| `example-server.json` | Structural template for one MCP server entry. Carries no live URLs, no tokens, no operator-specific fields. | Header-exempt per `src/apothem/schemas/header-exceptions.txt` (JSON has no comment syntax; the sibling `NOTICE.md` carries the provenance for the directory class). |

## Populating a Local Config

1. Copy `example-server.json` to a sibling `*.local.json` (e.g., `mcp/my-server.local.json`). The `.local.json` suffix matches the gitignore pattern `*.local.json` so the file never lands in version control.
2. Edit the local copy to fill in the operator-specific fields named in the template:
   - `command` — absolute path or PATH-resolvable executable that runs the server.
   - `args` — array of CLI arguments passed to the command.
   - `env` — environment variables the server requires (the template names the keys; the operator supplies the values).
3. Register the server through your tool's native MCP mechanism. On the Claude Code adapter (one of many), that is `claude mcp add` writing to `~/.claude.json` (user or local scope) or a project-level `.mcp.json`; other tools project into their own native surfaces. Apothem honors the operator-owned surface and authors no entries.

## Adding a New Server Template

When a new MCP server class is introduced:

1. Author a new `mcp/<server-class>.json` template alongside the existing one. The template carries placeholder values (`"<your-token>"`, `"<your-endpoint>"`) so a copy-and-fill produces a runnable config.
2. Update this README's Files table with the new template.
3. Update `NOTICE.md`'s server-class enumeration if the new template introduces a class the rationale does not cover.

<!-- REUSE-IgnoreEnd -->

## Bindings

- **Drives →** Every operator's MCP-server-onboarding workflow within projects rooted at this ecosystem; the `mcp/*.local.json` files the operator authors from these templates.
- **Satisfies →** The operator-owned MCP model documented at `site/content/docs/reference/mcp.mdx` (Apothem syncs the inventory but authors no entries).
- **Established by ↑** `site/content/docs/reference/mcp.mdx` (the canonical MCP reference).
- **Cross-bound with ↔** `mcp/NOTICE.md` (authorship provenance + JSON header-exemption rationale); `.gitignore` (`*.local.json` pattern excluding operator-specific configs).
