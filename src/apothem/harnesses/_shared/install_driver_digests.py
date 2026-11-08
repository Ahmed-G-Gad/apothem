# SPDX-License-Identifier: MIT

"""Project a pass's results to ledger targets, with each written file's digest.

An install record lists every file the pass wrote. Each target that is a file
or a folder Apothem copies whole (a skill, an agent, a command, a rule) also
records the SHA-256 of what the pass left on disk: ``digest`` for a file,
``files`` for each file in a folder. Uninstall removes a file only while its
content still matches, so a file the operator wrote or changed is never
removed (see :func:`install_driver_removal.remove_written`).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from apothem.lib.install_ledger import LedgerRecord, LedgerTarget

from .install_driver_pathsafety import _is_link, _walk_without_links
from .install_driver_types import MaterializationResult, MaterializationRun

#: Modes whose targets are surgically edited rather than written whole: their
#: removal compares the managed content itself, so no digest is recorded.
_EDITED_MODES: frozenset[str] = frozenset({"sentinel_merge", "sweep_stale"})


def file_digest(path: Path) -> str | None:
    """Return the SHA-256 of *path*'s bytes, or ``None`` when it cannot be read."""
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 16), b""):
                digest.update(chunk)
    except OSError:
        return None
    return digest.hexdigest()


def folder_digests(folder: Path) -> dict[str, str]:
    """Return each file under *folder* mapped to its SHA-256, never entering a link.

    Keys are ``/``-separated paths relative to *folder*. A file that cannot be
    read is left out, so it is never treated as Apothem's.
    """
    digests: dict[str, str] = {}
    for path in _walk_without_links(folder).files:
        digest = file_digest(path)
        if digest is not None:
            digests[path.relative_to(folder).as_posix()] = digest
    return digests


def _written_digests(
    result: MaterializationResult,
) -> tuple[str | None, dict[str, str] | None]:
    """Return the ``digest`` and ``files`` fields for one written target."""
    if result.owned is not None or result.operation in _EDITED_MODES:
        return None, None
    path = Path(result.path)
    if _is_link(path):
        return None, None
    if path.is_file():
        return file_digest(path), None
    if path.is_dir():
        return None, folder_digests(path)
    return None, None


# Result outcomes that represent a materialized on-disk file worth recording in
# the install ledger (a created/updated/unchanged target). A clean install yields
# only created/updated, so this set equals the run's ``files_written`` there while
# also capturing the full managed set on an idempotent re-install.
_LEDGER_OUTCOMES: frozenset[str] = frozenset({"created", "updated", "unchanged"})

# Result operations that are NOT standalone installed ledger targets: the
# per-surface data-home files (reversed wholesale by the data-home cleanup on
# uninstall, not file-by-file) and the advisory capability-projection note. A
# stale-sweep result is recorded only when it removed something (an ``updated``
# result carrying its backup), so rollback can put the swept path back; the
# ``unchanged`` result every absent legacy path emits is not a target.
_NON_LEDGER_OPERATIONS: frozenset[str] = frozenset(
    {"data_surface", "capability_projection"}
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
        if result.operation == "sweep_stale" and result.outcome != "updated":
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
        digest, files = _written_digests(result)
        targets.append(
            LedgerTarget(
                path=result.path,
                mode=result.operation,
                ownership_class=result.detail.get("ownership_class", "operator-owned"),
                backup_ref=result.backup_path,
                outcome=result.outcome,
                created=created,
                owned=result.owned,
                digest=digest,
                files=files,
            )
        )
    return tuple(targets)


def backup_ledger_targets(
    results: list[MaterializationResult],
) -> tuple[LedgerTarget, ...]:
    """Project the backups an uninstall or rollback relied on to ledger targets.

    One :class:`LedgerTarget` per result that carries a backup, with the same
    path, mode (the result ``operation``), ownership class and outcome
    projection :func:`_ledger_targets` uses for install records. Recording them
    keeps those backup sets referenced, so retention never deletes them while
    the record itself is kept. Duplicate paths keep the first backup, the
    state before the operation.
    """
    targets: list[LedgerTarget] = []
    seen: set[str] = set()
    for result in results:
        if result.backup_path is None or result.path in seen:
            continue
        seen.add(result.path)
        targets.append(
            LedgerTarget(
                path=result.path,
                mode=result.operation,
                ownership_class=result.detail.get("ownership_class", "operator-owned"),
                backup_ref=result.backup_path,
                outcome=result.outcome,
            )
        )
    return tuple(targets)
