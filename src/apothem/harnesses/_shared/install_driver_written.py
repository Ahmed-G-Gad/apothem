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
from collections.abc import Iterable, Mapping
from pathlib import Path

from apothem.lib.install_ledger import LedgerTarget

from .install_driver_backup import backup_existing
from .install_driver_digests import file_digest
from .install_driver_pathsafety import (
    _is_link,
    _normalized,
    _unsafe_symlink,
    _validate_target_path,
    _walk_without_links,
    kept_links_detail,
)
from .install_driver_sweep import _link_kept as link_kept
from .install_driver_types import MaterializationResult, _path_text, _result

#: ``detail`` key of a removal: the files it kept because nothing shows Apothem
#: wrote them as they are now (newline-joined paths).
KEPT_FILES = "kept_files"

#: ``detail`` key of a failed removal: the files Apothem wrote that it could
#: not remove (newline-joined paths).
STUCK_FILES = "stuck_files"

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

    Each emptied folder goes, deepest first; a folder that still holds
    something stays.
    """
    for path in written:
        if not _is_link(path):
            with contextlib.suppress(OSError):
                path.unlink()
    walk = _walk_without_links(target)
    for folder in sorted(
        [*walk.folders, target], key=lambda path: len(path.parts), reverse=True
    ):
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
) -> MaterializationResult | None:
    """Remove *target* only as far as the install record shows Apothem wrote it.

    *recorded* maps each path of the install record to its target (``None``
    when there is no record). A file goes only while its SHA-256 matches the
    recorded ``digest``; in a folder only the recorded files whose content
    still matches go, then each folder left empty. Everything else stays and
    is named in the result: a file the operator added or changed, a target
    the record does not list, a record written before digests existed (run
    ``apothem update``, then uninstall again), and anything behind a link.
    The target is backed up before anything is removed.
    """
    allowed = allowed_root or install_root
    entry = None if recorded is None else recorded.get(_path_text(target))
    proof = _proof(entry)
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
            "the install record does not show which files Apothem wrote "
            "(it was made by an earlier release); run apothem update, then "
            "uninstall again",
        )
    written = _written_now(target, proof)
    if not written:
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
    return _result(
        "updated",
        "remove_existing",
        target,
        "removed the files Apothem wrote",
        backup_path=backup,
        detail=detail,
    )


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
        warnings.append(
            _kept_whole(
                folder,
                "changed",
                f"{len(kept)} file(s) in it are not what Apothem wrote "
                "(changed or yours)",
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


def still_written(entry: LedgerTarget) -> bool:
    """Return True when a file *entry* records still has the content Apothem wrote.

    Used as install evidence after an unfinished uninstall: a path that merely
    exists (a settings file the tool recreated, a folder of the operator's)
    proves nothing.
    """
    proof = _proof(entry)
    return proof is not None and bool(_written_now(Path(entry.path), proof))
