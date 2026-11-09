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
from .install_driver_sweep import _link_kept as link_kept
from .install_driver_sweep import kept_link_warnings, links_left_in
from .install_driver_types import MaterializationResult, _path_text, _result

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

#: Kept reasons that leave the uninstall unfinished: files this release cannot
#: show are Apothem's or not, under an install an earlier release recorded
#: without digests (``no-digests``) or with no install record at all
#: (``no-record``). ``apothem update`` records them; a second uninstall then
#: finishes.
UNFINISHED_REASONS: frozenset[str] = frozenset({"no-digests", "no-record"})

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

    It blocks the uninstall while Apothem's own files are behind the link, or,
    under an install an earlier release recorded (*legacy*), files at names
    this release writes: the tool still loads them. Otherwise the target stays
    and the uninstall completes.
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
    warnings report them. An empty folder goes (it holds nothing of anyone's).
    """
    walk = _walk_without_links(target)
    if not walk.files and not walk.links and not walk.unreadable:
        with contextlib.suppress(OSError):
            target.rmdir()
        return None
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
    the uninstall unfinished (``kept_reason`` ``no-digests``): ``apothem
    update`` records it, then a second uninstall finishes. The files kept in
    a folder are named in the result's ``detail`` (``kept_differing`` for
    those, ``kept_files`` for the rest); :func:`kept_file_warnings` reports
    them.
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
        if link is None:
            return target_error
        return _through_link(target, link, proof, legacy=legacy)
    if not target.exists():
        return None
    if proof is None:
        if recorded is None:
            return _kept_whole(
                target,
                "no-record",
                "no install record shows Apothem wrote it",
                files=_files_in(target),
            )
        if entry is None:
            return _kept_whole(
                target,
                "unrecorded",
                "the install record does not list it",
                files=_files_in(target),
            )
        return _kept_whole(
            target, "no-digests", _EARLIER_RELEASE, files=_files_in(target)
        )
    written = _written_now(target, proof)
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
            detail={
                STUCK_FILES: "\n".join(_path_text(path) for path in stuck),
                **_kept_detail(target, kept_files, proof if legacy else None),
            },
        )
    detail = {
        **kept_links_detail(kept_links),
        **_kept_detail(target, kept_files, proof if legacy else None),
    }
    return _result(
        "updated",
        "remove_existing",
        target,
        "removed the files Apothem wrote",
        backup_path=backup,
        detail=detail,
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


def _named_by(
    target: Path, proof: dict[str, str], paths: list[Path] | None = None
) -> bool:
    """Return True when *proof* lists the name of a file at *target* or in *paths*."""
    if target.is_file():
        return "" in proof
    found = _walk_without_links(target).files if paths is None else paths
    return any(path.relative_to(target).as_posix() in proof for path in found)


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


def left_behind(
    results: list[MaterializationResult],
    active: list[LedgerRecord],
    *,
    floor: Path,
) -> list[MaterializationResult]:
    """Return a warning for each path the uninstall kept: links and the user's files."""
    kept = [*kept_link_warnings(results), *kept_file_warnings(results)]
    created = {Path(path) for install in active for path in install.created_dirs}
    named = {result.detail.get("symlink") for result in results}
    kept += [
        warning
        for warning in links_left_in(created, known=kept)
        if warning.path not in named
    ]
    recorded = (target.path for install in active for target in install.targets)
    return [*kept, *links_on_the_way(recorded, floor, known=[*results, *kept])]


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


def still_written(entry: LedgerTarget) -> bool:
    """Return True when a file *entry* records still has the content Apothem wrote.

    Used as install evidence after an unfinished uninstall: a path that merely
    exists (a settings file the tool recreated, a folder of the operator's)
    proves nothing, unless the record predates digests.
    """
    proof = _proof(entry)
    if proof is None:
        # An earlier release recorded no digests: the path is the evidence,
        # and the removal that follows still checks each file's content.
        return os.path.lexists(entry.path)
    return bool(_written_now(Path(entry.path), proof))


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
    ends the install, and a failure to write it raises, so the caller can
    record the uninstall as unfinished instead. An unfinished one keeps the
    install active, so a second run is driven by the same record; it is
    written even when the pass raised, and a failure to write it then does not
    hide the pass's own error. Retention is the caller's to run.
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
