# SPDX-License-Identifier: MIT

"""Cohort-wide guard for the audit content-root convention.

The seven inventory-record-resolving scanners and the capability-index
renderer all import ``CONTENT_ROOT`` from the shared ``_scan_lib`` module
(loaded via each module's ``sys.path`` shim) — the default ``--root`` for the
scanners and the anchor the renderer walks. Because they import from the one
shared module, every consumer exposes the IDENTICAL ``CONTENT_ROOT`` object.

This pins the single-source-of-truth: a regression that re-introduces a
per-module local definition (the prior ``render_capability_index`` shape) or
shadows the import would expose a DISTINCT object and fail the identity check.

(Note: the consumers load ``_scan_lib`` as a bare top-level module via their
``sys.path`` shim, which is a separate module object from the package-qualified
``apothem.audit._scan_lib``. The identity is therefore asserted consumer-to-
consumer, not against the package-qualified import.)
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

# The seven inventory-record-resolving scanners (whose --root defaults to
# CONTENT_ROOT) plus the capability-index renderer (whose former local
# definition was consolidated onto the shared _scan_lib constant).
_CONTENT_ROOT_CONSUMERS = [
    "apothem.audit.check_links",
    "apothem.audit.scan_frontmatter",
    "apothem.audit.scan_drift_features",
    "apothem.audit.scan_plans_discipline",
    "apothem.audit.scan_secrets_pii",
    "apothem.audit.scan_stale_tokens",
    "apothem.audit.scan_plan_leakage",
    "apothem.audit.render_capability_index",
]


def _reference_content_root() -> Path:
    return importlib.import_module(_CONTENT_ROOT_CONSUMERS[0]).CONTENT_ROOT


@pytest.mark.parametrize("module_name", _CONTENT_ROOT_CONSUMERS)
def test_consumer_shares_the_cohort_content_root(module_name: str) -> None:
    module = importlib.import_module(module_name)
    assert module.CONTENT_ROOT is _reference_content_root()


def test_cohort_content_root_resolves_to_the_apothem_package() -> None:
    root = _reference_content_root()
    assert root.name == "apothem"
    assert (root / "rules").is_dir()
    assert (root / "audit").is_dir()
