<!-- SPDX-License-Identifier: MIT -->

# Apothem for VS Code

Install and manage the **Apothem** shared profile for **VS Code** and
**GitHub Copilot** directly from your
editor. One profile, materialized into the editor's native configuration surface
(`.github/copilot-instructions.md` and the rest of the governed corpus), kept in
lock-step with the Apothem engine.

This extension is a thin convenience layer: every command runs the Apothem
engine itself, so it always reflects your installed Apothem version and never
duplicates engine logic.

## Commands

Open the Command Palette (`Ctrl+Shift+P` / `Cmd+Shift+P`) and run:

| Command | Action |
|---|---|
| **Apothem: Install in this workspace** | Materialize the shared profile into this workspace |
| **Apothem: Verify** | Check the installed configuration against the profile |
| **Apothem: Update** | Refresh the workspace to the current profile |
| **Apothem: Uninstall** | Remove the materialized configuration |
| **Apothem: Doctor** | Diagnose the environment and report a next step |

Install, Verify, Update and Uninstall ask which harness to act on. The list
starts with this editor's own harness (GitHub Copilot in VS Code, Cursor, or
Windsurf); **Other harness…** takes any harness name, and **all** acts on every
supported harness, including files in your home directory. Each command runs
as a task in the terminal panel, with the workspace folder as `--project`.

## Requirements

The extension drives the Apothem engine through the npm shim by default
(`npx @ahmed-g-gad/apothem@1.1.0`), which needs Node.js on the `PATH`. To run from a
local checkout instead, set **`apothem.runner`** in your user Settings (for
example, `python -m apothem`). The setting is machine-scoped: a workspace's
`.vscode/settings.json` cannot change it. The runner is split on spaces into a
program and its arguments, and every argument is passed quoted, never as shell
text.

The extension is disabled in Restricted Mode and runs only in a trusted
workspace.

## Links

- Documentation: <https://apothem.ahmedgad.com/>
- Source and issues: <https://github.com/ahmed-g-gad/apothem>

Distributed as the signed `apothem.vsix` that the release workflow attaches to
each new GitHub Release (or built from a checkout with the vsce locked in
`.github/vsce/`, which needs Node.js 22 or later: run
`npm ci --prefix .github/vsce --ignore-scripts` at the repository root, then
`../.github/vsce/node_modules/.bin/vsce package --no-dependencies` in this
folder) — install with
`code --install-extension apothem.vsix`, or the editor's *Install from VSIX…*
command. It installs across the VS Code family and manages the
GitHub Copilot instruction surface. A Marketplace listing is not yet published:
the `apothem` name is held by another publisher, so the extension identifier is
still unresolved.
