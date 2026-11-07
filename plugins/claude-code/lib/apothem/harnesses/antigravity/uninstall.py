# SPDX-License-Identifier: MIT

"""Uninstall logic for the antigravity harness adapter."""

from __future__ import annotations

from pathlib import Path

from apothem.harnesses._shared import install_driver

_HARNESS_NAME: str = "antigravity"


@install_driver.backup_session()
def uninstall(output_path: Path) -> None:
    """Remove the Apothem install from the Antigravity harness root.

    The ``GEMINI.md`` anchor is a ``sentinel_merge`` manifest target, so the
    shared driver strips only Apothem's managed block (operator prose survives)
    and backs the file up under the Apothem backup root; no whole-file ``.bak``
    sibling is left beside the operator's file. The Apothem plugin under
    ``~/.gemini/config/plugins/apothem/`` is removed.

    The shared uninstall reverses only the layout the current manifest declares.
    An install from before the plugin moved to ``~/.gemini/config/plugins/``
    holds it at ``~/.gemini/antigravity-cli/plugins/apothem/``, a path no install
    entry targets any longer. The manifest's ``stale-sweep`` list names it, so it
    is swept first (backed up, then removed whole) and its backup is passed on as
    ``prior_results``: the uninstall record then references it and retention
    keeps it. The same sweep removes a retired ``~/.antigravity/profile.yaml``,
    also after a backup. ``~/.gemini/antigravity/`` is never swept: Antigravity
    keeps its MCP OAuth tokens and session transcripts there.
    """
    harness_root = output_path.parent
    legacy = install_driver.sweep_stale(
        install_driver.load_rules(_HARNESS_NAME).stale_sweep,
        harness_root,
        harness_name=_HARNESS_NAME,
        allowed_root=install_driver._allowed_write_root(harness_root, None),
    )
    install_driver.run_uninstall(
        _HARNESS_NAME, harness_root=harness_root, prior_results=tuple(legacy)
    )
