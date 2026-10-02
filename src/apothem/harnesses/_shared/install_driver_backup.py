# SPDX-License-Identifier: MIT

"""Backup capture, atomic write, restore, and install-ledger projection."""

from __future__ import annotations

import contextlib
import hashlib
import shutil
from pathlib import Path

from apothem.harnesses._shared import install_driver
from apothem.lib import atomic_io, install_ledger
from apothem.lib.install_ledger import LedgerRecord, LedgerTarget

from .install_driver_pathsafety import (
    _allowed_write_root,
    _normalized,
    _root_for,
    _validate_target_path,
    _within_allowed_root,
)
from .install_driver_types import (
    MaterializationResult,
    MaterializationRun,
    _handle_rm_error,
    _result,
)


def _unique_path(path: Path) -> Path:
    """Return *path* or a suffixed sibling when the path already exists."""
    if not path.exists():
        return path
    for index in range(1, 1000):
        candidate = path.with_name(f"{path.name}.{index}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"cannot allocate backup path for {path}")


def _reserve_unique_backup(base: Path, *, is_dir: bool) -> Path:
    """Atomically reserve a unique backup destination, suffixing on collision.

    Closes the check-then-act race that lets two concurrent install passes
    resolve the same ``base`` within a single timestamp second (the granularity
    of ``_timestamp_slug``). The first reserver gets ``base``; subsequent
    reservers get ``base.1``, ``base.2`` ... . The reservation is the
    filesystem object itself — an empty directory for tree backups, an
    exclusively-created placeholder file for single-file backups — so the win
    is atomic across processes rather than a non-atomic existence check that
    races into ``FileExistsError`` (Windows ``WinError 183``).

    The uncontended path returns ``base`` unchanged, preserving the documented
    ``~/.apothem/backups/<timestamp>/<harness>/<relative-path>`` layout for the
    common case; the suffix appears only on a genuine same-second collision.

    Args:
        base: The desired destination path under the backup root.
        is_dir: ``True`` when *base* names a directory backup (reserved via
            ``mkdir``), ``False`` when it names a file backup (reserved via an
            exclusive ``touch``).

    Returns:
        The reserved destination path. Callers populate it: a directory backup
        copies into it with ``dirs_exist_ok=True``; a file backup overwrites
        the placeholder via ``copy2``.

    Raises:
        RuntimeError: When 1000 suffixed candidates are all taken.
    """
    base.parent.mkdir(parents=True, exist_ok=True)
    for index in range(1000):
        candidate = base if index == 0 else base.with_name(f"{base.name}.{index}")
        try:
            if is_dir:
                candidate.mkdir()
            else:
                candidate.touch(exist_ok=False)
        except FileExistsError:
            continue
        return candidate
    raise RuntimeError(f"cannot allocate backup path for {base}")


def _sibling_backup_path(target: Path) -> Path:
    """Return a timestamped sibling backup path for a file target."""
    timestamp = install_driver._timestamp_slug()
    return _unique_path(target.parent / f"{target.name}.{timestamp}.bak")


def _replace_path(
    target: Path,
    *,
    install_root: Path,
    harness_name: str,
    allowed_root: Path | None = None,
) -> MaterializationResult | None:
    """Backup and remove one existing target before writing its replacement."""
    target_error = _validate_target_path(
        target,
        allowed_root=allowed_root or install_root,
        operation="remove_existing",
    )
    if target_error is not None:
        return target_error
    if not target.exists():
        return None
    backup = backup_existing(
        target,
        install_root=install_root,
        harness_name=harness_name,
        allowed_root=allowed_root or install_root,
    )
    if target.is_dir():
        shutil.rmtree(target, onerror=_handle_rm_error)
    else:
        with contextlib.suppress(OSError):  # pragma: no cover
            target.unlink()
    return _result(
        "updated",
        "remove_existing",
        target,
        "removed existing target before replacement",
        backup_path=backup,
    )


def backup_file_to_sibling(target: Path) -> Path | None:
    """Rename *target* to a timestamped sibling backup when it is a file."""
    if not target.is_file():
        return None
    backup = _sibling_backup_path(target)
    target.rename(backup)
    return backup


def _backup_relative_path(target: Path, boundary_root: Path) -> Path:
    """Return *target* relative to the allowed-write boundary root.

    The boundary is ``_allowed_write_root`` (the home/parent for user-scope, the
    project root for project-scope) — NOT the narrower harness install root. A
    harness whose targets reach outside its own root (codex writes
    ``~/.config/apothem/…`` and ``~/.agents/skills/…`` alongside ``~/.codex/…``)
    therefore keeps each target's full relative path under the backup tree, so two
    distinct out-of-root files never collapse to one basename and
    :func:`restore_backup` can rebuild the original absolute path from the same
    boundary. The basename fallback only fires for a target genuinely outside the
    boundary (a defect the write path already refuses).
    """
    try:
        return target.resolve().relative_to(boundary_root.resolve())
    except ValueError:
        return Path(target.name)


def backup_existing(
    target: Path,
    *,
    install_root: Path,
    harness_name: str,
    allowed_root: Path | None = None,
) -> Path | None:
    """Copy an existing target into the Apothem backup root before mutation.

    The backup is keyed by *target*'s path relative to *allowed_root* (the
    allowed-write boundary; defaults to *install_root* for callers that share the
    two), so the backup tree mirrors the boundary-relative layout that
    :func:`restore_backup` reconstructs against.
    """
    if not target.exists():
        return None
    rel = _backup_relative_path(target, allowed_root or install_root)
    base = (
        install_driver.BACKUP_ROOT
        / install_driver._timestamp_slug()
        / harness_name
        / rel
    )
    if target.is_dir():
        backup = _reserve_unique_backup(base, is_dir=True)
        shutil.copytree(target, backup, dirs_exist_ok=True)
    else:
        backup = _reserve_unique_backup(base, is_dir=False)
        shutil.copy2(target, backup)
    return backup


def _write_file_atomically(target: Path, data: bytes) -> None:
    """Write *data* through a sibling temp file and atomic replace.

    Delegates to :func:`apothem.lib.atomic_io.write_bytes_atomically` so the
    engine has a single atomic-write implementation shared with the state
    stores and the append-only ledger.
    """
    atomic_io.write_bytes_atomically(target, data)


def write_bytes_safely(
    target: Path,
    content: bytes,
    *,
    install_root: Path,
    harness_name: str,
    operation: str = "write_bytes",
    source: Path | None = None,
    allowed_root: Path | None = None,
) -> MaterializationResult:
    """Write bytes with no-op detection, backup-before-replace, and atomic swap."""
    target_error = _validate_target_path(
        target,
        allowed_root=allowed_root or install_root,
        operation=operation,
    )
    if target_error is not None:
        return target_error
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return _result(
            "error",
            operation,
            target,
            f"could not create target directory: {exc}",
            source=source,
        )
    existed = target.exists()
    backup: Path | None = None
    if existed:
        try:
            if target.read_bytes() == content:
                return _result(
                    "unchanged",
                    operation,
                    target,
                    "content already matches",
                    source=source,
                )
        except OSError:
            # Best-effort read: backup and replacement still report any write error.
            pass
        try:
            backup = backup_existing(
                target,
                install_root=install_root,
                harness_name=harness_name,
                allowed_root=allowed_root or install_root,
            )
        except OSError as exc:
            return _result(
                "error",
                operation,
                target,
                f"could not back up existing target: {exc}",
                source=source,
            )
    try:
        install_driver._write_file_atomically(target, content)
    except OSError as exc:
        return _result(
            "error",
            operation,
            target,
            f"could not write target atomically: {exc}",
            source=source,
            backup_path=backup,
        )
    return _result(
        "updated" if existed else "created",
        operation,
        target,
        "wrote file",
        source=source,
        backup_path=backup,
    )


def _guarded_unlink(
    target: Path,
    *,
    allowed_root: Path,
    operation: str,
) -> MaterializationResult:
    """Delete *target* after confirming it stays inside *allowed_root*.

    The deletion path for an Apothem-only file the surgical uninstall reduced to
    empty. Guards the unlink with the same path-escape / symlink check the write
    paths use, so an uninstall can never delete outside the materialization root.
    """
    target_error = _validate_target_path(
        target, allowed_root=allowed_root, operation=operation
    )
    if target_error is not None:
        return target_error
    with contextlib.suppress(OSError):  # pragma: no cover - defensive
        target.unlink()
    return _result("updated", operation, target, "removed Apothem-only file")


def _install_lock_path(harness_name: str, root: Path) -> Path:
    """Return the per-(harness, root) advisory install-lock path.

    Keyed by harness AND a digest of the resolved root so two installs into the
    same root serialize behind one lock while installs into different roots run
    concurrently. The lock lives under the (test-isolatable) ledger state root,
    not inside the install tree.
    """
    digest = hashlib.sha256(str(root.resolve()).encode("utf-8")).hexdigest()[:16]
    return install_ledger.STATE_ROOT / harness_name / f"{digest}.install.lock"


def _compensating_rollback(
    results: list[MaterializationResult], *, allowed_root: Path
) -> None:
    """Undo the on-disk writes recorded in *results* (newest first).

    Reverses a partially-applied install pass: a target with a captured backup is
    restored from it (the operator's prior bytes or tree); a target written fresh
    (no backup) is removed (its pre-install state was absence). Targets outside
    *allowed_root* are skipped defensively. Best-effort and exception-safe — it
    runs from an ``except`` handler that re-raises the original failure, so it must
    not raise itself.
    """
    for result in reversed(results):
        if result.outcome not in {"created", "updated"}:
            continue
        target = Path(result.path)
        if not _within_allowed_root(_normalized(target), _normalized(allowed_root)):
            continue
        with contextlib.suppress(OSError):
            if result.backup_path:
                backup = Path(result.backup_path)
                if backup.is_dir():
                    if target.exists():
                        shutil.rmtree(target, onerror=_handle_rm_error)
                    shutil.copytree(backup, target, dirs_exist_ok=True)
                elif backup.is_file():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(backup, target)
            elif target.is_dir():
                shutil.rmtree(target, onerror=_handle_rm_error)
            elif target.exists():
                target.unlink()


# Result outcomes that represent a materialized on-disk file worth recording in
# the install ledger (a created/updated/unchanged target). A clean install yields
# only created/updated, so this set equals the run's ``files_written`` there while
# also capturing the full managed set on an idempotent re-install.
_LEDGER_OUTCOMES: frozenset[str] = frozenset({"created", "updated", "unchanged"})

# Result operations that are NOT standalone installed ledger targets: the
# per-surface data-home files (reversed wholesale by the data-home cleanup on
# uninstall, not file-by-file), the advisory capability-projection note, and the
# stale-sweep pass (a removal that emits an ``unchanged`` result for every absent
# legacy path — recording those would log phantom targets that were never written).
_NON_LEDGER_OPERATIONS: frozenset[str] = frozenset(
    {"data_surface", "capability_projection", "sweep_stale"}
)


def _ledger_targets(
    run: MaterializationRun, *, prior: LedgerRecord | None = None
) -> tuple[LedgerTarget, ...]:
    """Project a materialization run's written files to typed ledger targets.

    One :class:`LedgerTarget` per created/updated/unchanged file result, carrying
    the path, the install mode (the result ``operation`` — ``sentinel_merge`` /
    ``write_text`` / a tree mode), the ownership class, the backup reference
    captured during the write, the pass outcome, the entries Apothem owns in a
    structured config, and whether Apothem created the file in this install
    cycle (carried forward from *prior*, the record that was current before this
    pass). Data-surface and advisory results are excluded; duplicate paths
    collapse to the first occurrence.
    """
    earlier = {target.path: target for target in prior.targets} if prior else {}
    targets: list[LedgerTarget] = []
    seen: set[str] = set()
    for result in run.results:
        if result.outcome not in _LEDGER_OUTCOMES:
            continue
        if result.operation in _NON_LEDGER_OPERATIONS:
            continue
        if result.path in seen:
            continue
        seen.add(result.path)
        before = earlier.get(result.path)
        created: bool | None
        if result.outcome == "created":
            created = True
        elif before is not None:
            created = before.created
        else:
            created = False
        targets.append(
            LedgerTarget(
                path=result.path,
                mode=result.operation,
                ownership_class=result.detail.get("ownership_class", "operator-owned"),
                backup_ref=result.backup_path,
                outcome=result.outcome,
                created=created,
                owned=result.owned,
            )
        )
    return tuple(targets)


def record_install(run: MaterializationRun, *, root: Path) -> LedgerRecord | None:
    """Append an install record for *run* to the per-harness ledger; return it.

    The record captures every file the pass wrote (including the materializer
    adapters' native configs, which are part of the adapter's combined run) so
    uninstall and rollback can reverse exactly what was installed rather than
    re-deriving intent from the live manifest. A dry-run pass records nothing
    (returns ``None``); a pass that wrote nothing still records an empty-target
    install marker so the harness+root has a latest record.
    """
    if run.dry_run:
        return None
    try:
        prior = install_ledger.current_install_record(run.harness, root=root)
    except install_ledger.LedgerError:
        prior = None
    record = LedgerRecord.create(
        harness=run.harness,
        root=root,
        kind="install",
        targets=_ledger_targets(run, prior=prior),
    )
    install_ledger.append_record(record)
    return record


def finalize_install(run: MaterializationRun, *, root: Path) -> MaterializationRun:
    """Record *run* in the install ledger and return it unchanged.

    The pass-through an adapter's ``install``/``update`` wraps around its final
    :class:`MaterializationRun` so every supported install surface (the CLI, the
    plugin shim, a direct adapter call) writes the ledger record uniformly at the
    one layer that sees the complete run — manifest targets, the projected
    instruction anchor, and any materializer-rendered native config alike.
    """
    record_install(run, root=root)
    return run


def list_backup_timestamps(harness_name: str | None = None) -> list[str]:
    """Return available backup timestamps under the Apothem backup root.

    Each timestamp is a ``~/.apothem/backups/<timestamp>/`` directory created
    before a mutating install pass. When *harness_name* is given, only
    timestamps carrying a backup set for that harness are returned. Results are
    sorted oldest-to-newest (the timestamp slug sorts lexically by time).
    """
    if not install_driver.BACKUP_ROOT.is_dir():
        return []
    stamps: list[str] = []
    for ts_dir in sorted(install_driver.BACKUP_ROOT.iterdir()):
        if not ts_dir.is_dir():
            continue
        if harness_name is None or (ts_dir / harness_name).is_dir():
            stamps.append(ts_dir.name)
    return stamps


def restore_backup(
    harness_name: str,
    timestamp: str,
    *,
    harness_root: Path | None = None,
    project_root: Path | None = None,
    only_refs: frozenset[str] | None = None,
) -> list[MaterializationResult]:
    """Restore a harness's files from a ``~/.apothem/backups/<timestamp>`` set.

    The backup tree at ``BACKUP_ROOT/<timestamp>/<harness_name>/`` mirrors the
    layout captured before the matching install pass, keyed relative to the
    allowed-write boundary (the home/parent for user-scope, the project root for
    project-scope). Each backed-up file is copied back to
    ``<allowed_root>/<relative-path>``, recreating parents and backing up
    whatever currently occupies the destination (the restore is itself
    reversible). Because the key is boundary-relative, an out-of-root target
    (codex ``~/.config/apothem/…`` or ``~/.agents/skills/…``) restores to its
    true original path rather than collapsing under the harness root.

    When *only_refs* is supplied (a set of resolved backup-file paths — the
    ``backup_ref`` values recorded by one install pass), restoration is scoped
    to exactly those files. The timestamp slug is second-granular, so two
    install passes in the same second share a ``<timestamp>/<harness>/`` set;
    scoping to a single record's refs keeps a rollback from clobbering files a
    sibling pass backed up under the shared timestamp. ``None`` restores the
    whole set (the legacy contract).

    Only file contents are restored; an intentionally-empty directory the
    operator had created is not recreated (the backup walk keys on files). This
    is a deliberate scope limit — config trees Apothem backs up are file sets,
    not empty-directory structures.

    Raises:
        ValueError: When neither *harness_root* nor *project_root* is supplied.
    """
    root = _root_for(harness_root, project_root)
    allowed_root = _allowed_write_root(harness_root, project_root)
    backup_set = install_driver.BACKUP_ROOT / timestamp / harness_name
    if not backup_set.is_dir():
        return [
            _result(
                "skipped",
                "restore_backup",
                backup_set,
                "no backup set for this harness and timestamp",
            )
        ]
    results: list[MaterializationResult] = []
    for backup_file in sorted(p for p in backup_set.rglob("*") if p.is_file()):
        if only_refs is not None and str(backup_file.resolve()) not in only_refs:
            # Scoped restore: this file belongs to a sibling pass that shared
            # the second-granular timestamp slug, not the record being rolled
            # back. Skip it so the rollback restores only its own targets.
            continue
        dest = allowed_root / backup_file.relative_to(backup_set)
        try:
            data = backup_file.read_bytes()
        except OSError as exc:  # pragma: no cover - defensive
            results.append(
                _result(
                    "error",
                    "restore_backup",
                    dest,
                    f"could not read backup file: {exc}",
                    source=backup_file,
                )
            )
            continue
        results.append(
            write_bytes_safely(
                dest,
                data,
                install_root=root,
                harness_name=harness_name,
                operation="restore_backup",
                source=backup_file,
                allowed_root=allowed_root,
            )
        )
    if not results:
        results.append(
            _result(
                "unchanged",
                "restore_backup",
                backup_set,
                "backup set contained no files",
            )
        )
    return results
