# SPDX-License-Identifier: MIT

"""The ``install --clean`` phase: clean-slate removal, then the profile restore.

``_clean_slate_phase`` runs the bounded clean-slate removal before a fresh
install and writes the shared profile back when that removal took it. The
restore is checked like every other profile write: it is never written through
a link that leads out of the home (see ``_refuse_profile_outside_home``), and a
profile the removal did not take is left as it is. A restore that cannot be
written names the copy that still holds the profile, and so does a removal
that stops partway. Patchable-helper call sites resolve through the
``apothem.cli`` package (``_pkg``).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

import apothem.cli as _pkg
from apothem.cli._helpers import _CliUserError, _refuse_profile_outside_home
from apothem.lib.atomic_io import write_bytes_atomically
from apothem.lib.clean_slate import (
    CleanSlateError,
    CleanSlateResult,
    LinkLeavingHomeError,
    RemovalError,
    UnsafeHomeError,
    run_clean_slate,
)
from apothem.lib.links import is_link
from apothem.lib.propagation import user_home

if TYPE_CHECKING:
    from apothem.cli._materialize import _RunContext


def _refused_error(exc: CleanSlateError) -> dict[str, object]:
    """Return the CLI error for a clean-slate run that refused to start."""
    if isinstance(exc, LinkLeavingHomeError):
        fix = (
            f"Replace the link {exc.link} with a real folder, or make it lead "
            "to a folder inside your home directory, then run the command again."
        )
    elif isinstance(exc, UnsafeHomeError):
        fix = (
            "Set your home directory (HOME, or USERPROFILE on Windows) to your "
            "own folder, not the root of a drive or file system and not a link "
            "that leads to one or cannot be followed, then run the command again."
        )
    else:
        fix = (
            "Re-run interactively, pass --yes for non-interactive use, "
            "or correct the unsafe target before retrying."
        )
    return _CliUserError(
        code="clean_slate.refused",
        message="Clean-slate removal was refused.",
        field="clean",
        reason=str(exc),
        fix=fix,
    ).to_dict()


def _profile_copy(
    profile_path: Path, profile_bytes: bytes, clean_result: CleanSlateResult
) -> Path | None:
    """Return a file that holds the profile the restore did not write back.

    The clean-slate backup copied the profile under its path relative to the
    home. When that copy is missing or differs (the profile was reached
    through another spelling), the bytes read before the removal are written
    beside the backup instead. ``None`` when neither is possible.
    """
    backup_dir = clean_result.backup_dir
    if backup_dir is None:
        return None
    try:
        copy = backup_dir / profile_path.relative_to(Path.home())
        held = copy.read_bytes() == profile_bytes
    except (OSError, ValueError):
        held = False
    if held:
        return copy
    spare = backup_dir / f"{profile_path.name}.not-restored"
    try:
        write_bytes_atomically(spare, profile_bytes)
    except OSError:
        return None
    return spare


def _is_the_home(folder: Path, home: Path) -> bool:
    """Return True when *folder* is the entry *home* names, links not followed.

    The two are compared by file identity read with ``lstat``, which also
    matches the home in another case or by its short (8.3) name; a link
    elsewhere that leads to the home is not the home. Where the filesystem
    reports no inode numbers, or a folder cannot be read, the spellings are
    compared instead.
    """
    try:
        stats = [os.lstat(folder), os.lstat(home)]
    except OSError:
        stats = []
    if stats and all(item.st_ino for item in stats):
        return os.path.samestat(stats[0], stats[1])
    return os.path.normcase(str(folder)) == os.path.normcase(str(home))


def _link_on_path(path: Path) -> Path | None:
    """Return the nearest link at or above *path*, below the home folder.

    The home is the one the path guards use (``user_home()``). The home
    folder and the folders above it are not examined: a profile moved to
    another drive behind a junction at the home is written there as before.
    """
    home = user_home()
    for folder in (path, *path.parents):
        if _is_the_home(folder, home):
            return None
        if is_link(folder):
            return folder
    return None


def _copy_back_fix(copy: Path, profile_path: Path) -> str:
    """Return the fix for a restore whose write failed: where to copy *copy*.

    A path reached through a link names the file the link leads to, not the
    path whose write just failed. The link is called broken only when the
    folder it leads to is gone (the clean-slate step removed it); when that
    folder exists and only a folder below it is missing, the fix names the
    missing folder to create.
    """
    keep = "or pass --profile PATH with a copy you keep elsewhere."
    saved = f"Your profile is saved at {copy}."
    link = _link_on_path(profile_path)
    if link is None:
        return f"{saved} Copy it back to {profile_path}, {keep}"
    leads_to = Path(os.path.realpath(link))
    if not leads_to.exists():
        return (
            f"{saved} The link {link} is broken: it leads to {leads_to}, which "
            "does not exist. Create that folder or replace the link with a real "
            f"folder, then copy the file back to {profile_path}, {keep}"
        )
    real = Path(os.path.realpath(profile_path))
    where = f"where the link {link} leads"
    if real.parent.is_dir():
        return f"{saved} Copy it back to {real}, {where}, {keep}"
    return (
        f"{saved} Create the folder {real.parent}, then copy it back to "
        f"{real}, {where}, {keep}"
    )


def _restore_failed(
    run: _RunContext,
    clean_result: CleanSlateResult,
    profile_bytes: bytes,
    *,
    code: str,
    reason: str,
) -> None:
    """Emit the error for a profile that was removed and not written back.

    A restore refused at a link (``clean_slate.profile_restore_refused``) is
    not told to copy the profile back to its path: that copy would go through
    the same link.
    """
    copy = _profile_copy(run.profile_path, profile_bytes, clean_result)
    if copy is None:
        fix = (
            "Restore the profile from the clean-slate backup directory reported above."
        )
    elif code == "clean_slate.profile_restore_refused":
        fix = (
            f"Your profile is saved at {copy}. Do not copy it back through the "
            "link named above. Replace that link with a real folder and copy "
            "the file back, or copy it to a folder outside your home directory "
            "and pass --profile PATH with that path."
        )
    else:
        fix = _copy_back_fix(copy, run.profile_path)
    run.fail(
        _CliUserError(
            code=code,
            message="Clean-slate removal ran, but the profile could not be "
            "written back.",
            field="clean",
            reason=reason,
            fix=fix,
        ).to_dict()
    )


def _restore_profile(
    run: _RunContext, profile_bytes: bytes, clean_result: CleanSlateResult
) -> bool:
    """Write the removed profile back; return False once an error is emitted.

    This restore is the identity safety net, so it gets the same care as every
    other profile write: a link that leads the profile out of the home refuses
    it (see ``_refuse_profile_outside_home``), and it is written atomically,
    since the in-memory bytes and the timestamped backup are the only copies
    left. A raw write would surface a disk-full or permission failure as a
    traceback with the canonical path already empty, and an interruption
    mid-write would leave it truncated.
    """
    try:
        _refuse_profile_outside_home(run.profile_path)
    except _CliUserError as exc:
        _restore_failed(
            run,
            clean_result,
            profile_bytes,
            code="clean_slate.profile_restore_refused",
            reason=exc.reason,
        )
        return False
    try:
        write_bytes_atomically(run.profile_path, profile_bytes)
    except OSError as exc:
        _restore_failed(
            run,
            clean_result,
            profile_bytes,
            code="clean_slate.profile_restore_failed",
            reason=str(exc),
        )
        return False
    return True


def _removal_failed(
    run: _RunContext, exc: RemovalError, profile_bytes: bytes | None
) -> None:
    """Emit the error for a removal that stopped partway (a locked file, say).

    The profile is written back first when the removal already took it, so
    the error never leaves the operator without it; a restore that fails
    emits its own error, which names the copy.
    """
    partial = CleanSlateResult(
        dry_run=False, backup_dir=exc.backup_dir, dispositions=()
    )
    if (
        profile_bytes is not None
        and not os.path.lexists(run.profile_path)
        and not _restore_profile(run, profile_bytes, partial)
    ):
        return
    run.fail(
        _CliUserError(
            code="clean_slate.removal_failed",
            message="Clean-slate removal stopped partway.",
            field="clean",
            reason=str(exc),
            fix=(
                f"Every removed folder was backed up to {exc.backup_dir} first. "
                "Close any program that holds a file there, then run the "
                "command again."
            ),
        ).to_dict()
    )


def _clean_slate_phase(
    run: _RunContext, *, assume_yes: bool
) -> tuple[bool, CleanSlateResult | None]:
    """Run the opt-in clean-slate removal, then restore the profile file.

    It runs after the profile is loaded into memory and before any fresh
    materialization. The default profile is inside one of the bounded removal
    targets (``~/.config/apothem``), so its bytes are captured here and written
    back when the removal took them: the shared profile is the operator's
    identity source of truth, not stale install state, and the timestamped
    backup preserves every removed target for recovery. A profile the removal
    left in place (a ``--profile PATH`` elsewhere, or a removal declined at the
    prompt) is not written at all; a removal that stops partway still writes
    it back (see :func:`_removal_failed`). Returns ``(proceed, result)``;
    *proceed* is false once an error has been emitted.
    """
    profile_path = run.profile_path
    profile_bytes = profile_path.read_bytes() if profile_path.is_file() else None
    try:
        clean_result = run_clean_slate(
            Path.home(),
            dry_run=run.dry_run,
            assume_yes=assume_yes,
            # Use the patchable seam (not raw sys.stdin.isatty()) so the
            # clean-slate interactivity gate is test-reachable, matching the
            # blast-radius confirmation.
            interactive=_pkg._stdin_is_interactive(),
            echo=(run.con.print if run.fmt != "json" else None),
        )
    except RemovalError as exc:
        _removal_failed(run, exc, profile_bytes)
        return False, None
    except CleanSlateError as exc:
        run.fail(_refused_error(exc))
        return False, None
    # A clean dry run falls through to the materialization preview: the
    # operation previews both phases (removals, then fresh writes), and JSON
    # mode keeps its single-envelope contract — the removal preview rides the
    # envelope's "clean" key instead of truncating the run.
    if run.dry_run or profile_bytes is None or os.path.lexists(profile_path):
        return True, clean_result
    return _restore_profile(run, profile_bytes, clean_result), clean_result
