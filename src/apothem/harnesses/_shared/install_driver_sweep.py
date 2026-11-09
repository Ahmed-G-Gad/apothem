# SPDX-License-Identifier: MIT

"""Removal of the stale paths earlier layouts wrote, and its dry-run preview.

The sweep never walks into, deletes through, or backs up through a link. A
symbolic link or a Windows junction at or below a stale path is the
operator's: Apothem writes no links. Such a link is left in place and reported
as a warning that names it.
"""

from __future__ import annotations

import contextlib
import shutil
from pathlib import Path

from .install_driver_backup import backup_existing
from .install_driver_pathsafety import (
    KEPT_LINKS,
    _is_lexically_within,
    _is_link,
    _is_relative_to,
    _link_on_path,
    _normalized,
    _unsafe_symlink,
    _validate_target_path,
    _walk_without_links,
    _write_boundary,
)
from .install_driver_types import (
    MaterializationOutcome,
    MaterializationResult,
    _handle_rm_error,
    _path_text,
    _result,
)


def _preserved_inside(stale: Path, preserve: frozenset[Path]) -> set[Path]:
    """Return the *preserve* paths that live inside the *stale* directory."""
    base = _normalized(stale)
    return {path for path in preserve if path != base and _is_relative_to(path, base)}


def protected_by(stale: Path, protect: frozenset[Path]) -> Path | None:
    """Return the live install target *stale* is another name for, if any.

    A stale path whose resolved location is a current install target, or holds
    one, must not be swept: a link between the earlier folder and the current
    one (a junction on Windows, which the symlink guard does not see) makes the
    stale path a second name for the live folder, and removing it removes the
    live folder with it. A stale path *inside* a current target folder is a
    different case, a stale file in a current folder, and is swept as usual.
    """
    resolved = _normalized(stale)
    for target in sorted(protect):
        if _is_lexically_within(target, resolved):
            return target
    return None


def _link_kept(link: Path) -> MaterializationResult:
    return _result(
        "warning",
        "sweep_stale",
        link,
        f"{link} is a link (a symbolic link or a junction), so it was left in "
        "place; nothing it points to was changed",
    )


def _unreadable_kept(folder: Path) -> MaterializationResult:
    return _result(
        "warning",
        "sweep_stale",
        folder,
        f"could not read {folder}, so it and what it holds were left in place",
    )


def _kept_notes(
    links: list[Path], unreadable: list[Path]
) -> list[MaterializationResult]:
    """Return one warning per link and per unreadable folder a sweep left."""
    return [
        *(_link_kept(link) for link in links),
        *(_unreadable_kept(folder) for folder in unreadable),
    ]


def stale_blocker(
    stale: Path, protect: frozenset[Path], allowed_root: Path
) -> MaterializationResult | None:
    """Return the result that keeps *stale* from being swept, if any.

    The live-target and link checks run before the write-path check, so a link
    that points out of the allowed root is kept with a warning rather than
    refused with an error, the same way in a dry run and a real run.
    """
    live = protected_by(stale, protect)
    link = _link_on_path(stale, allowed_root) if live is not None else None
    if live is not None and link is not None:
        # Kept on every run, and still there after an uninstall, when it points
        # at a folder Apothem no longer fills: the operator removes it.
        return _result(
            "warning",
            "sweep_stale",
            stale,
            f"{stale} reaches the current folder {_normalized(stale)} through "
            f"the link {link}, "
            "so it was left in place; the link stays after an uninstall, so "
            "remove it yourself once nothing uses the old path",
            detail={"live_target": _path_text(live), "link": _path_text(link)},
        )
    if live is not None:
        return _result(
            "unchanged",
            "sweep_stale",
            stale,
            "stale path resolves onto a live install target; left in place",
            detail={"live_target": _path_text(live)},
        )
    if _is_link(stale):
        return _link_kept(stale)
    refused = _validate_target_path(
        stale, allowed_root=allowed_root, operation="sweep_stale"
    )
    through = _unsafe_symlink(stale, allowed_root) if refused is not None else None
    if through is not None:
        # A link above the leftover path (a dotfiles folder linked in, say):
        # removing through it is what the write guard refuses, so the path is
        # kept with a warning, the same way at install, update and uninstall.
        return _result(
            "warning",
            "sweep_stale",
            stale,
            f"{stale} is reached through the link {through}, so it was left in "
            "place: Apothem does not remove anything through a link. Delete it "
            "yourself if nothing uses it",
            detail={"symlink": _path_text(through)},
        )
    return refused


def kept_link_warnings(
    results: list[MaterializationResult],
) -> list[MaterializationResult]:
    """Return one warning per path a removal in *results* left in place.

    A path is a link the removal kept, a folder it could not read, or a file it
    could not remove.
    """
    return [
        _kept_note(Path(kept))
        for result in results
        for kept in result.detail.get(KEPT_LINKS, "").splitlines()
        if kept
    ]


def links_left_in(
    folders: set[Path], *, known: list[MaterializationResult]
) -> list[MaterializationResult]:
    """Return a warning per link directly inside a folder an install created.

    The folder stays after an uninstall because the link is in it, and the
    link may point at a folder that is gone. Links *known* already carry a
    warning and are skipped.
    """
    seen = {result.path for result in known}
    notes = []
    for folder in sorted(folders):
        if not folder.is_dir() or _is_link(folder):
            continue
        try:
            children = sorted(folder.iterdir())
        except OSError:
            continue
        for child in children:
            if _is_link(child) and _path_text(child) not in seen:
                seen.add(_path_text(child))
                notes.append(_link_kept(child))
    return notes


def _kept_note(path: Path) -> MaterializationResult:
    if _is_link(path):
        return _link_kept(path)
    if path.is_dir():
        return _unreadable_kept(path)
    return _result(
        "warning",
        "sweep_stale",
        path,
        f"could not remove {path}, so it was left in place",
    )


def _doomed_and_kept(
    stale: Path, keep: set[Path]
) -> tuple[list[Path], list[MaterializationResult]]:
    """Return the files a sweep of *stale* removes, and a warning per link it keeps.

    A folder the sweep cannot read is kept with a warning as well.
    """
    walk = _walk_without_links(stale)
    doomed = [path for path in walk.files if _normalized(path) not in keep]
    return doomed, _kept_notes(walk.links, walk.unreadable)


def stale_needs_sweep(
    stale: Path,
    preserve: frozenset[Path] = frozenset(),
    protect: frozenset[Path] = frozenset(),
) -> bool:
    """Return True when *stale* exists and holds more than *preserve* paths and links.

    A stale path that is a *protect* path under another name, or is itself a
    link, is never swept.
    """
    if not stale.exists() and not stale.is_symlink():
        return False
    if protected_by(stale, protect) is not None or _is_link(stale):
        return False
    if not stale.is_dir():
        return True
    return bool(_doomed_and_kept(stale, _preserved_inside(stale, preserve))[0])


def preview_stale_sweep(
    stale: Path,
    *,
    preserve: frozenset[Path],
    protect: frozenset[Path],
    allowed_root: Path,
    message: str,
) -> list[MaterializationResult]:
    """Return what :func:`sweep_stale` would report for *stale*, writing nothing."""
    blocker = stale_blocker(stale, protect, allowed_root)
    if blocker is not None:
        return [blocker]
    kept = (
        _doomed_and_kept(stale, _preserved_inside(stale, preserve))[1]
        if stale.is_dir()
        else []
    )
    outcome: MaterializationOutcome = (
        "skipped" if stale_needs_sweep(stale, preserve, protect) else "unchanged"
    )
    return [_result(outcome, "sweep_stale", stale, message), *kept]


def _sweep_around(
    stale: Path, keep: set[Path], *, root: Path, harness_name: str, allowed_root: Path
) -> list[MaterializationResult]:
    """Sweep a stale directory except the current files (*keep*) and links it holds."""
    doomed, kept = _doomed_and_kept(stale, keep)
    if not doomed:
        return [
            _result(
                "unchanged",
                "sweep_stale",
                stale,
                "stale path holds only current files and links",
            ),
            *kept,
        ]
    backup = backup_existing(
        stale, install_root=root, harness_name=harness_name, allowed_root=allowed_root
    )
    for path in doomed:
        # Checked again just before the removal: the walk ran earlier.
        if not _is_link(path):
            with contextlib.suppress(OSError):
                path.unlink()
    folders = sorted(
        _walk_without_links(stale).folders,
        key=lambda path: len(path.parts),
        reverse=True,
    )
    for folder in folders:
        # rmdir removes an empty folder only; a junction would be removed too,
        # so a folder that has become a link since the walk is skipped.
        if _is_link(folder) or any(
            _is_relative_to(path, _normalized(folder)) for path in keep
        ):
            continue
        with contextlib.suppress(OSError):
            folder.rmdir()
    return [
        _result(
            "updated",
            "sweep_stale",
            stale,
            "removed stale files; kept current ones and any links",
            backup_path=backup,
        ),
        *kept,
    ]


def sweep_stale(
    stale_sweep: list[str],
    root: Path,
    *,
    harness_name: str = "manual",
    allowed_root: Path | None = None,
    preserve: frozenset[Path] = frozenset(),
    protect: frozenset[Path] = frozenset(),
) -> list[MaterializationResult]:
    """Remove each stale top-level path under *root* from earlier layouts.

    A stale directory is removed whole with ``shutil.rmtree`` when it holds no
    link and no *preserve* path; files are removed via ``Path.unlink``. Missing
    paths are skipped, so a re-install is idempotent. A stale directory that
    holds a *preserve* path (a file the current layout still writes there, such
    as the profile document) or a link keeps them: only its other files are
    removed, and each link is reported with a warning. A stale path that
    resolves onto, or above, one of the *protect* paths (the current install
    targets) is left in place, with no backup: it is the live folder under
    another name. A stale path that is itself a link is left in place with a
    warning.
    """
    results: list[MaterializationResult] = []
    boundary = _write_boundary(allowed_root, root)
    for legacy in stale_sweep:
        stale = root / legacy
        blocker = stale_blocker(stale, protect, boundary)
        if blocker is not None:
            results.append(blocker)
            continue
        if stale.is_dir():
            keep = _preserved_inside(stale, preserve)
            walk = _walk_without_links(stale)
            if keep or walk.links or walk.unreadable:
                results.extend(
                    _sweep_around(
                        stale,
                        keep,
                        root=root,
                        harness_name=harness_name,
                        allowed_root=boundary,
                    )
                )
                continue
            backup = backup_existing(
                stale,
                install_root=root,
                harness_name=harness_name,
                allowed_root=boundary,
            )
            shutil.rmtree(stale, onerror=_handle_rm_error)
            results.append(
                _result(
                    "updated",
                    "sweep_stale",
                    stale,
                    "removed stale directory",
                    backup_path=backup,
                )
            )
        elif stale.is_file():
            backup = backup_existing(
                stale,
                install_root=root,
                harness_name=harness_name,
                allowed_root=boundary,
            )
            with contextlib.suppress(OSError):  # pragma: no cover
                stale.unlink()
            results.append(
                _result(
                    "updated",
                    "sweep_stale",
                    stale,
                    "removed stale file",
                    backup_path=backup,
                )
            )
        else:
            results.append(
                _result("unchanged", "sweep_stale", stale, "stale path absent")
            )
    return results
