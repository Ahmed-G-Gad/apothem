# SPDX-License-Identifier: MIT

"""Where an install's shared data stores live, as recorded on its ledger record.

Uninstall, rollback and the last-harness guard read the data home an install
recorded, so they reverse the stores where the install actually wrote them.
"""

from __future__ import annotations

import os
from pathlib import Path

from apothem.lib import install_ledger
from apothem.lib.data_home import DataHomeError, resolve_shared_data_home
from apothem.lib.harness_registry import SUPPORTED_PACKAGE_KEYS

from .install_driver_pathsafety import _normalized, _within_allowed_root


def _same_path(left: Path, right: Path) -> bool:
    """Return True when *left* and *right* name the same location."""
    return os.path.normcase(str(_normalized(left))) == os.path.normcase(
        str(_normalized(right))
    )


def _data_home_for(record: install_ledger.LedgerRecord | None, *, root: Path) -> Path:
    """Return the shared working directory the install recorded under *root*.

    An install pass writes its data stores under the home its profile resolved
    (see :func:`apothem.lib.data_home.resolve_install_data_home`) and records that
    home on its ledger record. Uninstall and rollback reverse the stores there,
    so the removal always targets what the install wrote.

    The recorded home is trusted only when it is ``<base>/<name>``, with *base*
    the install root or the user home and *name* a single path component. A
    ledger entry that names anything else falls through to the default. A record
    with no home (written before the field existed) and an absent record resolve
    to the default ``<root>/.apothem``, the location every install used before
    the field was recorded.
    """
    recorded = record.data_home if record is not None else None
    if recorded:
        home = Path(recorded)
        base = home.parent
        if _same_path(base, root) or _same_path(base, Path.home()):
            try:
                return resolve_shared_data_home(
                    base=base, directory_name=home.name
                ).root
            except DataHomeError:
                pass
    return resolve_shared_data_home(base=root).root


def _store_boundary(home: Path, *, allowed_root: Path) -> Path:
    """Return the write boundary the data stores under *home* are removed within.

    The install write root guards the default home, which sits inside it. A
    user-home store sits outside a project-scope write root by design, so the
    boundary widens to the base the home sits beneath. That base is already
    pinned to the install root or the user home by :func:`_data_home_for`.
    """
    if _within_allowed_root(_normalized(home), _normalized(allowed_root)):
        return allowed_root
    return home.parent


def _other_harness_shares_home(*, current_harness: str, shared_home: Path) -> bool:
    """Report whether another installed harness still shares *shared_home*.

    The shared data home is collapsed across harnesses, so removing it on the
    first uninstall would destroy data the remaining harnesses depend on. This
    consults the install ledger across every package key (except
    *current_harness*) and returns ``True`` when any other harness is still
    installed at a root whose data home is *shared_home*.

    A harness is "still installed at a root" when its most recent ledger
    record of any kind for that root is an ``install``. The records are grouped
    by install root before the latest is taken. Grouping by home instead would
    let an ``uninstall`` marker (which carries no home) go unmatched, leaving the
    guard stuck on "retain". The home of each latest install record comes from
    :func:`_data_home_for`, so two roots that share a user-home store are both
    counted. *current_harness* is excluded explicitly because the current
    uninstall's own ``uninstall`` marker is appended only AFTER this guard runs
    (see :func:`run_uninstall`).

    The check is fail-safe: any error reading the ledger raises out to the
    caller, which treats it as "cannot prove last-harness" and retains the
    shared home rather than risk a destructive removal on an uncertain count.
    """
    for package_key in SUPPORTED_PACKAGE_KEYS:
        if package_key == current_harness:
            continue
        # Records are append-ordered, so the last record per root is the latest.
        latest_by_root: dict[str, install_ledger.LedgerRecord] = {}
        for record in install_ledger.read_records(package_key):
            latest_by_root[str(_normalized(Path(record.root)))] = record
        for record in latest_by_root.values():
            if record.kind != "install":
                continue
            root = Path(record.root)
            if _same_path(_data_home_for(record, root=root), shared_home):
                return True
    return False
