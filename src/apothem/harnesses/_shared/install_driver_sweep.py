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
    _is_lexically_within,
    _is_link,
    _is_relative_to,
    _normalized,
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


def stale_blocker(
    stale: Path, protect: frozenset[Path], allowed_root: Path
) -> MaterializationResult | None:
    """Return the result that keeps *stale* from being swept, if any.

    The live-target and link checks run before the write-path check, so a link
    that points out of the allowed root is kept with a warning rather than
    refused with an error, the same way in a dry run and a real run.
    """
    live = protected_by(stale, protect)
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
    return _validate_target_path(
        stale, allowed_root=allowed_root, operation="sweep_stale"
    )


def _doomed_and_links(stale: Path, keep: set[Path]) -> tuple[list[Path], list[Path]]:
    """Return the files a sweep of *stale* removes, and the links it keeps."""
    files, _folders, links = _walk_without_links(stale)
    return [path for path in files if _normalized(path) not in keep], links


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
    return bool(_doomed_and_links(stale, _preserved_inside(stale, preserve))[0])


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
    links = _walk_without_links(stale)[2] if stale.is_dir() else []
    outcome: MaterializationOutcome = (
        "skipped" if stale_needs_sweep(stale, preserve, protect) else "unchanged"
    )
    return [
        _result(outcome, "sweep_stale", stale, message),
        *(_link_kept(link) for link in links),
    ]


def _sweep_around(
    stale: Path, keep: set[Path], *, root: Path, harness_name: str, allowed_root: Path
) -> list[MaterializationResult]:
    """Sweep a stale directory except the current files (*keep*) and links it holds."""
    doomed, links = _doomed_and_links(stale, keep)
    kept = [_link_kept(link) for link in links]
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
        _walk_without_links(stale)[1], key=lambda path: len(path.parts), reverse=True
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
            if keep or _walk_without_links(stale)[2]:
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
