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
import re
from collections.abc import Callable, Mapping
from pathlib import Path

from apothem.lib.install_ledger import LedgerTarget

from .install_driver_backup import backup_existing
from .install_driver_blocks import whole_block_left
from .install_driver_digests import file_digest
from .install_driver_pathsafety import (
    _is_link,
    _unsafe_symlink,
    _validate_target_path,
    _walk_without_links,
    _write_boundary,
    kept_links_detail,
)
from .install_driver_types import (
    KEPT_REASON,
    MaterializationResult,
    _path_text,
    _result,
)

#: ``detail`` key of a removal: the files it kept because nothing shows Apothem
#: wrote them as they are now (newline-joined paths).
KEPT_FILES = "kept_files"

#: ``detail`` key of a removal: the files it kept that sit at a name this
#: release writes but differ from it, under an install an earlier release
#: recorded without digests (newline-joined paths).
KEPT_DIFFERING = "kept_differing"

#: ``detail`` key of a failed removal: the files Apothem wrote that it could
#: not remove (newline-joined paths).
STUCK_FILES = "stuck_files"

#: Kept reasons ``apothem update`` settles: files this release cannot show are
#: Apothem's or not, under an install an earlier release recorded without
#: digests (``no-digests``) or with no install record at all (``no-record``).
#: The update records them; a second uninstall then finishes. A path kept after
#: a finished uninstall (``no-active-install``) is not one: no install is left
#: to finish. Each leaves the uninstall unfinished (see
#: :data:`install_driver_outcome.UNFINISHED_REASONS`); the ``detail`` key is
#: :data:`~install_driver_types.KEPT_REASON`.
UNPROVEN_REASONS: frozenset[str] = frozenset({"no-digests", "no-record"})


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


def _paths(text: str) -> list[str]:
    """Split a newline-joined ``detail`` value into paths.

    Only ``\n`` separates them: a file name may hold other line breaks
    (``U+2028``, ``\x85``), which :meth:`str.splitlines` would split on.
    """
    return [path for path in text.split("\n") if path]


def _files_in(target: Path) -> list[str] | None:
    """Return what the folder *target* holds (never through a link), or ``None``.

    Files, the links in it and the folders that cannot be read: a folder kept
    whole lists them all, so the report can name each one.
    """
    if not target.is_dir() or _is_link(target):
        return None
    walk = _walk_without_links(target)
    return [_path_text(path) for path in (*walk.files, *walk.links, *walk.unreadable)]


def _kept_whole(
    target: Path, reason: str, message: str, files: list[str] | None = None
) -> MaterializationResult:
    """Return the warning for a target an uninstall left in place.

    *files* names what is kept inside a folder target (``detail``
    ``kept_files``, present even when empty), so the report can list each one.
    """
    detail = {KEPT_REASON: reason}
    if files is not None:
        detail[KEPT_FILES] = "\n".join(files)
    return _result(
        "warning",
        "remove_existing",
        target,
        f"{target} was kept: {message}",
        detail=detail,
    )


def _through_link(
    target: Path, link: Path, proof: dict[str, str] | None, *, legacy: bool
) -> MaterializationResult:
    """Return the warning for a target reached through *link*.

    It blocks the uninstall while files *proof* shows are Apothem's are behind
    the link, or, under an install an earlier release recorded (*legacy*),
    files at names this release writes: the tool still loads them. Otherwise
    the target stays and the uninstall completes.
    """
    blocked = proof is not None and (
        bool(_written_now(target, proof)) or (legacy and _named_by(target, proof))
    )
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


def _own_bytecode(source: Path) -> list[Path]:
    """Return the bytecode files Python compiled from the module *source*.

    These are ``__pycache__/<stem>.<tag>.pyc`` and
    ``__pycache__/<stem>.<tag>.opt-<n>.pyc`` beside *source*, for any
    interpreter tag. No other file in ``__pycache__`` counts as Apothem's, and
    nothing is read through a link.
    """
    if source.suffix != ".py":
        return []
    cache = source.parent / "__pycache__"
    if _is_link(cache) or not cache.is_dir():
        return []
    name = re.compile(
        re.escape(source.stem) + r"\.[A-Za-z0-9_-]+(?:\.opt-[0-9]+)?\.pyc"
    )
    try:
        entries = sorted(cache.iterdir())
    except OSError:
        return []
    return [
        path
        for path in entries
        if name.fullmatch(path.name) and not _is_link(path) and path.is_file()
    ]


def _remove_own_bytecode(removed: list[Path]) -> set[Path]:
    """Remove the bytecode of each module in *removed*; return its cache folders.

    A module that is still there (it could not be removed) keeps its bytecode.
    The caller removes each returned ``__pycache__`` folder once it is empty.
    """
    caches: set[Path] = set()
    for source in removed:
        if os.path.lexists(source):
            continue
        for path in _own_bytecode(source):
            with contextlib.suppress(OSError):
                path.unlink()
            caches.add(path.parent)
    return caches


def _remove_matching(
    target: Path, written: list[Path]
) -> tuple[list[Path], list[Path]]:
    """Remove *written* under the folder *target*; return the files and links kept.

    The bytecode Python compiled from a removed module goes with it (see
    :func:`_own_bytecode`). Then each empty folder goes (see
    :func:`_remove_empty_folders`), an emptied ``__pycache__`` and an
    operator's empty folder included: it holds nothing of anyone's, and it
    would keep *target* with nothing to report.
    """
    for path in written:
        if not _is_link(path):
            with contextlib.suppress(OSError):
                path.unlink()
    _remove_own_bytecode(written)
    _remove_empty_folders(target)
    if not target.exists():
        return [], []
    after = _walk_without_links(target)
    return after.files, [*after.links, *after.unreadable]


def _remove_empty_folders(target: Path) -> None:
    """Remove each empty folder in the folder *target*, deepest first, then *target*.

    Never through a link: the walk enters none, and none is removed. A folder
    that still holds something stays.
    """
    folders = [*_walk_without_links(target).folders, target]
    for folder in sorted(folders, key=lambda path: len(path.parts), reverse=True):
        if not _is_link(folder):
            with contextlib.suppress(OSError):
                folder.rmdir()


def _kept_detail(
    target: Path, kept: list[Path], legacy_proof: dict[str, str] | None
) -> dict[str, str]:
    """Return the ``detail`` that names the files kept in the folder *target*.

    Under an install an earlier release recorded (*legacy_proof*, what this
    release writes there), a kept file at a name this release writes is
    ``kept_differing`` and makes the uninstall unfinished; every other kept
    file is the operator's or changed (``kept_files``).
    """
    differing = [
        path
        for path in kept
        if legacy_proof is not None
        and path.relative_to(target).as_posix() in legacy_proof
    ]
    others = [path for path in kept if path not in differing]
    detail: dict[str, str] = {}
    if others:
        detail[KEPT_FILES] = "\n".join(_path_text(path) for path in others)
    if differing:
        detail[KEPT_DIFFERING] = "\n".join(_path_text(path) for path in differing)
        detail[KEPT_REASON] = "no-digests"
    return detail


def _kept_folder(
    target: Path, legacy_proof: dict[str, str] | None
) -> MaterializationResult | None:
    """Return the result for a folder in which nothing is Apothem's as it is now.

    Nothing is removed. The folder's files are named in the result's
    ``detail`` (see :func:`_kept_detail`), and its links and unreadable
    folders as ``kept_links``; :func:`kept_file_warnings` and the link
    warnings report them. A folder that holds no file goes, with the empty
    folders in it (it holds nothing of anyone's); one that stays is reported.
    """
    walk = _walk_without_links(target)
    if not walk.files and not walk.links and not walk.unreadable:
        _remove_empty_folders(target)
        if not target.exists():
            return None
        return _kept_whole(target, "not-removed", "it could not be removed")
    return _result(
        "unchanged",
        "remove_existing",
        target,
        f"{target} was kept",
        detail={
            **kept_links_detail([*walk.links, *walk.unreadable]),
            **_kept_detail(target, walk.files, legacy_proof),
        },
    )


def remove_written(
    target: Path,
    *,
    recorded: Mapping[str, LedgerTarget] | None,
    install_root: Path,
    harness_name: str,
    allowed_root: Path | None = None,
    expected: Callable[[Path], dict[str, str] | None] | None = None,
    installs_ended: bool = False,
) -> MaterializationResult | None:
    """Remove *target* only as far as the install record shows Apothem wrote it.

    *recorded* maps each path of the install record to its target (``None``
    when no install is in place). A file goes only while its SHA-256 matches
    the recorded ``digest``; in a folder only the recorded files whose content
    still matches go, then each folder left empty. Everything else stays and
    is named in the result: a file the operator added or changed, a target
    the record does not list, and anything behind a link. The target is
    backed up before anything is removed.

    With no install in place, *installs_ended* tells the two cases apart.
    False: the ledger holds no record of an install here (it was deleted, or
    never written), so nothing shows whether Apothem wrote what is there, and
    the uninstall does not finish (``kept_reason`` ``no-record``). True: the
    latest record here is a finished uninstall, so each target is compared
    with *expected*, as below, but with no install-time token filled in (an
    interpreter's path never matches; see
    :func:`install_driver_expected.expected_lookup`): a file with those bytes
    goes, and so does a folder that holds no file; the rest stays with a
    warning (``no-active-install``) but never stops the uninstall, though
    one with those bytes behind a link does. Any other history (a rollback,
    or only unfinished uninstalls) is the first case.

    A target an earlier release recorded without digests is compared with
    what this release writes there (*expected*, the digests of those files;
    see :func:`install_driver_expected.expected_digests`): a file with those
    bytes goes. A file at a name Apothem writes that differs stays and leaves
    the uninstall unfinished (``kept_reason`` ``no-digests``): ``apothem
    update`` records it, then a second uninstall finishes. The files kept in
    a folder are named in the result's ``detail`` (``kept_differing`` for
    those, ``kept_files`` for the rest); :func:`kept_file_warnings` reports
    them. Without *expected* (a rollback), such a target is compared with
    nothing, so it stays with a warning that says only that.
    """
    allowed = _write_boundary(allowed_root, install_root)
    entry = None if recorded is None else recorded.get(_path_text(target))
    proof = _proof(entry)
    legacy = proof is None and entry is not None and expected is not None
    ended = recorded is None and installs_ended
    # Before the link check, so Apothem's files behind a link are found.
    if (legacy or (ended and os.path.lexists(target))) and expected is not None:
        proof = expected(target)
    target_error = _validate_target_path(
        target, allowed_root=allowed, operation="remove_existing"
    )
    if target_error is not None:
        link = _unsafe_symlink(target, allowed)
        if link is None:
            return target_error
        return _through_link(target, link, proof, legacy=legacy)
    if not target.exists():
        return None
    written = [] if proof is None else _written_now(target, proof)
    if proof is None or (ended and not written):
        files = _files_in(target)
        if ended and files == []:
            # A folder that holds no file holds nothing of anyone's.
            return _kept_folder(target, None)
        return _kept_whole(
            target,
            *_why_kept(recorded, entry, expected, ended=installs_ended),
            files=files,
        )
    if not written and target.is_file():
        if legacy and _named_by(target, proof):
            return _kept_whole(target, "no-digests", _EARLIER_RELEASE)
        return _kept_whole(
            target, "changed", "it is not what Apothem wrote (changed or yours)"
        )
    if not written:
        return _kept_folder(target, proof if legacy else None)
    backup = backup_existing(
        target,
        install_root=install_root,
        harness_name=harness_name,
        allowed_root=allowed,
    )
    if target.is_file():
        with contextlib.suppress(OSError):
            target.unlink()
        for cache in _remove_own_bytecode([target]):
            with contextlib.suppress(OSError):
                cache.rmdir()
        kept_files: list[Path] = []
        kept_links: list[Path] = []
    else:
        kept_files, kept_links = _remove_matching(target, written)
    stuck = [path for path in written if os.path.lexists(path)]
    # A file Apothem wrote that would not go is named as stuck, never as a
    # kept file of the operator's or one that differs.
    kept = _kept_detail(
        target,
        [path for path in kept_files if path not in stuck],
        proof if legacy else None,
    )
    if stuck:
        return _result(
            "error",
            "remove_existing",
            target,
            f"could not remove {len(stuck)} file(s) Apothem wrote at {target}; "
            "close what holds them or make them writable, then run the command "
            "again",
            backup_path=backup,
            detail={STUCK_FILES: "\n".join(map(_path_text, stuck)), **kept},
        )
    return _result(
        "updated",
        "remove_existing",
        target,
        "removed the files Apothem wrote",
        backup_path=backup,
        detail={**kept_links_detail(kept_links), **kept},
    )


def _why_kept(
    recorded: Mapping[str, LedgerTarget] | None,
    entry: LedgerTarget | None,
    expected: Callable[[Path], dict[str, str] | None] | None,
    *,
    ended: bool,
) -> tuple[str, str]:
    """Return the ``kept_reason`` and message for a target nothing proves.

    See :func:`remove_written` for each case.
    """
    if recorded is None and ended:
        return "no-active-install", _NO_ACTIVE_INSTALL
    if recorded is None:
        return "no-record", "no install record shows whether Apothem wrote it"
    if entry is None:
        return "unrecorded", "the install record does not list it"
    if expected is None:
        return "no-digests", _ROLLBACK_UNCHECKED
    return "no-digests", _EARLIER_RELEASE_UNSHIPPED


#: Why a path stays when no install is recorded here after a finished uninstall.
_NO_ACTIVE_INSTALL = (
    "no install record lists it, and it does not match what this release "
    "writes; remove it by hand if you no longer want it"
)

#: Why a path an earlier release recorded stays when this release writes
#: nothing there to compare it with.
_EARLIER_RELEASE_UNSHIPPED = (
    "the install record (made by an earlier release) cannot show it is "
    "Apothem's, and this release writes nothing there to compare it with; "
    "copy it first if you edited it, then run apothem update, then apothem "
    "uninstall again"
)

#: Why a path an earlier release recorded stays after a rollback, which
#: compares nothing with this release.
_ROLLBACK_UNCHECKED = (
    "an earlier release recorded it without digests, so rollback cannot tell "
    "it is Apothem's, and it stays"
)

#: Why a file an earlier release recorded stays, and the next step.
_EARLIER_RELEASE = (
    "the install record (made by an earlier release) cannot show it is "
    "Apothem's, and it differs from what this release writes; apothem update "
    "overwrites it with this release's file (after a backup), so copy it first "
    "if you edited it, then run apothem update, then apothem uninstall again"
)

#: The same for files kept in a folder.
_EARLIER_RELEASE_FILES = (
    "the install record (made by an earlier release) cannot show they are "
    "Apothem's; apothem update overwrites them with this release's files "
    "(after a backup), so copy any you edited first, then run apothem update, "
    "then apothem uninstall again"
)


def _named_by(target: Path, proof: dict[str, str]) -> bool:
    """Return True when *proof* lists the name of a file at *target*."""
    if target.is_file():
        return "" in proof
    files = _walk_without_links(target).files
    return any(path.relative_to(target).as_posix() in proof for path in files)


def kept_file_warnings(
    results: list[MaterializationResult],
) -> list[MaterializationResult]:
    """Return a warning for each kind of file a removal kept in a folder.

    A file at a name this release writes that differs, under an install an
    earlier release recorded (``kept_differing``), gets the earlier-release
    warning; any other kept file is the operator's or changed
    (``kept_files``). Each warning names its files in ``detail``
    (``kept_files``). A result that is itself a warning already reports its
    target and is skipped, so nothing is reported twice.
    """
    warnings = []
    for result in results:
        if result.outcome == "warning":
            continue
        folder = Path(result.path)
        differing = _paths(result.detail.get(KEPT_DIFFERING, ""))
        kept = _paths(result.detail.get(KEPT_FILES, ""))
        if differing:
            warnings.append(
                _kept_whole(
                    folder,
                    "no-digests",
                    f"{len(differing)} file(s) in it differ from what this "
                    f"release writes; {_EARLIER_RELEASE_FILES}",
                    files=differing,
                )
            )
        if kept:
            warnings.append(
                _kept_whole(
                    folder,
                    "changed",
                    f"{len(kept)} file(s) in it are not what Apothem wrote "
                    "(changed or yours)",
                    files=kept,
                )
            )
    return warnings


def still_written(entry: LedgerTarget) -> bool:
    """Return True when a file *entry* records still has the content Apothem wrote.

    Used as install evidence after an unfinished uninstall: a path that merely
    exists (a settings file the tool recreated, a folder of the operator's)
    proves nothing, unless the record predates digests. A managed-block file
    (``sentinel_merge``) is meant to hold the operator's text beside Apothem's
    block, so the block, not the whole file, is what Apothem wrote: it counts
    while it carries the whole block, both markers. A BEGIN marker left without
    its END does not count: the uninstall leaves that file as it is (see
    :func:`install_driver_blocks.whole_block_left`).
    """
    if entry.mode == "sentinel_merge":
        return whole_block_left(entry)
    proof = _proof(entry)
    if proof is None:
        # An earlier release recorded no digests: the path is the evidence,
        # and the removal that follows still checks each file's content.
        return os.path.lexists(entry.path)
    return bool(_written_now(Path(entry.path), proof))
