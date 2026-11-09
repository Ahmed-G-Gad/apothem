# SPDX-License-Identifier: MIT

"""Path-escape / symlink / case-fold guards and write-root resolution."""

from __future__ import annotations

import os
import sys
from pathlib import Path, PosixPath, WindowsPath

from apothem.lib.links import is_link
from apothem.lib.propagation import USER_LEVEL_PREFIXES, user_home

from .install_driver_types import (
    MaterializationError,
    MaterializationResult,
    MaterializationRun,
    _path_text,
    _result,
)


def _is_relative_to(path: Path, root: Path) -> bool:
    """Return True when *path* is inside *root* after normalization."""
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _normalized(path: Path) -> Path:
    """Return an absolute normalized path without requiring existence."""
    return path.expanduser().resolve(strict=False)


#: The ``lstat`` the case probe reads, kept apart so a test can replace it
#: without replacing ``os.lstat`` for the whole process.
_lstat = os.lstat


def _filesystem_is_case_insensitive(path: Path) -> bool:
    """Best-effort: does the filesystem holding *path* fold case?

    Probes the nearest existing ancestor by re-casing its name: on a volume
    that folds case the swapped-case name is the same entry, by file identity
    (device and inode, read without following a link). A swapped-case name
    that does not exist, or that is a different entry (a sibling folder that
    differs only in case on a case-sensitive volume), means the volume does
    not fold case. Falls back to the platform default (Windows and macOS fold
    case by default; other POSIX volumes do not) when no letter-bearing
    ancestor exists, or when the volume reports no inode numbers.
    """
    base = path
    while not base.exists() and base.parent != base:
        base = base.parent
    name = base.name
    if base.exists() and name and name.swapcase() != name:
        try:
            original = _lstat(base)
            swapped = _lstat(base.with_name(name.swapcase()))
        except OSError:
            return False
        if original.st_ino and swapped.st_ino:
            return os.path.samestat(original, swapped)
    return sys.platform in ("win32", "darwin")


def _parts_within(path: Path, root: Path) -> bool:
    """Return True when *path* is *root* or below it, comparing names by case.

    ``PurePath.relative_to`` ignores case on Windows, which would put a
    sibling that differs only in case inside *root* on a folder where Windows
    keeps case (``fsutil file setCaseSensitiveInfo``, as WSL sets).
    """
    return path.parts[: len(root.parts)] == root.parts


def _within_allowed_root(target: Path, root: Path) -> bool:
    """Return True when *target* is inside *root*, case-fold-aware.

    An exact (case-sensitive, on every platform) containment is tried first.
    When it fails and the
    boundary filesystem folds case, the comparison is retried on case-normalized
    paths so a case variant that resolves to the same location (``~/.Claude`` vs
    ``~/.claude``) is correctly treated as inside the root — without widening the
    boundary on a case-sensitive filesystem, where such a variant is a genuinely
    different location. ``os.path.normcase`` folds case on Windows; the extra
    lower-casing covers macOS's case-insensitive default, where ``normcase`` is a
    POSIX no-op.
    """
    normalized_target = _normalized(target)
    normalized_root = _normalized(root)
    if _parts_within(normalized_target, normalized_root):
        return True
    if not _filesystem_is_case_insensitive(normalized_root):
        return False
    folded_target = Path(os.path.normcase(str(normalized_target)).lower())
    folded_root = Path(os.path.normcase(str(normalized_root)).lower())
    return _is_relative_to(folded_target, folded_root)


def _existing_chain(path: Path, floor: Path) -> list[Path]:
    """Return existing path components from *path* upward to *floor*."""
    expanded = path.expanduser()
    probe = expanded if os.path.lexists(expanded) else expanded.parent
    floor_expanded = floor.expanduser()
    chain: list[Path] = []
    while True:
        if os.path.lexists(probe):
            chain.append(probe)
        if _normalized(probe) == _normalized(floor_expanded):
            break
        parent = probe.parent
        if parent == probe:
            break
        probe = parent
    return chain


def _lexical_key(path: Path) -> str:
    """Return *path* normalized without resolving symlinks, case-folded where the OS is."""
    return os.path.normcase(os.path.normpath(str(path)))


def _is_lexically_within(path: Path, parent: Path) -> bool:
    """Return True when *path* is *parent* or below it, by name only."""
    key, base = _lexical_key(path), _lexical_key(parent)
    return key == base or key.startswith(base.rstrip(os.sep) + os.sep)


def _linkable_ancestors(
    path: Path, floor: Path, *, project_floor: bool = False
) -> list[Path]:
    """Return the folders a link at or above which *path* may cross.

    Dotfile managers link ``~/.config`` or ``~/.agents`` into a dotfiles
    folder. When *floor* is the user home, a link at or above one of the
    manifest's closed user-level folders (``~/.agents/skills``,
    ``~/.config/apothem/rules``, ...) is allowed: the write guard has already
    confirmed the resolved path stays in the home. When the install root is
    below ``~/.config`` (OpenCode's folder, or a ``CODEX_HOME`` there), *floor*
    is at or below the folder ``~/.config`` leads to, and a link at
    ``~/.config`` is allowed when that folder is inside the home. A link below
    either folder (a skill folder, the install root, a file in it) is still
    refused. The walk stops at *floor*, so a link above it is not examined.

    A *project_floor* (the boundary is a project root, see
    :func:`_allowed_write_root`) gets no ``~/.config`` exemption: there a link
    at ``~/.config`` is the install root itself, which is refused like any
    other linked project root.
    """
    home = user_home()
    bases: list[Path] = []
    normalized_floor = _normalized(floor)
    if normalized_floor == _normalized(home):
        bases = [
            base
            for base in (home / prefix for prefix in USER_LEVEL_PREFIXES)
            if _is_lexically_within(path, base)
        ]
    config = home / ".config"
    if (
        _is_lexically_within(path, config)
        and not project_floor
        and _is_relative_to(normalized_floor, _normalized(config))
        and _within_allowed_root(config, home)
    ):
        bases.append(config)
    return bases


#: The one link test the write guard, the sweeps and the reversal share (see
#: :func:`apothem.lib.links.is_link`); the clean-slate routine uses it too.
_is_link = is_link


def _walk_without_links(top: Path) -> tuple[list[Path], list[Path], list[Path]]:
    """Return the files, folders and links below *top*, never entering a link.

    ``Path.rglob`` enters a Windows junction (``is_symlink()`` is False for
    one), so a walk that deletes what it finds would delete through it.
    """
    files: list[Path] = []
    folders: list[Path] = []
    links: list[Path] = []
    pending = [top]
    while pending:
        try:
            entries = sorted(os.scandir(pending.pop()), key=lambda e: e.name)
        except OSError:
            continue
        for entry in entries:
            path = Path(entry.path)
            if _is_link(path):
                links.append(path)
            elif entry.is_dir(follow_symlinks=False):
                folders.append(path)
                pending.append(path)
            else:
                files.append(path)
    return files, folders, links


def _unsafe_symlink(
    path: Path, floor: Path, *, project_floor: bool = False
) -> Path | None:
    """Return the first symlink or junction in the write path, if any.

    A link at or above a user-level folder, or at ``~/.config`` for an install
    root below it (see :func:`_linkable_ancestors`), does not count. Nor does
    the home folder itself or a folder above it, as the home is spelled (a
    profile moved to another drive behind a junction): the caller has already
    checked that the resolved path stays inside the resolved allowed root, so
    such a link cannot lead the write out of the home. *project_floor* says
    *floor* is a project root (see :func:`_linkable_ancestors`).
    """
    home = user_home()
    bases = _linkable_ancestors(path, floor, project_floor=project_floor)
    for candidate in _existing_chain(path, floor):
        if _is_lexically_within(home, candidate):
            continue
        if _is_link(candidate) and not any(
            _is_lexically_within(base, candidate) for base in bases
        ):
            return candidate
    return None


def _names_same_folder(first: Path, second: Path) -> bool:
    """Return True when *first* and *second* name one folder.

    When both exist they are compared by file identity, which also matches a
    change of case on a case-insensitive volume, a short (8.3) name, a bind
    mount, a link or a junction. Otherwise, or when the filesystem reports no
    inode numbers (some network and FUSE mounts do), their resolved paths are
    compared.
    """
    try:
        stats = [first.stat(), second.stat()]
    except OSError:
        stats = []
    if stats and all(item.st_ino for item in stats):
        return os.path.samestat(stats[0], stats[1])
    return _normalized(first) == _normalized(second)


def _spelled_inside_home(path: Path) -> bool:
    """Return True when *path*, as spelled, passes through the home folder.

    One of its spelled ancestors (or *path* itself) is the home folder, by
    file identity: the home as it is spelled, resolved, in another case or by
    its short name.
    """
    home = user_home()
    return any(_names_same_folder(folder, home) for folder in (path, *path.parents))


def _link_leaving_home(root: Path) -> Path | None:
    """Return the link that leads *root*, spelled inside the home, out of it.

    ``None`` when *root* is spelled outside the home (the operator named that
    folder, through ``XDG_CONFIG_HOME`` or ``CODEX_HOME``), when it stays
    inside the home once resolved, or when no link sits between it and the
    home (a bind mount or a macOS firmlink naming the home another way leads
    nowhere else). The write guard stops its walk at the folder above the
    install root, so a link higher up (``CODEX_HOME=~/a/b/codex`` with ``~/a``
    leading out of the home) is found here. Of the links on the way up, the
    one named is the highest that leads out of the home itself, not a link
    below it that stays inside (``~/a`` leading to ``~/c`` while ``~/a/b``
    leads out names ``~/a/b``).
    """
    home = user_home()
    if not _spelled_inside_home(root) or _within_allowed_root(root, home):
        return None
    first: Path | None = None
    leading_out: Path | None = None
    for folder in (root, *root.parents):
        if _names_same_folder(folder, home):
            break
        if not _is_link(folder):
            continue
        first = first or folder
        if not _within_allowed_root(folder, home):
            leading_out = folder
    return leading_out or first


def _first_link(root: Path) -> Path | None:
    """Return the first link at or above *root*, read without resolving any."""
    for folder in (root, *root.parents):
        try:
            if _is_link(folder):
                return folder
        except OSError:
            return None
    return None


def link_leaving_home_refusal(
    root: Path, *, operation: str
) -> MaterializationResult | None:
    """Return the error result for a link that leads *root* out of the home.

    ``None`` when there is no such link (see :func:`_link_leaving_home`) or a
    folder on the way cannot be read; the result's ``detail["symlink"]``
    names the link. A link loop counts as such a link where resolving it
    raises :class:`RuntimeError` (Python 3.10 to 3.12): the first link found
    is named. From Python 3.13 resolving a loop does not raise, so this check
    names no link for it; the write that follows cannot pass through the loop
    and stops there.
    """
    try:
        link = _link_leaving_home(root)
    except RuntimeError:
        link = _first_link(root) or root
    except (OSError, ValueError):
        return None
    if link is None:
        return None
    return _result(
        "error",
        operation,
        root,
        "target path crosses a symlink",
        detail={
            "symlink": _path_text(link),
            "leads_to": _leads_to(link),
            "fix": (
                f"Replace the link {link} with a real folder, or make it lead "
                "to a folder inside your home directory. A folder you name by "
                "its own path outside your home directory is followed."
            ),
        },
    )


def _leads_to(link: Path) -> str:
    """Return where *link* leads, as display text; the link itself for a loop."""
    try:
        return _path_text(_normalized(link))
    except (OSError, RuntimeError, ValueError):
        return _path_text(link)


def link_refusal_text(refusal: MaterializationResult) -> str:
    """Return ``(<link> leads outside the home folder, to <where>)`` for *refusal*.

    *refusal* is a result from :func:`link_leaving_home_refusal`; the text
    names the link and the folder it leads to, for an error message.
    """
    link = refusal.detail.get("symlink", refusal.path)
    leads_to = refusal.detail.get("leads_to")
    where = f", to {leads_to}" if leads_to and leads_to != link else ""
    return f"({link} leads outside the home folder{where})"


def link_refusal_reason_and_fix(
    result: MaterializationResult,
) -> tuple[str, str] | None:
    """Return the CLI reason and fix for a *result* refused at a link.

    ``None`` when *result* names no link (``detail["symlink"]``). The reason
    names the link and where it leads; "target path crosses a symlink" alone
    leaves the operator searching the path for it. A refusal from
    :func:`link_leaving_home_refusal` carries its own fix and says the link
    leads outside the home; any other link refusal is told to replace the
    link with a real folder.
    """
    link = result.detail.get("symlink")
    if not link:
        return None
    leads_to = result.detail.get("leads_to")
    reason = f"{result.message}: {link} is a link"
    if leads_to and leads_to != link:
        reason += f" to {leads_to}"
    own_fix = result.detail.get("fix")
    if own_fix:
        return f"{reason}, outside your home directory", own_fix
    return (
        reason,
        f"Replace the link {link} with a real folder, then run the command again.",
    )


def refuse_link_leaving_home(
    harness_name: str,
    root: Path,
    *,
    operation: str,
    uninstall: bool = False,
    dry_run: bool = False,
) -> None:
    """Raise when a link leads the install root *root* out of the home.

    Run before an install, update or uninstall of a harness whose root an
    environment variable moves (see :func:`_link_leaving_home`); nothing is
    written or removed. A link loop on the way up (Python 3.10 to 3.12 raise
    :class:`RuntimeError` resolving one) is refused too, naming the first link
    found. A folder that cannot be read is left to the write guard, which
    still checks every target. Read-only commands never call this. An
    uninstall's message also carries the fix, since the uninstall output shows
    only the message.

    Raises:
        MaterializationError: When there is such a link, or a link loop.
    """
    refusal = link_leaving_home_refusal(root, operation=operation)
    if refusal is None:
        return
    verb = "uninstall refused" if uninstall else "materialization write failed"
    message = f"{verb}: {refusal.message} {link_refusal_text(refusal)}"
    if uninstall:
        message += f". {refusal.detail['fix']}"
    raise MaterializationError(
        message,
        MaterializationRun(harness=harness_name, dry_run=dry_run, results=(refusal,)),
    )


def _ensure_directory(path: Path, *, operation: str) -> MaterializationResult | None:
    """Create *path* and its parents; return an error result when that is impossible.

    The result names the existing path that is not a folder (``~/.agents``
    left as a file, say) when that is what blocks the install, so the operator
    sees which path to move.
    """
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        blocker = next(
            (
                item
                for item in (path, *path.parents)
                if item.exists() and not item.is_dir()
            ),
            None,
        )
        reason = (
            f"{blocker} exists and is not a folder; move it, then run the command again"
            if blocker is not None
            else str(exc)
        )
        return _result(
            "error",
            operation,
            path,
            f"could not create {path}: {reason}",
            detail={"blocking_path": _path_text(blocker)} if blocker else None,
        )
    return None


def _prepare_target_directory(
    path: Path, *, allowed_root: Path, operation: str
) -> MaterializationResult | None:
    """Validate *path* against *allowed_root*, then create it; an error result if either fails."""
    return _validate_target_path(
        path, allowed_root=allowed_root, operation=operation
    ) or _ensure_directory(path, operation=operation)


def _root_for(harness_root: Path | None, project_root: Path | None) -> Path:
    """Return the active install root, preferring the user-scope harness root."""
    root = harness_root if harness_root is not None else project_root
    if root is None:
        raise ValueError("install driver requires either harness_root or project_root")
    return root


if sys.platform == "win32":
    _ConcretePath = WindowsPath
else:
    _ConcretePath = PosixPath


class _ProjectFloor(_ConcretePath):
    """A write boundary that is a project root, not the folder above one.

    A harness root's boundary is the folder above it, so a link at that
    folder sits above the install root; a project root's boundary is the
    project root itself, so a link there is the install root. The two cannot
    be told apart by path, and a link at ``~/.config`` is allowed only above
    an install root (see :func:`_linkable_ancestors`), so the boundary
    carries its kind. It is an ordinary path everywhere else, and the paths
    derived from it (``resolve()``, ``/``) keep the kind.
    """


def _allowed_write_root(harness_root: Path | None, project_root: Path | None) -> Path:
    """Return the filesystem boundary allowed for resolved install targets.

    A project root's boundary is returned as a :class:`_ProjectFloor`, so the
    write guard knows it is a project root (see :func:`_validate_target_path`).
    """
    if project_root is not None:
        return _ProjectFloor(_normalized(project_root))
    if harness_root is None:
        raise ValueError("install driver requires either harness_root or project_root")
    return _normalized(harness_root).parent


def _validate_target_path(
    target: Path,
    *,
    allowed_root: Path,
    operation: str,
) -> MaterializationResult | None:
    """Return an error result when a resolved target is unsafe.

    An *allowed_root* from :func:`_allowed_write_root` for a project root is
    a :class:`_ProjectFloor`, which gets no ``~/.config`` link exemption.
    """
    project_floor = isinstance(allowed_root, _ProjectFloor)
    normalized_target = _normalized(target)
    normalized_root = _normalized(allowed_root)
    if not _within_allowed_root(normalized_target, normalized_root):
        return _result(
            "error",
            operation,
            target,
            "target escapes the allowed materialization root",
            detail={"allowed_root": _path_text(normalized_root)},
        )
    symlink = _unsafe_symlink(target, normalized_root, project_floor=project_floor)
    if symlink is not None:
        return _result(
            "error",
            operation,
            target,
            "target path crosses a symlink",
            detail={"symlink": _path_text(symlink), "leads_to": _leads_to(symlink)},
        )
    return None


#: Path segment naming Apothem's own working subtree beneath a harness or
#: project root (mirrors ``_APOTHEM_SUBTREE`` in :mod:`apothem.lib.data_home`,
#: and the ``.apothem/`` segment the manifest's target templates hardcode). No
#: vendor creates this directory, so a target inside it exists only because an
#: Apothem install put it there.
_APOTHEM_SUBTREE: str = ".apothem"


def _holds_content(target: Path) -> bool:
    """Return True when *target* is a file, or a directory holding some file.

    An empty directory is NOT content. Uninstall reverses tree targets
    child-by-child (so operator-authored siblings survive) and leaves the
    directory itself in place, so every Apothem tree target outlives an
    uninstall as an empty shell. Testing mere existence would report a fully
    uninstalled harness as still installed.
    """
    if _is_link(target):
        return False
    if target.is_file():
        return True
    if not target.is_dir():
        return False
    return bool(_walk_without_links(target)[0])


def _stale_path_proves_install(stale: Path) -> bool:
    """Return True when an earlier layout's folder still holds Apothem's files.

    The manifest's ``stale-sweep`` list names paths earlier releases wrote. One
    that holds content under the Apothem-owned ``.apothem/`` subtree (or sits
    inside it) is the same kind of evidence as a current target there: an
    install exists in the earlier layout, and an uninstall or update has work
    to do on it, even when the current layout's targets are gone. A stale
    path that is a link (a junction on Windows) is the operator's, not
    Apothem's, and is not followed.
    """
    if _is_link(stale):
        return False
    if _APOTHEM_SUBTREE in stale.parts:
        return _holds_content(stale)
    return _holds_content(stale / _APOTHEM_SUBTREE)
