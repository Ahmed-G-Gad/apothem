# SPDX-License-Identifier: MIT

"""Apothem harness adapter protocol — public re-export.

Every concrete adapter must implement :class:`HarnessAdapter`. The protocol
is defined in the foundation layer at :mod:`apothem.lib.harness_protocol` and
re-exported here, so ``from apothem.harnesses import HarnessAdapter`` stays the
stable public import path for adapters, tests, and documentation — the
foundation declares the contract, this consumer package re-exposes it. The
adapters are declared in :mod:`apothem.lib.harness_registry`; the
``pyproject.toml`` entry-point group mirrors that registry exactly.
"""

from __future__ import annotations

from apothem.lib.harness_protocol import HarnessAdapter as HarnessAdapter
