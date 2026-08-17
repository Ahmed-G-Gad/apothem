# SPDX-License-Identifier: MIT

"""Thin alias shim re-exporting the bundled apothem engine's public API.

Importing ``apothem_lib`` makes the engine's public submodules reachable
under one flat namespace (``apothem_lib.profile``, ``apothem_lib.adapters``,
...) without requiring callers to know the bundled package layout.
"""

from __future__ import annotations

from apothem import __version__
from apothem import harnesses as adapters
from apothem.lib import profile, propagation, reporter

__all__ = [
    "__version__",
    "adapters",
    "profile",
    "propagation",
    "reporter",
]
