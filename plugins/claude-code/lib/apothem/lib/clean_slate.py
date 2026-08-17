# SPDX-License-Identifier: MIT

"""Clean-slate installer routine: bounded, backed-up, opt-in target removal.

This module is the engine-side single source of truth for the opt-in
destructive install path. It owns the safety contract end to end: a closed
removal target set, an unsafe-root guard, a timestamped backup taken before
any removal, per-target confirmation, a dry-run preview, and a non-interactive
override that must be requested explicitly.

The shell installers forward to ``apothem install --clean``; the CLI handler
calls :func:`run_clean_slate` directly. The routine never reads global process
state for its target home — the caller passes ``home`` explicitly — so it is
fully exercisable against a sandbox directory without ever touching a real
home directory.

The closed removal target set is the four paths under the resolved home:
``~/.claude``, ``~/.codex``, ``~/.agents``, and ``~/.config/apothem``. Every
other ``~/.config`` entry is preserved; the entire ``~/.config`` directory is
never a removal target.
"""

from __future__ import annotations

import shutil
import stat
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

__all__ = [
    "BackupError",
    "CleanSlateError",
    "CleanSlateResult",
    "Clock",
    "ConfirmFn",
    "EchoFn",
    "TargetDisposition",
    "UnsafeRootError",
    "bounded_targets",
    "run_clean_slate",
]

# The closed removal target set: exactly these paths under the resolved home
# directory, and nothing else. Extending the set is a code change, never a
# runtime argument.
_BOUNDED_TARGET_RELPATHS: tuple[tuple[str, ...], ...] = (
    (".claude",),
    (".codex",),
    (".agents",),
    (".config", "apothem"),
)

# The only entry removable directly under ``~/.config``; every other child of
# ``~/.config`` is preserved.
_CONFIG_DIRNAME = ".config"
_CONFIG_REMOVABLE_CHILD = "apothem"

#: A predicate that decides whether a single target should be removed.
ConfirmFn = Callable[[Path], bool]
#: A source of the current time, injected so backups are deterministic in tests.
Clock = Callable[[], datetime]
#: A sink for human-facing progress lines.
EchoFn = Callable[[str], None]


class CleanSlateError(RuntimeError):
    """Base error for the clean-slate routine."""


class UnsafeRootError(CleanSlateError):
    """Raised when a removal target resolves to an unsafe root.

    The guard refuses the home directory itself, a filesystem or drive root,
    an empty or unset path, the entire ``~/.config`` directory, and any
    ``~/.config`` child other than ``apothem``.
    """


class BackupError(CleanSlateError):
    """Raised when the pre-removal backup cannot be written.

    When this is raised no target has been removed: the backup precedes every
    removal, and a backup failure aborts the run.
    """


@dataclass(frozen=True)
class TargetDisposition:
    """The outcome for a single removal target.

    Attributes:
        path: The resolved target path.
        present: Whether the target existed on disk when the run began.
        removed: Whether the target was removed during this run.
        skipped_reason: Why a present target was not removed, when applicable
            (for example, ``"declined"`` when per-target confirmation was
            answered in the negative).
    """

    path: Path
    present: bool
    removed: bool = False
    skipped_reason: str | None = None


@dataclass(frozen=True)
class CleanSlateResult:
    """The aggregate outcome of a clean-slate run.

    Attributes:
        dry_run: Whether the run was a preview that changed nothing on disk.
        backup_dir: The timestamped backup directory, or ``None`` when no
            present target required backing up (or in a dry run).
        dispositions: The per-target outcome, one entry per bounded target.
    """

    dry_run: bool
    backup_dir: Path | None
    dispositions: tuple[TargetDisposition, ...]

    @property
    def removed(self) -> tuple[Path, ...]:
        """The targets removed during this run."""
        return tuple(d.path for d in self.dispositions if d.removed)

    @property
    def present_targets(self) -> tuple[Path, ...]:
        """The targets that existed on disk when the run began."""
        return tuple(d.path for d in self.dispositions if d.present)


def bounded_targets(home: Path) -> list[Path]:
    """Return the closed removal target set under ``home``.

    Args:
        home: The resolved home directory the targets are relative to.

    Returns:
        Exactly four paths — ``~/.claude``, ``~/.codex``, ``~/.agents``, and
        ``~/.config/apothem`` — in that order, and nothing else.
    """
    return [home.joinpath(*parts) for parts in _BOUNDED_TARGET_RELPATHS]


def _unsafe_reason(target: Path, home: Path) -> str | None:
    """Return a refusal reason for an unsafe target, or ``None`` when safe."""
    if not str(target).strip():
        return "refuses empty or unset path"
    resolved = target.expanduser()
    # Reject any parent-directory traversal before the equality checks below:
    # those checks compare the unresolved path, so a ".."-bearing target (e.g.
    # ~/x/.. resolving to the home directory, or ~/.claude/../.. climbing above
    # it) would otherwise slip past them and be removed. Rejecting ".." outright
    # — rather than canonicalizing with resolve() — also preserves the
    # deliberate do-not-follow-symlinks contract this routine upholds.
    if ".." in resolved.parts:
        return f"refuses parent-directory traversal: {resolved}"
    if resolved == Path(resolved.anchor) or resolved.parent == resolved:
        return f"refuses filesystem root: {resolved}"
    if resolved == home:
        return f"refuses home directory itself: {resolved}"
    config_dir = home / _CONFIG_DIRNAME
    if resolved == config_dir:
        return f"refuses entire {config_dir} (would remove unrelated applications)"
    if resolved.parent == config_dir and resolved.name != _CONFIG_REMOVABLE_CHILD:
        return f"refuses non-apothem ~/.config entry: {resolved}"
    return None


def _utcnow() -> datetime:
    """Return the current UTC time."""
    return datetime.now(timezone.utc)


def _timestamp(clock: Clock) -> str:
    """Render an ISO-8601 basic-format UTC timestamp for backup directories."""
    return clock().strftime("%Y%m%dT%H%M%SZ")


def _exists(path: Path) -> bool:
    """Return whether a path exists, counting broken symlinks as present."""
    return path.exists() or path.is_symlink()


def _backup_targets(
    present: Sequence[Path],
    backup_root: Path,
    home: Path,
    clock: Clock,
) -> Path:
    """Copy every present target into a fresh timestamped backup directory.

    Args:
        present: The targets that exist on disk and must be backed up.
        backup_root: The directory the timestamped backup is created under.
        home: The resolved home directory, used to preserve relative layout.
        clock: The time source for the timestamp.

    Returns:
        The created backup directory.

    Raises:
        BackupError: When any part of the backup cannot be written. No target
            is removed when this is raised.
    """
    backup_dir = backup_root / f"clean-slate-{_timestamp(clock)}"
    try:
        backup_dir.mkdir(parents=True, exist_ok=True)
        for src in present:
            try:
                rel: Path = src.relative_to(home)
            except ValueError:
                rel = Path(src.name)
            dest = backup_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            if src.is_dir() and not src.is_symlink():
                shutil.copytree(src, dest, symlinks=True, dirs_exist_ok=True)
            else:
                shutil.copy2(src, dest, follow_symlinks=False)
    except OSError as exc:
        raise BackupError(f"backup write failed under {backup_dir}: {exc}") from exc
    return backup_dir


def _remove_tree(path: Path) -> None:
    """Remove a directory tree, clearing read-only bits on a first failure.

    The retry clears the read-only attribute that Windows sets on some files
    (for example, files under a ``.git`` object store) and which otherwise
    blocks removal.
    """
    try:
        shutil.rmtree(path)
    except OSError:
        for child in sorted(path.rglob("*"), reverse=True):
            try:
                child.chmod(stat.S_IWRITE)
                if child.is_dir() and not child.is_symlink():
                    child.rmdir()
                else:
                    child.unlink(missing_ok=True)
            except OSError:
                continue
        path.chmod(stat.S_IWRITE)
        shutil.rmtree(path)


def _remove_path(path: Path) -> None:
    """Remove a single target, whether a symlink, directory, or file."""
    if path.is_symlink():
        path.unlink(missing_ok=True)
    elif path.is_dir():
        _remove_tree(path)
    else:
        path.unlink(missing_ok=True)


def _default_confirm(path: Path) -> bool:
    """Prompt interactively for confirmation to remove a single target."""
    try:
        reply = input(f"Remove {path}? [y/N] ").strip().lower()
    except EOFError:
        return False
    return reply in {"y", "yes"}


def run_clean_slate(
    home: Path,
    *,
    dry_run: bool = False,
    assume_yes: bool = False,
    interactive: bool = True,
    confirm: ConfirmFn | None = None,
    targets: Sequence[Path] | None = None,
    backup_root: Path | None = None,
    clock: Clock | None = None,
    echo: EchoFn | None = None,
) -> CleanSlateResult:
    """Run the opt-in clean-slate removal with the full safety contract.

    The ordering is fixed: guard, then (for a real run) back up every present
    target, then confirm and remove each target individually. A dry run reports
    the disposition of every target and changes nothing on disk.

    Args:
        home: The resolved home directory the bounded target set is relative
            to. Passed explicitly so the routine is sandbox-testable.
        dry_run: When true, preview the disposition of every target and change
            nothing on disk.
        assume_yes: When true, bypass per-target confirmation (the
            non-interactive opt-in).
        interactive: Whether the caller is attached to an interactive terminal.
            When false and ``assume_yes`` is not set, the run refuses rather
            than auto-confirming.
        confirm: A per-target confirmation predicate. Defaults to an
            interactive prompt.
        targets: An explicit target list, defaulting to :func:`bounded_targets`.
            Provided for tests; production callers use the default.
        backup_root: The directory backups are written under. Defaults to
            ``~/.apothem/backups``, which lies outside the bounded target set.
        clock: The time source for the backup timestamp.
        echo: A sink for human-facing progress lines.

    Returns:
        A :class:`CleanSlateResult` describing the disposition of every target.

    Raises:
        UnsafeRootError: When the home directory or any target is unsafe.
        CleanSlateError: When the run is non-interactive without ``assume_yes``.
        BackupError: When the pre-removal backup cannot be written.
    """
    emit: EchoFn = echo if echo is not None else (lambda _message: None)
    tick: Clock = clock if clock is not None else _utcnow

    if not str(home).strip():
        raise UnsafeRootError("refuses empty or unset home directory")
    home_resolved = home.expanduser()
    if (
        home_resolved == Path(home_resolved.anchor)
        or home_resolved.parent == home_resolved
    ):
        raise UnsafeRootError(f"refuses filesystem root as home: {home_resolved}")

    target_list = (
        [t.expanduser() for t in targets]
        if targets is not None
        else bounded_targets(home_resolved)
    )

    # Unsafe-root guard over every target — refuse before any backup or removal.
    for target in target_list:
        reason = _unsafe_reason(target, home_resolved)
        if reason is not None:
            raise UnsafeRootError(reason)

    if dry_run:
        emit("Clean-slate dry-run — no files will be changed.")
        dispositions = tuple(
            TargetDisposition(path=target, present=_exists(target))
            for target in target_list
        )
        for disposition in dispositions:
            verb = "remove" if disposition.present else "absent"
            emit(f"  {verb}: {disposition.path}")
        return CleanSlateResult(
            dry_run=True, backup_dir=None, dispositions=dispositions
        )

    if not interactive and not assume_yes:
        raise CleanSlateError(
            "refusing destructive clean-slate in a non-interactive context "
            "without an explicit confirmation flag",
        )

    present = [target for target in target_list if _exists(target)]

    backup_dir: Path | None = None
    if present:
        root = (
            backup_root
            if backup_root is not None
            else home_resolved / ".apothem" / "backups"
        )
        backup_dir = _backup_targets(present, root, home_resolved, tick)
        emit(f"Backed up {len(present)} target(s) to {backup_dir}")

    confirm_fn: ConfirmFn = confirm if confirm is not None else _default_confirm
    dispositions_built: list[TargetDisposition] = []
    for target in target_list:
        if not _exists(target):
            dispositions_built.append(TargetDisposition(path=target, present=False))
            continue
        if not assume_yes and not confirm_fn(target):
            dispositions_built.append(
                TargetDisposition(
                    path=target,
                    present=True,
                    removed=False,
                    skipped_reason="declined",
                )
            )
            emit(f"  skipped (declined): {target}")
            continue
        _remove_path(target)
        dispositions_built.append(
            TargetDisposition(path=target, present=True, removed=True)
        )
        emit(f"  removed: {target}")

    return CleanSlateResult(
        dry_run=False,
        backup_dir=backup_dir,
        dispositions=tuple(dispositions_built),
    )
