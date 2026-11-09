# SPDX-License-Identifier: MIT

"""Remove a target only as far as its install record shows Apothem wrote it.

An install record carries the SHA-256 of each file the pass wrote (see
:mod:`install_driver_digests`). Uninstall removes a file only while it still
holds that content, so a file the operator added to an Apothem folder, or one
that replaced an Apothem file of the same name, stays.
"""

from __future__ import annotations

import contextlib
import os
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path

from apothem.lib import install_ledger
from apothem.lib.harness_materializer import (
    APOTHEM_BLOCK_END,
    complete_managed_block,
    has_stray_begin,
)
from apothem.lib.install_ledger import LedgerRecord, LedgerTarget

from .install_driver_backup import backup_existing
from .install_driver_digests import backup_ledger_targets, file_digest
from .install_driver_pathsafety import (
    _is_link,
    _normalized,
    _unsafe_symlink,
    _validate_target_path,
    _walk_without_links,
    kept_links_detail,
)
from .install_driver_retention import apply_retention
from .install_driver_sweep import _link_kept as link_kept
from .install_driver_sweep import kept_link_warnings, links_left_in
from .install_driver_types import MaterializationResult, _path_text, _result

#: ``detail`` key of a removal: the files it kept because nothing shows Apothem
#: wrote them as they are now (newline-joined paths).
KEPT_FILES = "kept_files"

#: ``detail`` key of a failed removal: the files Apothem wrote that it could
#: not remove (newline-joined paths).
STUCK_FILES = "stuck_files"

#: Kept reasons that leave the uninstall unfinished: files of an install an
#: earlier release recorded, which this release cannot show are Apothem's.
UNFINISHED_REASONS: frozenset[str] = frozenset({"no-digests"})

#: ``detail`` key naming why a target was kept whole (see :func:`remove_written`).
KEPT_REASON = "kept_reason"


def _proof(entry: LedgerTarget | None) -> dict[str, str] | None:
    """Return what the record shows Apothem wrote at *entry*, keyed by relative path.

    ``""`` keys a file target. ``None`` when the record holds no digests.
    """
    if entry is None:
        return None
    if entry.files is not None:
        return entry.files
    return {"": entry.digest} if entry.digest is not None else None


def _written_now(target: Path, proof: dict[str, str]) -> list[Path]:
    """Return the files at *target* that still hold what Apothem wrote.

    Reads through a link (nothing is removed here), never enters one below
    *target*.
    """
    if target.is_file():
        return [target] if _matches(target, proof.get("")) else []
    if not target.is_dir():
        return []
    return [
        path
        for path in _walk_without_links(target).files
        if _matches(path, proof.get(path.relative_to(target).as_posix()))
    ]


def _matches(path: Path, expected: str | None) -> bool:
    """Return True when *path* is readable and has the recorded SHA-256 *expected*.

    A path the record does not list, or one that cannot be read, never matches.
    """
    if expected is None:
        return False
    return file_digest(path) == expected


def _kept_whole(target: Path, reason: str, message: str) -> MaterializationResult:
    """Return the warning for a target an uninstall left entirely in place."""
    return _result(
        "warning",
        "remove_existing",
        target,
        f"{target} was kept: {message}",
        detail={KEPT_REASON: reason},
    )


def _through_link(
    target: Path, link: Path, proof: dict[str, str] | None
) -> MaterializationResult:
    """Return the warning for a target reached through *link*.

    It blocks the uninstall only while Apothem's own files are behind the
    link: the tool still loads them. Otherwise the target stays and the
    uninstall completes.
    """
    blocked = proof is not None and bool(_written_now(target, proof))
    detail = {"symlink": _path_text(link)}
    if blocked:
        detail["blocked"] = "1"
    return _result(
        "warning",
        "remove_existing",
        target,
        f"{target} is reached through the link {link}, so it was left in "
        "place: Apothem does not remove anything through a link",
        detail=detail,
    )


def _remove_matching(
    target: Path, written: list[Path]
) -> tuple[list[Path], list[Path]]:
    """Remove *written* under the folder *target*; return the files and links kept.

    Each folder that held a removed file goes once empty, deepest first; a
    folder that still holds something stays, and so does an empty folder the
    operator made, which held nothing Apothem wrote.
    """
    for path in written:
        if not _is_link(path):
            with contextlib.suppress(OSError):
                path.unlink()
    emptied = {target}
    for path in written:
        emptied.update(
            parent
            for parent in path.parents
            if parent == target or target in parent.parents
        )
    for folder in sorted(emptied, key=lambda path: len(path.parts), reverse=True):
        if not _is_link(folder):
            with contextlib.suppress(OSError):
                folder.rmdir()
    if not target.exists():
        return [], []
    after = _walk_without_links(target)
    return after.files, [*after.links, *after.unreadable]


def remove_written(
    target: Path,
    *,
    recorded: Mapping[str, LedgerTarget] | None,
    install_root: Path,
    harness_name: str,
    allowed_root: Path | None = None,
    expected: Callable[[Path], dict[str, str] | None] | None = None,
) -> MaterializationResult | None:
    """Remove *target* only as far as the install record shows Apothem wrote it.

    *recorded* maps each path of the install record to its target (``None``
    when there is no record). A file goes only while its SHA-256 matches the
    recorded ``digest``; in a folder only the recorded files whose content
    still matches go, then each folder left empty. Everything else stays and
    is named in the result: a file the operator added or changed, a target
    the record does not list, and anything behind a link. The target is
    backed up before anything is removed.

    A target an earlier release recorded without digests is compared with
    what this release writes there (*expected*, the digests of those files;
    see :func:`install_driver_expected.expected_digests`): a file with those
    bytes goes. A file at a name Apothem writes that differs stays and leaves
    the uninstall unfinished (``kept_reason`` ``no-digests``), since run
    ``apothem update`` records it, then a second uninstall finishes.
    """
    allowed = allowed_root or install_root
    entry = None if recorded is None else recorded.get(_path_text(target))
    proof = _proof(entry)
    legacy = proof is None and entry is not None and expected is not None
    if legacy and expected is not None:
        proof = expected(target)
    target_error = _validate_target_path(
        target, allowed_root=allowed, operation="remove_existing"
    )
    if target_error is not None:
        link = _unsafe_symlink(target, _normalized(allowed))
        return target_error if link is None else _through_link(target, link, proof)
    if not target.exists():
        return None
    if proof is None:
        if recorded is None:
            return _kept_whole(
                target, "no-record", "no install record shows Apothem wrote it"
            )
        if entry is None:
            return _kept_whole(
                target, "unrecorded", "the install record does not list it"
            )
        return _kept_whole(
            target,
            "no-digests",
            _EARLIER_RELEASE,
        )
    written = _written_now(target, proof)
    if not written:
        if legacy and _named_by(target, proof):
            return _kept_whole(target, "no-digests", _EARLIER_RELEASE)
        return _kept_whole(
            target, "changed", "it is not what Apothem wrote (changed or yours)"
        )
    backup = backup_existing(
        target,
        install_root=install_root,
        harness_name=harness_name,
        allowed_root=allowed,
    )
    if target.is_file():
        with contextlib.suppress(OSError):
            target.unlink()
        kept_files: list[Path] = []
        kept_links: list[Path] = []
    else:
        kept_files, kept_links = _remove_matching(target, written)
    stuck = [path for path in written if os.path.lexists(path)]
    if stuck:
        return _result(
            "error",
            "remove_existing",
            target,
            f"could not remove {len(stuck)} file(s) Apothem wrote at {target}; "
            "close what holds them or make them writable, then run the command "
            "again",
            backup_path=backup,
            detail={STUCK_FILES: "\n".join(_path_text(path) for path in stuck)},
        )
    detail = kept_links_detail(kept_links)
    if kept_files:
        detail[KEPT_FILES] = "\n".join(_path_text(path) for path in kept_files)
    if legacy and _named_by(target, proof, kept_files):
        detail[KEPT_REASON] = "no-digests"
    return _result(
        "updated",
        "remove_existing",
        target,
        "removed the files Apothem wrote",
        backup_path=backup,
        detail=detail,
    )


#: Why a target an earlier release recorded stays, and the next step.
_EARLIER_RELEASE = (
    "the install record (made by an earlier release) does not show which files "
    "Apothem wrote, and it differs from what this release writes; move any file "
    "of your own out of it (an update replaces it), then run apothem update, "
    "then apothem uninstall again"
)


def _named_by(
    target: Path, proof: dict[str, str], paths: list[Path] | None = None
) -> bool:
    """Return True when a file at *target* (or among *paths*) has a name *proof* lists."""
    if target.is_file():
        return "" in proof
    found = _walk_without_links(target).files if paths is None else paths
    return any(path.relative_to(target).as_posix() in proof for path in found)


def kept_file_warnings(
    results: list[MaterializationResult],
) -> list[MaterializationResult]:
    """Return one warning per folder in which a removal kept files.

    The files were not written by Apothem as they are now: the operator added
    or changed them, so the folder stays with them in it.
    """
    warnings = []
    for result in results:
        kept = [line for line in result.detail.get(KEPT_FILES, "").splitlines() if line]
        if not kept:
            continue
        folder = Path(result.path)
        if result.detail.get(KEPT_REASON) == "no-digests":
            warnings.append(_kept_whole(folder, "no-digests", _EARLIER_RELEASE))
            continue
        names = [Path(path).relative_to(folder).as_posix() for path in kept]
        shown = ", ".join(names[:5]) + (
            f" and {len(names) - 5} more" if len(names) > 5 else ""
        )
        warnings.append(
            _kept_whole(
                folder,
                "changed",
                f"{len(kept)} file(s) in it are not what Apothem wrote "
                f"(changed or yours): {shown}",
            )
        )
    return warnings


def links_on_the_way(
    paths: Iterable[str],
    floor: Path,
    *,
    known: list[MaterializationResult],
) -> list[MaterializationResult]:
    """Return one warning per link between *floor* and a recorded path.

    An uninstall leaves a link and what it points to in place; when nothing
    of Apothem's is left behind it, nothing else would name it. A link a
    result in *known* already names is skipped.
    """
    seen = {result.path for result in known} | {
        result.detail["symlink"] for result in known if "symlink" in result.detail
    }
    notes = []
    for text in paths:
        for ancestor in Path(text).parents:
            if ancestor == floor or floor not in ancestor.parents:
                break
            if _path_text(ancestor) not in seen and _is_link(ancestor):
                seen.add(_path_text(ancestor))
                notes.append(link_kept(ancestor))
    return notes


def left_behind(
    results: list[MaterializationResult],
    active: list[LedgerRecord],
    *,
    floor: Path,
    prior: tuple[MaterializationResult, ...] = (),
) -> list[MaterializationResult]:
    """Return a warning for each path the uninstall kept: links and the user's files.

    A link a *prior* result (the caller's own removal) already names is not
    named again.
    """
    kept = [*kept_link_warnings(results), *kept_file_warnings(results)]
    created = {Path(path) for install in active for path in install.created_dirs}
    named = {result.detail.get("symlink") for result in (*prior, *results)}
    kept += [
        warning
        for warning in links_left_in(created, known=kept)
        if warning.path not in named
    ]
    recorded = (target.path for install in active for target in install.targets)
    return [
        *kept,
        *links_on_the_way(recorded, floor, known=[*prior, *results, *kept]),
        *stray_begin_warnings([*prior, *results]),
    ]


def stray_begin_at(path: Path) -> bool:
    """Return True when *path* holds a BEGIN marker that starts no whole block."""
    try:
        text = path.read_bytes().decode("utf-8", errors="replace")
    except OSError:
        return False
    return has_stray_begin(text)


def stray_begin_install_warnings(
    results: list[MaterializationResult],
) -> list[MaterializationResult]:
    """Name each managed-block file an install or update keeps a stray BEGIN in.

    The text after a BEGIN marker with no END is kept as it is, and Apothem's
    own block is written apart from it, so the marker stays until the operator
    deletes it; verify reports the file until then.
    """
    paths = dict.fromkeys(
        result.path
        for result in results
        if result.operation == "sentinel_merge" and result.outcome != "error"
    )
    return [
        _result(
            "warning",
            "stray_begin",
            Path(path),
            f"{path} has an Apothem BEGIN marker that starts no whole block of its "
            f"own (its END marker {APOTHEM_BLOCK_END} is gone, or the marker is "
            "yours). Apothem never cuts the text after it: install and update "
            "keep that text as it is and write their block apart from it. Delete "
            "that marker line by hand; apothem verify fails for this tool until "
            "you do.",
        )
        for path in paths
        if stray_begin_at(Path(path))
    ]


def endless_block_left(entry: LedgerTarget) -> bool:
    """Return True when *entry*, a managed-block file, lost its block's END marker.

    After an unfinished uninstall such a file keeps the install open, so the
    next uninstall runs, names the file and finishes (see :func:`still_written`,
    which does not count it as Apothem's).
    """
    return entry.mode == "sentinel_merge" and stray_begin_at(Path(entry.path))


def stray_begin_warnings(
    results: list[MaterializationResult],
) -> list[MaterializationResult]:
    """Name each file the uninstall rewrote that still holds a BEGIN marker alone.

    Taking Apothem's whole block out can leave such a line above where it was
    (a stray line of the operator's, say). An install keeps it as it is and
    verify reports the file, so the operator deletes it by hand.
    """
    rewritten = {
        result.path: result.operation
        for result in results
        if result.outcome == "updated"
        and result.operation in {"surgical_uninstall", "retire_anchor"}
    }
    return [
        _result(
            "warning",
            operation,
            Path(path),
            f"{path} still holds a line that reads as the Apothem BEGIN marker, "
            f"with no END marker ({APOTHEM_BLOCK_END}) after it, now that "
            "Apothem's block is out. Delete that line by hand: an install keeps "
            "it as it is, and apothem verify fails until you do.",
        )
        for path, operation in rewritten.items()
        if stray_begin_at(Path(path))
    ]


def still_written(entry: LedgerTarget) -> bool:
    """Return True when a file *entry* records still has the content Apothem wrote.

    Used as install evidence after an unfinished uninstall: a path that merely
    exists (a settings file the tool recreated, a folder of the operator's)
    proves nothing, unless the record predates digests. A managed-block file
    (``sentinel_merge``) is meant to hold the operator's text beside Apothem's
    block, so the block, not the whole file, is what Apothem wrote: it counts
    while it carries the whole block, both markers. A BEGIN marker left without
    its END does not count: the uninstall leaves that file as it is.
    """
    if entry.mode == "sentinel_merge":
        try:
            text = Path(entry.path).read_bytes().decode("utf-8", errors="replace")
        except OSError:
            return False
        return complete_managed_block(text) is not None
    proof = _proof(entry)
    if proof is None:
        # An earlier release recorded no digests: the path is the evidence,
        # and the removal that follows still checks each file's content.
        return os.path.lexists(entry.path)
    return bool(_written_now(Path(entry.path), proof))


def install_may_be_open(harness_name: str, root: Path) -> bool:
    """Return False only when the ledger shows the install at *root* was closed.

    Closed means the latest record there is an ``uninstall``, or a rollback of
    a known install.

    An install still in effect, and a root the ledger knows nothing about (an
    install from before the ledger, a ledger lost or unreadable), may be open:
    the evidence that depends on it keeps counting there.
    """
    try:
        if install_ledger.current_install_record(harness_name, root=root):
            return True
        latest = install_ledger.latest_record(harness_name, root=root, kind=None)
    except (OSError, install_ledger.LedgerError):
        return True
    if latest is None:
        return True
    # Closed: an uninstall, or a rollback of a known install. An unfinished
    # uninstall or a rollback with no install leaves it possibly open.
    return not (
        latest.kind == "uninstall"
        or (latest.kind == "rollback" and latest.install_id is not None)
    )


def left_unfinished(results: list[MaterializationResult]) -> bool:
    """Return True when Apothem's files stay where the uninstall could not finish.

    A removal failed, Apothem's files stay behind a link, or files an earlier
    release recorded without digests stay because this release cannot show
    they are Apothem's (``apothem update`` records them, then a second
    uninstall finishes).
    """
    return any(
        result.outcome == "error"
        or result.detail.get("blocked")
        or result.detail.get(KEPT_REASON) in UNFINISHED_REASONS
        for result in results
    )


def record_uninstall(
    harness_name: str,
    root: Path,
    record: LedgerRecord | None,
    results: list[MaterializationResult],
    *,
    finished: bool,
) -> None:
    """Append the uninstall record, ``uninstall-incomplete`` unless *finished*.

    Either record references every backup the pass took. A finished uninstall
    ends the install and runs retention. An unfinished one keeps the install
    active, so a second run is driven by the same record; it is written even
    when the pass raised, and a failure to write it then does not hide the
    pass's own error.
    """
    entry = LedgerRecord.create(
        harness=harness_name,
        root=root,
        kind="uninstall" if finished else "uninstall-incomplete",
        targets=backup_ledger_targets(results),
        install_id=record.install_id if record is not None else None,
    )
    if not finished:
        with contextlib.suppress(OSError, install_ledger.LedgerError):
            install_ledger.append_record(entry)
        return
    install_ledger.append_record(entry)
    apply_retention(harness_name)
