# SPDX-License-Identifier: MIT

"""Uninstall logic for the open-claw harness adapter."""

from __future__ import annotations

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
# effect wrote loses its managed block (rules_file.retire_all); a file that
# cannot be cleaned (behind a link, or a block the strip could not take out)
# leaves the uninstall recorded unfinished, so the install stays active; an
# openclaw.json with comments that still holds Apothem's entries stops the
# uninstall first, since the shared strip cannot rewrite it (the error names
# what to remove by hand).
uninstall = make_native_config_uninstall(
    _HARNESS_NAME,
    materialize_native_config,
    before_fn=rules_file.before_uninstall,
)
