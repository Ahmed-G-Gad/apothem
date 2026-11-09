# SPDX-License-Identifier: MIT

"""Links that lead an install root, spelled inside the home, out of it.

The write guard (:mod:`.install_driver_pathsafety`) checks each target below
an install root. This module checks the folders above the root: a link there
that leads out of the home stops an install, update, uninstall or rollback
before anything is written, unless the operator named the folder outside the
home by its own path. It also builds the refusal texts the CLI shows.
"""

from __future__ import annotations

import os
from pathlib import Path

from apothem.lib.propagation import user_home

from .install_driver_pathsafety import (
    LINK_FIX_LEAD,
    _is_link,
    _leads_to,
    _normalized,
    _within_allowed_root,
)
from .install_driver_types import (
    MaterializationError,
    MaterializationResult,
    MaterializationRun,
    _path_text,
    _result,
)


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

    ``None`` when *result* names no link (``detail["symlink"]``). A refusal
    from :func:`link_leaving_home_refusal` carries its own fix; its reason
    names the link, where it leads, and that this is outside the home. A
    write-guard refusal's message already names the kind of link, the link
    and where it leads, then its fix after
    :data:`~.install_driver_pathsafety.LINK_FIX_LEAD`: the reason is the part
    before it, so the fix is given once.
    """
    link = result.detail.get("symlink")
    if not link:
        return None
    leads_to = result.detail.get("leads_to")
    named = f"{link} is a link"
    if leads_to and leads_to != link:
        named += f" to {leads_to}"
    own_fix = result.detail.get("fix")
    if own_fix:
        return f"{result.message}: {named}, outside your home directory", own_fix
    reason, lead, _ = result.message.partition(LINK_FIX_LEAD)
    return (
        reason if lead else f"{result.message}: {named}",
        f"Replace the link {link} with a real folder that holds the same files, "
        "then run the command again.",
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
