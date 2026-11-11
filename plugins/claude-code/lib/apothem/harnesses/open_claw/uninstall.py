# SPDX-License-Identifier: MIT

"""Uninstall logic for the open-claw harness adapter."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from apothem.harnesses._shared.install_driver import (
    MaterializationResult,
    MaterializationRun,
)
from apothem.harnesses._shared.wrapper_factories import make_native_config_uninstall
from apothem.harnesses.open_claw import rules_file
from apothem.harnesses.open_claw.materializer import materialize_native_config

_HARNESS_NAME: str = "open_claw"

# The native ``openclaw.json`` is rendered by the materializer rather than the
# manifest, so it is cleaned surgically: only the entries the install ledger
# records as Apothem's (the skills directory it added to ``skills.load.extraDirs``
# and any ``skills`` / ``load`` / ``extraDirs`` container it created) are
# stripped from the parsed operator JSON — operator-added keys and the
# operator's own ``extraDirs`` entries survive — and the file is deleted only
# when Apothem created it and nothing operator-authored remains. The
# pre-mutation file is copied into the Apothem backup root; no whole-file
# ``.bak`` sibling is left beside the operator's file. The manifest support
# subtree is then cleaned child-by-child by the shared driver. No profile-derived
# namespace is owned wholesale here, so ``apothem_keys`` stays at the driver
# default (empty). Before that, every workspace rules file an install still in
# effect wrote loses its managed block (rules_file.retire_all); a file reached
# through a link leaves the uninstall recorded unfinished, so the install stays
# active, and a block the strip could not take out stops the uninstall before
# openclaw.json changes; an openclaw.json with comments that still holds
# Apothem's entries stops the uninstall first, since the shared strip cannot
# rewrite it (the error names what to remove by hand).
_remove = make_native_config_uninstall(
    _HARNESS_NAME,
    materialize_native_config,
    before_fn=rules_file.before_uninstall,
)


def uninstall(output_path: Path) -> MaterializationRun:
    """Remove Apothem's open-claw install; say which leftover files no longer load.

    A rules file reached through a link stays, and the uninstall is reported
    unfinished. After the shared steps have changed *output_path*, each such
    file OpenClaw would no longer load (see :func:`rules_file.still_loaded`)
    gets ``loaded: "0"`` on its warning, and the report drops "still loads".
    While openclaw.json exists but cannot be read as JSON5, nothing shows what
    OpenClaw loads, so the warnings keep the default wording.
    """
    run = _remove(output_path)
    config = rules_file.read_config(output_path)
    if config is None and output_path.exists():
        return run
    home = output_path.parent.parent
    return replace(
        run, results=tuple(_not_loaded(result, config, home) for result in run.results)
    )


def _not_loaded(
    result: MaterializationResult, config: object, home: Path
) -> MaterializationResult:
    """Mark a blocked rules-file warning whose file OpenClaw no longer loads."""
    if result.operation != rules_file.RETIRE or not result.detail.get("blocked"):
        return result
    if config is not None and rules_file.still_loaded(config, Path(result.path), home):
        return result
    return replace(result, detail={**result.detail, "loaded": "0"})
