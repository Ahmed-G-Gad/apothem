# SPDX-License-Identifier: MIT

"""No-write previews for the writes an install makes outside the manifest list.

``run_install(dry_run=True)`` classifies every manifest entry. An install also
writes the shared data stores, and the adapters write a native config, an
instruction anchor (Claude Code ``CLAUDE.md``) or a profile document; the
helpers here classify those the same way — ``created`` / ``updated`` /
``unchanged`` against the current file — so ``install --dry-run`` and ``diff``
list every path the real install then writes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final

from apothem.lib.data_home import resolve_install_data_home

from .install_driver_types import (
    MaterializationOutcome,
    MaterializationResult,
    _result,
    _with_detail,
)

#: The uniform message every dry-run result carries. A dry run writes nothing,
#: so the message states only that; the prospective ``outcome`` word
#: (``created`` / ``updated`` / ``unchanged``) carries the would-this-change
#: distinction, exactly as the stale-sweep dry-run results already do.
DRY_RUN_MESSAGE: Final[str] = "dry run: no filesystem changes made"


def prospective_result(
    target: Path,
    *,
    before: str | None,
    after: str,
    operation: str,
    detail: dict[str, str] | None = None,
) -> MaterializationResult:
    """Return the dry-run result of writing *after* over *before* at *target*.

    *before* is the current text (``None`` when the file does not exist).
    """
    outcome: MaterializationOutcome
    if before is None:
        outcome = "created"
    elif before == after:
        outcome = "unchanged"
    else:
        outcome = "updated"
    return _with_detail(
        _result(outcome, operation, target, DRY_RUN_MESSAGE), dict(detail or {})
    )


def preview_data_surfaces(
    root: Path, *, profile: dict[str, Any] | None
) -> list[MaterializationResult]:
    """Return the dry-run results for the shared data stores an install seeds.

    Mirrors ``_materialize_data_surfaces``: every store reports ``created`` when
    the shared home does not exist yet and ``unchanged`` when it does (seeding
    never overwrites a store). The store directories stand for the files the
    install writes inside them.
    """
    home = resolve_install_data_home(root, profile=profile)
    outcome: MaterializationOutcome = "unchanged" if home.root.exists() else "created"
    return [
        _result(outcome, "data_surface", store, DRY_RUN_MESSAGE)
        for store in (home.memory, home.contexts, home.learning)
    ]
