# SPDX-License-Identifier: MIT

"""Module entry point: ``python -m apothem``.

``python -m apothem`` is the canonical invocation surface — apothem ships
no ``[project.scripts]`` console-script shim. The npm shim
(``npx @ahmed-g-gad/apothem``), the Claude Code plugin, and the one-shot
installers all run this same module surface; the installers additionally
place a thin ``apothem`` shell shim on ``PATH`` that forwards here. This
module makes the package directly executable so a fresh checkout, CI
sandbox, or isolated virtualenv resolves the identical entry point with
nothing installed.
"""

from apothem.cli import _configure_stdio, main

if __name__ == "__main__":
    # Force UTF-8 stdio (Windows) before Click parses anything. Click emits
    # ``--help`` / ``--version`` from eager-option handling, and usage errors
    # from argument parsing, *before* the group callback body runs — so a
    # reconfigure inside that callback (apothem/cli/__init__.py) never reaches
    # those surfaces. Doing it here, at the invocation entry and never at
    # import (this block runs only under ``python -m apothem``), makes every
    # Click surface inherit UTF-8 on a legacy-codepage host when stdout is a
    # pipe or redirect. The group-callback call remains as defense-in-depth
    # for a direct ``apothem.cli.main`` import that bypasses this entry.
    _configure_stdio()
    # Pin the completion trigger. Click derives the completion env var from
    # the detected program name, which under ``python -m apothem`` is
    # "python -m apothem" — an unmatchable variable name — so the emitted
    # completion scripts (which all set ``_APOTHEM_COMPLETE``) would never
    # engage. Pinning complete_var keeps shell completion working on every
    # invocation surface without altering usage strings.
    raise SystemExit(main(complete_var="_APOTHEM_COMPLETE"))
