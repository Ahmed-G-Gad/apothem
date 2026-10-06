# SPDX-License-Identifier: MIT

"""Rollback of a recorded install pass, and the created-directory record.

An install record lists every target the pass wrote, with the pass outcome and
the backup it captured. Rollback reverses that record target by target, newest
first:

* a target with a backup is restored from it, at the recorded path (a file is
  rewritten, a directory is replaced wholesale, so files the install added
  inside it go too);
* a target the pass created is removed;
* a legacy layout the pass swept away is restored from its backup;
* the data stores the pass seeded are removed when no other harness uses them;
* the directories the pass created are removed once empty, deepest first.

Every file rollback removes or replaces is first copied into the Apothem backup
root, so a rollback is itself reversible.

:func:`capture_missing_dirs` records, before an install writes anything, which
directories on the way to its targets do not exist yet; ``finalize_install``
stores the ones the pass then created on the ledger record.
"""

from __future__ import annotations

import shutil
from collections.abc import Iterable
from dataclasses import replace
from pathlib import Path
from typing import Any

from apothem.harnesses._shared import install_driver
from apothem.lib.data_home import resolve_install_data_home, resolve_shared_data_home
from apothem.lib.install_ledger import LedgerRecord, LedgerTarget
from apothem.lib.propagation import resolve_target

from .install_driver_backup import backup_existing, write_bytes_safely
from .install_driver_lifecycle import _remove_data_home
from .install_driver_pathsafety import (
    _allowed_write_root,
    _normalized,
    _root_for,
    _validate_target_path,
    _within_allowed_root,
)
from .install_driver_treeops import remove_created_dirs
from .install_driver_types import (
    MaterializationResult,
    _handle_rm_error,
    _result,
    backup_session,
)


def _chain(path: Path, boundary: Path) -> list[Path]:
    """Return *path* and its ancestors strictly below *boundary*."""
    chain: list[Path] = []
    probe = _normalized(path)
    floor = _normalized(boundary)
    while probe != floor and _within_allowed_root(probe, floor):
        chain.append(probe)
        if probe.parent == probe:
            break
        probe = probe.parent
    return chain


def capture_missing_dirs(
    harness_name: str,
    *,
    harness_root: Path | None = None,
    project_root: Path | None = None,
    profile: dict[str, Any] | None = None,
    extra: Iterable[Path] = (),
) -> frozenset[Path]:
    """Return the directories an install of *harness_name* may create.

    Call it before the install writes anything. Covers every manifest target and
    the directories on the way to it, the shared data home and its stores, the
    *extra* paths the adapter writes outside the manifest (a native config, a
    profile document) and the allowed-write boundary itself; only paths inside
    that boundary and not present yet are returned. After the pass, the ones that now exist are the
    directories it created.
    """
    boundary = _allowed_write_root(harness_root, project_root)
    root = _root_for(harness_root, project_root)
    candidates: list[Path] = []
    for entry in install_driver.load_rules(harness_name).install:
        target = resolve_target(
            entry.target, harness_root=harness_root, project_root=project_root
        )
        candidates.extend(_chain(target, boundary))
    home = resolve_install_data_home(root, profile=profile)
    for directory in (home.root, home.plans, home.memory, home.contexts, home.learning):
        candidates.extend(_chain(directory, boundary))
    for path in extra:
        candidates.extend(_chain(path, boundary))
    if harness_root is not None:
        candidates.extend(_chain(harness_root, boundary))
    # The boundary itself can be new too (``~/.config`` for opencode, whose
    # harness root is ``~/.config/opencode``).
    candidates.append(_normalized(boundary))
    return frozenset(path for path in candidates if not path.exists())


def _restore_directory(
    target: Path, backup: Path, *, root: Path, harness_name: str, allowed_root: Path
) -> MaterializationResult:
    """Replace *target* with the backed-up directory *backup*."""
    target_error = _validate_target_path(
        target, allowed_root=allowed_root, operation="restore_backup"
    )
    if target_error is not None:
        return target_error
    existed = target.exists()
    current = (
        backup_existing(
            target,
            install_root=root,
            harness_name=harness_name,
            allowed_root=allowed_root,
        )
        if existed
        else None
    )
    if target.is_dir():
        shutil.rmtree(target, onerror=_handle_rm_error)
    elif existed:
        target.unlink()
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(backup, target)
    return _result(
        "updated" if existed else "created",
        "restore_backup",
        target,
        "restored the directory the install replaced",
        source=backup,
        backup_path=current,
    )


def _restore_target(
    recorded: LedgerTarget, *, root: Path, harness_name: str, allowed_root: Path
) -> MaterializationResult:
    """Restore one recorded target from the backup its install captured."""
    target = Path(recorded.path)
    backup = Path(str(recorded.backup_ref))
    if not backup.exists():
        return _result(
            "error",
            "restore_backup",
            target,
            f"the backup this install captured is gone: {backup}",
        )
    if backup.is_dir():
        return _restore_directory(
            target,
            backup,
            root=root,
            harness_name=harness_name,
            allowed_root=allowed_root,
        )
    removed: MaterializationResult | None = None
    if target.is_dir():
        # A directory now stands where the backed-up file was. Its backup rides
        # on the restore result so the rollback record references it.
        removed = _remove_created(
            target, root=root, harness_name=harness_name, allowed_root=allowed_root
        )
    restored = write_bytes_safely(
        target,
        backup.read_bytes(),
        install_root=root,
        harness_name=harness_name,
        operation="restore_backup",
        source=backup,
        allowed_root=allowed_root,
    )
    if removed is not None and removed.backup_path and restored.backup_path is None:
        return replace(restored, backup_path=removed.backup_path)
    return restored


def _remove_created(
    target: Path, *, root: Path, harness_name: str, allowed_root: Path
) -> MaterializationResult | None:
    """Back up and remove a file or directory the install created."""
    if not target.exists() and not target.is_symlink():
        return None
    target_error = _validate_target_path(
        target, allowed_root=allowed_root, operation="remove_created"
    )
    if target_error is not None:
        return target_error
    backup = backup_existing(
        target, install_root=root, harness_name=harness_name, allowed_root=allowed_root
    )
    if target.is_dir() and not target.is_symlink():
        shutil.rmtree(target, onerror=_handle_rm_error)
    else:
        target.unlink()
    return _result(
        "updated",
        "remove_created",
        target,
        "removed what the install created",
        backup_path=backup,
    )


@backup_session()
def rollback_install(
    record: LedgerRecord,
    *,
    harness_name: str,
    harness_root: Path | None = None,
    project_root: Path | None = None,
) -> list[MaterializationResult]:
    """Reverse the install pass *record* describes; return one result per change.

    See the module docstring for the order and rules. A record written before
    per-target outcomes were recorded can only have its backups restored: the
    files it created are not known, so they stay.
    """
    root = _root_for(harness_root, project_root)
    allowed_root = _allowed_write_root(harness_root, project_root)
    results: list[MaterializationResult] = []
    for recorded in reversed(record.targets):
        result: MaterializationResult | None = None
        if recorded.backup_ref:
            result = _restore_target(
                recorded,
                root=root,
                harness_name=harness_name,
                allowed_root=allowed_root,
            )
        elif recorded.outcome == "created":
            result = _remove_created(
                Path(recorded.path),
                root=root,
                harness_name=harness_name,
                allowed_root=allowed_root,
            )
        if result is not None:
            results.append(result)
    created = {Path(path) for path in record.created_dirs}
    stores = resolve_shared_data_home(base=root)
    if created & {stores.memory, stores.contexts, stores.learning}:
        removal = _remove_data_home(harness_name, root=root, allowed_root=allowed_root)
        if removal is not None and removal.outcome != "unchanged":
            results.append(removal)
    results.extend(remove_created_dirs(created, allowed_root=allowed_root))
    return results
