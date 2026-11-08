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
from apothem.lib.data_home import DataHome, resolve_install_data_home
from apothem.lib.install_ledger import LedgerRecord, LedgerTarget
from apothem.lib.propagation import resolve_target

from .install_driver_backup import backup_existing, write_bytes_safely
from .install_driver_datahome import _data_home_for, _remove_data_home
from .install_driver_pathsafety import (
    _allowed_write_root,
    _is_lexically_within,
    _is_link,
    _normalized,
    _remove_tree_keeping_links,
    _root_for,
    _skip_links_into,
    _validate_target_path,
    _walk_without_links,
    _within_allowed_root,
    kept_links_detail,
)
from .install_driver_shared import UserLevelGate, entry_write_root, locked_for_harness
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
    directories it created. A user-level target is bounded by the user home, so
    the directories on the way to it (``~/.agents``) are covered too.
    """
    boundary = _allowed_write_root(harness_root, project_root)
    root = _root_for(harness_root, project_root)
    candidates: list[Path] = []
    for entry in install_driver.load_rules(harness_name).install:
        target = resolve_target(
            entry.target, harness_root=harness_root, project_root=project_root
        )
        candidates.extend(
            _chain(target, entry_write_root(entry, harness_root, project_root))
        )
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
    """Replace *target* with the backed-up directory *backup*.

    A link at *target* (a junction on Windows) is left in place: removing it
    fails, and copying the backup over it would write through it. Below
    *target*, the backup is copied in around any link, which stays as it is.
    """
    if _is_link(target):
        return _result(
            "unchanged",
            "restore_backup",
            target,
            f"{target} is a link (a symbolic link or a junction), so it was left "
            "in place and the backup was not restored there",
            source=backup,
        )
    target_error = _validate_target_path(
        target, allowed_root=allowed_root, operation="restore_backup"
    )
    if target_error is not None:
        return target_error
    links = _walk_without_links(target).links if target.is_dir() else []
    if links:
        return _restore_around_links(
            target, backup, links, root, harness_name, allowed_root
        )
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


def _restore_around_links(
    target: Path,
    backup: Path,
    links: list[Path],
    root: Path,
    harness_name: str,
    allowed_root: Path,
) -> MaterializationResult:
    """Copy *backup* into *target* without removing, entering or replacing a link.

    The copy merges: files in *target* that the backup does not hold stay.
    """
    current = backup_existing(
        target, install_root=root, harness_name=harness_name, allowed_root=allowed_root
    )
    shutil.copytree(
        backup,
        target,
        dirs_exist_ok=True,
        ignore=_skip_links_into(backup, target, links),
    )
    return _result(
        "updated",
        "restore_backup",
        target,
        f"copied the backup into the directory, around {len(links)} link(s) "
        "left in place; files the backup does not hold were kept",
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
    kept: list[Path] = []
    if target.is_dir() and not _is_link(target):
        kept = _remove_tree_keeping_links(target)
    else:
        target.unlink()
    return _result(
        "updated",
        "remove_created",
        target,
        "removed what the install created"
        + (f"; left {len(kept)} path(s) in it in place" if kept else ""),
        backup_path=backup,
        detail=kept_links_detail(kept),
    )


def _still_swept(recorded_path: str, harness_name: str, *, root: Path) -> bool:
    """Return True when a stale-sweep entry of *harness_name* still covers the path.

    An install record lists the stale paths its pass swept. A release can drop
    an entry because the path stopped being Apothem's: Antigravity keeps its own
    data in ``~/.gemini/antigravity/``, which an early release listed. Restoring
    such a record's backup would replace the live folder with a stale copy.
    """
    rules = install_driver.load_rules(harness_name)
    return any(
        _is_lexically_within(Path(recorded_path), root / legacy)
        for legacy in rules.stale_sweep
    )


#: Detail key on a ``restore_backup`` row that restored nothing because the
#: path is in the way or its backup is gone; the CLI reports it as a warning.
LEFT_IN_PLACE = "left_in_place"


def _restore_missing(
    recorded: LedgerTarget, *, root: Path, harness_name: str, allowed_root: Path
) -> list[MaterializationResult]:
    """Copy back each file of a swept path's backup that is missing now.

    Releases 1.0.1 to 1.5.0 swept folders that held a user's own files
    (``~/.claude/commands``, ``~/.codex/rules``). Rolling such an install back
    writes every file the sweep took that is not there now, atomically, and
    keeps every file that is, so nothing on disk is replaced. Each file written
    is its own ``created`` row, so a partly failed restore counts as a partial
    rollback and names what it wrote. A file that cannot be written (the path
    is unsafe, a file stands where a folder was, no permission) is listed in a
    closing ``error`` row; the others are still restored. Every row names the
    backup, so the rollback record keeps it referenced.
    """
    target = Path(recorded.path)
    backup = Path(str(recorded.backup_ref)) if recorded.backup_ref else None
    if backup is None or not backup.exists():
        return [
            _result(
                "skipped",
                "restore_backup",
                target,
                "left in place: Apothem no longer sweeps this path and its "
                "backup is gone, so nothing was restored there",
                detail={LEFT_IN_PLACE: "backup-gone"},
            )
        ]
    in_the_way = _in_the_way(target, backup)
    if in_the_way is not None:
        return [
            _result(
                "skipped",
                "restore_backup",
                target,
                f"left in place: {target} is now {in_the_way}, so nothing was "
                f"restored there; copy what you need from {backup}",
                backup_path=backup,
                detail={LEFT_IN_PLACE: in_the_way},
            )
        ]
    files = (
        [backup]
        if backup.is_file()
        else sorted(path for path in backup.rglob("*") if path.is_file())
    )
    rows: list[MaterializationResult] = []
    failed: list[str] = []
    for source in files:
        destination = (
            target if source == backup else target / source.relative_to(backup)
        )
        if destination.exists() or _is_link(destination):
            continue
        try:
            written = write_bytes_safely(
                destination,
                source.read_bytes(),
                install_root=root,
                harness_name=harness_name,
                operation="restore_backup",
                source=source,
                allowed_root=allowed_root,
            )
        except OSError:
            failed.append(str(destination))
            continue
        if written.outcome == "error":
            failed.append(str(destination))
        else:
            rows.append(
                _result(
                    "created",
                    "restore_backup",
                    destination,
                    f"restored from {source}",
                    source=source,
                    backup_path=backup,
                )
            )
    restored = len(rows)
    if failed:
        rows.append(
            _result(
                "error",
                "restore_backup",
                target,
                f"restored {restored} missing file(s) from {backup}; could not "
                f"write {', '.join(failed)}; copy them from the backup by hand",
                source=backup,
                backup_path=backup,
                detail={"failed": ", ".join(failed)},
            )
        )
        return rows
    message = (
        f"restored {restored} missing file(s) from {backup}; kept what is there now"
        if restored
        else f"left in place: everything in {backup} is still there"
    )
    rows.append(
        _result(
            "unchanged",
            "restore_backup",
            target,
            message,
            source=backup,
            backup_path=backup,
        )
    )
    return rows


def _in_the_way(target: Path, backup: Path) -> str | None:
    """Name what now stands at *target* that a restore of *backup* must not touch.

    A link (symlink or junction) is never written through. A folder backup
    cannot land on a file, nor a file backup on a folder.
    """
    if _is_link(target):
        return "a link"
    if backup.is_dir() and target.is_file():
        return "a file"
    if backup.is_file() and target.is_dir():
        return "a folder"
    return None


@locked_for_harness
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

    A target in a user-level folder (``~/.agents/skills/``) is reversed within
    the home, and only when no other install still lists it: a ``created`` flag
    alone is not enough, because a later install may have claimed the target.
    A target this install only found in place goes too when an install that has
    let go of it created it (:meth:`UserLevelGate.inherited`), so rolling back
    every holder does not strand the folder. An unreadable ledger stops the
    rollback before anything changes.
    The rollback holds the user-level lock (see ``shared_scope``).
    """
    root = _root_for(harness_root, project_root)
    allowed_root = _allowed_write_root(harness_root, project_root)
    gate = UserLevelGate.for_harness(
        harness_name, root=root, harness_root=harness_root, project_root=project_root
    )
    blocked = gate.ledger_blocked(target.path for target in record.targets)
    if blocked is not None:
        return [blocked]
    results: list[MaterializationResult] = []
    for recorded in reversed(record.targets):
        result: MaterializationResult | None = None
        if recorded.mode == "sweep_stale" and not _still_swept(
            recorded.path, harness_name, root=root
        ):
            # The path left the stale-sweep list, so it was the user's: put back
            # what is missing, never over what is there now.
            results.extend(
                _restore_missing(
                    recorded,
                    root=root,
                    harness_name=harness_name,
                    allowed_root=allowed_root,
                )
            )
            continue
        shared = gate.covers(recorded.path)
        target_root = gate.boundary if shared else allowed_root
        if shared:
            result = gate.retained(recorded.path)
            if result is not None:
                results.append(result)
                continue
        with gate.scope_for(recorded.path):
            if recorded.backup_ref:
                result = _restore_target(
                    recorded,
                    root=root,
                    harness_name=harness_name,
                    allowed_root=target_root,
                )
            elif recorded.outcome == "created" or (
                shared
                and recorded.outcome == "unchanged"
                and gate.inherited(recorded.path, record)
            ):
                result = _remove_created(
                    Path(recorded.path),
                    root=root,
                    harness_name=harness_name,
                    allowed_root=target_root,
                )
        if result is not None:
            results.append(result)
    created = {Path(path) for path in record.created_dirs}
    # The stores live where the reversed install wrote them, as its record says.
    home = _data_home_for(record, root=root)
    stores = DataHome.from_root(home)
    if created & {stores.memory, stores.contexts, stores.learning}:
        removal = _remove_data_home(
            harness_name, root=root, home=home, allowed_root=allowed_root
        )
        if removal is not None and removal.outcome != "unchanged":
            results.append(removal)
    results.extend(remove_created_dirs(created, allowed_root=allowed_root))
    results.extend(gate.tidy(created))
    return results
