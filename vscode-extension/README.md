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

## Requirements

The extension drives the Apothem engine through the npm shim by default
(`npx @ahmed-g-gad/apothem`), which needs Node.js on the `PATH`. To run from a
local checkout instead, set **`apothem.runner`** in Settings (for example,
`python -m apothem`).

## Links

- Documentation: <https://apothem.ahmedgad.com/>
- Source and issues: <https://github.com/ahmed-g-gad/apothem>

Distributed as the signed `apothem.vsix` attached to each GitHub Release —
install with `code --install-extension apothem.vsix`, or the editor's *Install
from VSIX…* command. It installs across the VS Code family and manages the
GitHub Copilot instruction surface. A Marketplace listing is not yet published:
the `apothem` name is held by another publisher, so the extension identifier is
still unresolved.
