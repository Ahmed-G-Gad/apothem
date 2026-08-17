# SPDX-License-Identifier: MIT

"""Uninstall logic for the claude-code harness adapter."""

from __future__ import annotations

from pathlib import Path

from apothem.harnesses._shared import install_driver

_HARNESS_NAME: str = "claude_code"


def uninstall(output_path: Path) -> None:
    """Remove Apothem-managed Claude Code targets surgically.

    ``settings.json`` is an operator-owned ``write_text`` manifest target, so the
    shared driver removes only Apothem's keys and hook handlers (operator-added
    permissions, keys, and non-Apothem hooks survive) and deletes the file only
    when nothing operator-authored remains. The pre-mutation file is copied into
    the Apothem backup root — no whole-file ``.bak`` sibling is left beside it.
    """
    install_driver.run_uninstall(_HARNESS_NAME, harness_root=output_path.parent)
