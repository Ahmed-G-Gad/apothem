# SPDX-License-Identifier: MIT

"""User-level install folders that several installs share.

Some manifest targets sit in the user home whatever the install root is: the
skills folders (``~/.agents/skills/`` and the vendor folders such as
``~/.kiro/skills/``) and the rules and templates corpus
(``~/.config/apothem/``). The manifest spells them ``${USER_HOME}/...``. Several
installs write the same absolute folder, so three rules keep them coherent:

* Every install that writes such a folder emits the same bytes. The skill
  folders use one emission (:data:`SHARED_EMISSION`) whichever harness writes
  them, so installs never rewrite each other's output.
* The install ledger is the reference counter. An install holds a folder while
  its current record lists the folder's path. An uninstall removes a folder
  only when no other install still holds it (:class:`UserLevelGate`).
* The folder is written under a lock from the first write to the ledger record
  (:func:`shared_scope`), because the holders are read from the ledger.

This module is a leaf of the driver: it imports only the lower layers, so the
modules that write, remove and verify can all use it. The removal itself is a
callback the lifecycle supplies.
"""

from __future__ import annotations

import contextlib
import os
import shutil
from collections.abc import Callable, Iterable, Iterator
from contextlib import AbstractContextManager, contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

from apothem.lib import install_ledger
from apothem.lib.harness_registry import (
    SUPPORTED_PACKAGE_KEYS,
    public_id_for_package_key,
)
from apothem.lib.install_ledger import LedgerRecord
from apothem.lib.propagation import (
    HarnessRules,
    InstallEntry,
    resolve_target,
    user_home,
    user_level_prefix,
)

from .install_driver_pathsafety import (
    _allowed_write_root,
    _normalized,
    _validate_target_path,
    _within_allowed_root,
)
from .install_driver_sharedlock import (
    locked_for_harness,
    rules_for,
    shared_scope,
    writes_user_level,
)
from .install_driver_types import (
    STAGING_SUFFIX,
    MaterializationResult,
    _handle_rm_error,
    _result,
)

#: The emission identity every user-level skill folder is rendered with,
#: whichever harness writes it. It is passed to the emission calls only;
#: backups, results and the ledger keep the real harness name.
SHARED_EMISSION: Final[str] = "shared_skills"

#: The top-level ``SKILL.md`` keys the shared emission leaves. The set is the
#: standard core (``name``, ``description``, ``allowed-tools``, ``metadata``)
#: plus the three Claude Code keys the corpus sets; ``allowedTools`` is never
#: emitted because Qwen Code throws on a non-array value.
SHARED_TOPLEVEL_KEYS: Final[frozenset[str]] = frozenset(
    {
        "name",
        "description",
        "user-invocable",
        "disable-model-invocation",
        "allowed-tools",
        "argument-hint",
        "metadata",
    }
)

#: Backup-tree segment for files taken from the user home during an install
#: whose own boundary is not the home (a project-scope install, or a Codex
#: root that is not ``~/.codex``). A project may hold its own ``.agents/skills/``,
#: so a home backup must never share a key with a project backup.
HOME_BACKUP_SEGMENT: Final[str] = "__home__"

#: Operations a user-level skill write can have.
SKILL_MODES: Final[frozenset[str]] = frozenset({"native_skills", "command_skills"})


def path_key(path: str | Path) -> str:
    """Return the comparison key of *path*: normalized, case-folded where the OS is.

    Lexical on purpose. Ledger records written before ``${USER_HOME}`` name
    Codex's skills as ``<root>/.codex/../.agents/skills/x``, and
    ``normpath`` folds that to the same key as ``<home>/.agents/skills/x``.
    The symlink-resolving :func:`_normalized` would not, and a symlink in the
    path is refused by the write guards anyway.
    """
    return os.path.normcase(os.path.normpath(str(path)))


def same_location(left: str | Path, right: str | Path) -> bool:
    """Return True when *left* and *right* name the same location."""
    return path_key(_normalized(Path(left))) == path_key(_normalized(Path(right)))


def entry_write_root(
    entry: InstallEntry, harness_root: Path | None, project_root: Path | None
) -> Path:
    """Return the boundary *entry*'s target must stay inside.

    A user-level entry is bounded by the user home. For Codex that equals the
    boundary it always had (the parent of ``~/.codex``), so a symlinked
    ``~/.agents`` is refused as before. Every other entry keeps the install's
    boundary.
    """
    if entry.user_level:
        return _normalized(user_home())
    return _allowed_write_root(harness_root, project_root)


def emission_name(entry: InstallEntry, harness_name: str) -> str:
    """Return the emission identity *entry*'s skills are rendered with."""
    if entry.user_level and entry.mode in SKILL_MODES:
        return SHARED_EMISSION
    return harness_name


def user_level_entries(rules: HarnessRules) -> list[InstallEntry]:
    """Return *rules*' user-level install entries, in manifest order."""
    return [entry for entry in rules.install if entry.user_level]


def check_resolved_target(
    entry: InstallEntry, target: Path
) -> MaterializationResult | None:
    """Return an error when *entry*'s resolved *target* cannot be written.

    A placeholder that survived resolution is an error for every entry: it would
    be normalized against the working directory and write there. A user-level
    entry must also resolve to one of the allowed folders under the home; the
    parser checks the template, and this checks the path the plan will use.
    """
    if "${" in str(target):
        return _result(
            "error",
            entry.mode,
            target,
            "target still contains an unresolved placeholder",
        )
    if not entry.user_level:
        return None
    prefix = user_level_prefix(entry.target)
    if prefix is None or path_key(target) != path_key(user_home() / prefix):
        return _result(
            "error",
            entry.mode,
            target,
            "user-level target is not an allowed folder in the user home",
            detail={"allowed_root": str(_normalized(user_home()))},
        )
    return None


# --- backups -----------------------------------------------------------------

_HOME_NAMESPACE: ContextVar[bool] = ContextVar(
    "apothem_home_backup_namespace", default=False
)


@contextmanager
def home_namespace(
    harness_root: Path | None, project_root: Path | None
) -> Iterator[None]:
    """Key the backups taken inside under ``__home__/`` when the boundary is not the home.

    Wrap the writes, removals and restores of user-level targets. When the
    install's own boundary already is the user home (the default Codex root)
    nothing changes and the backup keys stay what they always were.
    """
    if same_location(_allowed_write_root(harness_root, project_root), user_home()):
        yield
        return
    token = _HOME_NAMESPACE.set(True)
    try:
        yield
    finally:
        _HOME_NAMESPACE.reset(token)


def entry_scope(
    entry: InstallEntry, harness_root: Path | None, project_root: Path | None
) -> AbstractContextManager[None]:
    """Return :func:`home_namespace` for a user-level *entry*, else a no-op scope."""
    if entry.user_level:
        return home_namespace(harness_root, project_root)
    return contextlib.nullcontext()


def home_backup_relative(target: Path, boundary_root: Path) -> Path | None:
    """Return *target*'s ``__home__/...`` backup key, or ``None`` outside a home scope.

    Only a backup keyed against the user home inside :func:`home_namespace`
    gets the segment; every other backup keeps its boundary-relative key.
    """
    if not _HOME_NAMESPACE.get() or not same_location(boundary_root, user_home()):
        return None
    try:
        relative = target.resolve().relative_to(boundary_root.resolve())
    except ValueError:
        return None
    return Path(HOME_BACKUP_SEGMENT) / relative


# --- holders -----------------------------------------------------------------


@dataclass(frozen=True)
class Holder:
    """One install that currently lists a user-level path in its ledger record."""

    harness: str
    root: str
    stale: bool = False

    @property
    def label(self) -> str:
        """Return ``<harness id> (<root>)`` for messages."""
        try:
            name = public_id_for_package_key(self.harness)
        except KeyError:
            name = self.harness
        return f"{name} ({self.root})"


@dataclass(frozen=True)
class HolderIndex:
    """The active ledger records, indexed by the paths they list."""

    by_path: dict[str, tuple[Holder, ...]] = field(default_factory=dict)
    stale: tuple[Holder, ...] = ()

    def lists(self, path: str | Path) -> bool:
        """Return True when any active record, stale roots included, lists *path*."""
        return path_key(path) in self.by_path

    def holders_of(
        self, path: str | Path, *, live_only: bool = True
    ) -> tuple[Holder, ...]:
        """Return the installs listing *path*; a root that no longer exists is skipped."""
        found = self.by_path.get(path_key(path), ())
        return tuple(h for h in found if not (live_only and h.stale))


def holder_index(*, exclude: tuple[str, str | Path] | None = None) -> HolderIndex:
    """Index every active install record, across all harnesses and roots, by path.

    A ``(harness, root)`` pair holds a path while its *current* install record
    lists it (:func:`install_ledger.current_install_record`, which replays
    install, uninstall and rollback records). *exclude* names the pair doing the
    asking; only that exact pair is left out, so one harness installed in two
    projects counts as two holders. A holder whose root directory no longer
    exists is marked stale and ignored by :meth:`HolderIndex.holders_of`, so a
    deleted project does not pin a folder for good.

    Raises:
        apothem.lib.install_ledger.LedgerError: A ledger is corrupted.
        OSError: A ledger cannot be read. The callers keep a folder they cannot
            prove unheld.
    """
    by_path: dict[str, list[Holder]] = {}
    stale: list[Holder] = []
    for package_key in SUPPORTED_PACKAGE_KEYS:
        if not writes_user_level(package_key):
            # Only a harness that writes a user-level folder can hold one, so
            # an unreadable ledger of any other harness is none of its business.
            continue
        roots = dict.fromkeys(
            record.root for record in install_ledger.read_records(package_key)
        )
        for root in roots:
            if (
                exclude is not None
                and package_key == exclude[0]
                and path_key(root) == path_key(exclude[1])
            ):
                continue
            record = install_ledger.current_install_record(package_key, root=root)
            if record is None:
                continue
            holder = Holder(package_key, root, stale=not Path(root).is_dir())
            if holder.stale:
                stale.append(holder)
            for target in record.targets:
                by_path.setdefault(path_key(target.path), []).append(holder)
    return HolderIndex(
        by_path={key: tuple(found) for key, found in by_path.items()},
        stale=tuple(stale),
    )


def retained_result(
    target: Path | str, holders: Iterable[Holder]
) -> MaterializationResult:
    """Return the ``unchanged`` result for a user-level target another install holds."""
    labels = [holder.label for holder in holders]
    shown = ", ".join(labels[:3]) + (
        f" and {len(labels) - 3} more" if len(labels) > 3 else ""
    )
    return _result(
        "unchanged",
        "shared_retained",
        Path(target),
        f"kept: still used by {shown}",
    )


def _unreadable_result(target: Path | str) -> MaterializationResult:
    return _result(
        "unchanged",
        "shared_retained",
        Path(target),
        "kept: the install ledger could not be read, so other installs may use it",
    )


# --- the gate ----------------------------------------------------------------


@dataclass
class UserLevelGate:
    """Decides, for one install, which recorded user-level targets it may remove.

    Built from the harness's rules, it knows the user-level folders the harness
    writes. :meth:`release` and :meth:`retained` answer "does another install
    still hold this target?" from the ledger, and :meth:`tidy` removes the empty
    folders the install left in the home. With no user-level entries the gate is
    inert.
    """

    harness_name: str
    root: Path
    harness_root: Path | None
    project_root: Path | None
    bases: dict[str, Path] = field(default_factory=dict)
    _index: HolderIndex | None = None
    _loaded: bool = False
    _released: set[str] = field(default_factory=set)

    @classmethod
    def build(
        cls,
        rules: HarnessRules,
        *,
        harness_name: str,
        root: Path,
        harness_root: Path | None,
        project_root: Path | None,
    ) -> UserLevelGate:
        """Return the gate for *rules* installed at *root*."""
        bases = {
            path_key(base): base
            for base in (
                resolve_target(
                    entry.target, harness_root=harness_root, project_root=project_root
                )
                for entry in user_level_entries(rules)
            )
        }
        return cls(harness_name, root, harness_root, project_root, bases)

    @classmethod
    def for_harness(
        cls,
        harness_name: str,
        *,
        root: Path,
        harness_root: Path | None,
        project_root: Path | None,
    ) -> UserLevelGate:
        """Return the gate for *harness_name*; inert when it has no manifest rules."""
        rules = rules_for(harness_name)
        if rules is None:
            return cls(harness_name, root, harness_root, project_root)
        return cls.build(
            rules,
            harness_name=harness_name,
            root=root,
            harness_root=harness_root,
            project_root=project_root,
        )

    @property
    def active(self) -> bool:
        """Return True when the harness writes any user-level folder."""
        return bool(self.bases)

    @property
    def boundary(self) -> Path:
        """Return the boundary user-level targets are removed within: the home."""
        return _normalized(user_home())

    def covers(self, path: str | Path) -> bool:
        """Return True when *path* is a direct child of a user-level folder."""
        return path_key(Path(path).parent) in self.bases

    def scope(self) -> AbstractContextManager[None]:
        """Return the backup-key scope for work on user-level targets."""
        return home_namespace(self.harness_root, self.project_root)

    def scope_for(self, path: str | Path) -> AbstractContextManager[None]:
        """Return :meth:`scope` for a user-level *path*, else a no-op scope."""
        return self.scope() if self.covers(path) else contextlib.nullcontext()

    def _holders(self) -> HolderIndex | None:
        if not self._loaded:
            self._loaded = True
            try:
                self._index = holder_index(exclude=(self.harness_name, self.root))
            except (install_ledger.LedgerError, OSError, ValueError):
                self._index = None
        return self._index

    def retained(self, path: str | Path) -> MaterializationResult | None:
        """Return the ``unchanged`` result keeping *path*, or ``None`` to go ahead.

        The target is kept when another install holds it, and also when the
        ledger cannot be read: a folder that cannot be proven unheld stays.
        """
        index = self._holders()
        if index is None:
            return _unreadable_result(path)
        holders = index.holders_of(path)
        return retained_result(path, holders) if holders else None

    def ledger_blocked(
        self, paths: Iterable[str | Path]
    ) -> MaterializationResult | None:
        """Return an error when the ledger is unreadable and *paths* touch a user-level folder.

        Removing the install's own files then would drop its claim on folders
        that cannot be proven unheld, and nothing could ever remove them. The
        caller stops before changing anything, so a repaired ledger and a second
        run finish the job.
        """
        covered = [path for path in paths if self.covers(path)]
        if not covered or self._holders() is not None:
            return None
        return _result(
            "error",
            "shared_retained",
            Path(covered[0]),
            "stopped before changing anything: the install ledger could not be "
            "read, so Apothem cannot tell whether other installs use the shared "
            "folders in your home; repair or move the unreadable ledger, then run "
            "the command again",
        )

    def inherited(self, path: str | Path, record: LedgerRecord) -> bool:
        """Return True when an install that has let go of *path* created it.

        A rollback removes what its install created. A target a later install
        only found in place was created by an earlier one, which may have been
        rolled back or uninstalled since while this install kept the folder.
        When this is the first claim on the folder and no other install lists
        it, the creation it inherited is removed with it, or nothing would be.
        An unreadable ledger proves nothing.
        """
        key = path_key(path)
        try:
            own = install_ledger.active_install_records(
                self.harness_name, root=self.root
            )
            ids = [item.install_id for item in own]
            earlier = (
                own[: ids.index(record.install_id)] if record.install_id in ids else own
            )
            if any(key == path_key(t.path) for item in earlier for t in item.targets):
                return False
            return any(
                target.outcome == "created" and path_key(target.path) == key
                for package_key in SUPPORTED_PACKAGE_KEYS
                if writes_user_level(package_key)
                for item in install_ledger.read_records(package_key)
                if item.kind == "install"
                for target in item.targets
            )
        except (install_ledger.LedgerError, OSError, ValueError):
            return False

    def release(
        self,
        entry: InstallEntry,
        record: LedgerRecord | None,
        remove: Callable[..., MaterializationResult | None],
    ) -> list[MaterializationResult]:
        """Remove the targets *record* lists under *entry*'s folder, unless held.

        Removal is record-driven: only a target the install's own current record
        lists goes, so a record from before the folder was managed, or no record,
        removes nothing here and an operator's same-named folder is never
        touched. A folder shared by two entries (skills and commands) is handled
        once. *remove* is called as ``remove(target, allowed_root=<home>)``.
        """
        if record is None:
            return []
        base = resolve_target(
            entry.target,
            harness_root=self.harness_root,
            project_root=self.project_root,
        )
        key = path_key(base)
        if key in self._released:
            return []
        self._released.add(key)
        results: list[MaterializationResult] = []
        for recorded in record.targets:
            if path_key(Path(recorded.path).parent) != key:
                continue
            held = self.retained(recorded.path)
            if held is not None:
                results.append(held)
                continue
            with self.scope():
                removal = remove(Path(recorded.path), allowed_root=self.boundary)
            if removal is not None:
                results.append(removal)
        return results

    def tidy(self, created_dirs: Iterable[str | Path]) -> list[MaterializationResult]:
        """Remove the empty folders this install left in the home, outside its boundary.

        Each user-level folder goes when empty, and so does the directory that
        holds it (``~/.agents``, ``~/.kiro``, ``~/.config/apothem``) and any
        directory the install's records say it created, once empty. The holding
        directory is tidied whoever created it: the install that creates it is
        often not the last one to hold the folder, and removing an empty
        directory loses nothing. ``~/.config`` goes too, but only once empty and
        only when the install writes ``~/.config/apothem``. A non-empty directory
        stays, and the home is never removed. Directories inside the install's
        own boundary are left to the ordinary created-directory removal.
        """
        install_boundary = _allowed_write_root(self.harness_root, self.project_root)
        home = self.boundary
        for base in self.bases.values():
            _sweep_staging(base, home)
        if not self.bases or same_location(install_boundary, home):
            return []
        protected = {path_key(home)}
        candidates = set(self.bases.values())
        holders = {
            holder
            for holder in (
                _holding_directory(base, user_home()) for base in self.bases.values()
            )
            if holder is not None
        }
        candidates.update(holders)
        if any(
            holder.name == "apothem" and holder.parent.name == ".config"
            for holder in holders
        ):
            candidates.add(user_home() / ".config")
        candidates.update(
            Path(path)
            for path in created_dirs
            if _within_allowed_root(Path(path), home)
            and not _within_allowed_root(Path(path), install_boundary)
        )
        results: list[MaterializationResult] = []
        for directory in sorted(
            (d for d in candidates if path_key(d) not in protected),
            key=lambda path: len(path.parts),
            reverse=True,
        ):
            if not directory.is_dir() or directory.is_symlink():
                continue
            if (
                _validate_target_path(
                    directory, allowed_root=home, operation="remove_directory"
                )
                is not None
            ):
                continue
            try:
                directory.rmdir()
            except OSError:
                continue
            results.append(
                _result(
                    "updated",
                    "remove_directory",
                    directory,
                    "removed an empty directory the install created",
                )
            )
        return results


def _sweep_staging(base: Path, home: Path) -> None:
    """Remove the staging folders an interrupted write left in *base*."""
    if not base.is_dir() or base.is_symlink():
        return
    for child in base.glob(f".*{STAGING_SUFFIX}"):
        if (
            child.is_dir()
            and not child.is_symlink()
            and _validate_target_path(
                child, allowed_root=home, operation="remove_staging"
            )
            is None
        ):
            shutil.rmtree(child, onerror=_handle_rm_error)


def _holding_directory(base: Path, home: Path) -> Path | None:
    """Return the home directory that holds the user-level folder *base*.

    ``~/.agents/skills`` is held by ``~/.agents`` and ``~/.config/apothem/rules``
    by ``~/.config/apothem``; ``None`` when *base* is not below *home*.
    """
    try:
        parts = base.relative_to(home).parts
    except ValueError:
        return None
    if len(parts) >= 2 and parts[0] == ".config":
        return home / parts[0] / parts[1] if len(parts) > 2 else None
    return home / parts[0] if len(parts) > 1 else None


__all__ = [
    "HOME_BACKUP_SEGMENT",
    "SHARED_EMISSION",
    "SHARED_TOPLEVEL_KEYS",
    "SKILL_MODES",
    "Holder",
    "HolderIndex",
    "UserLevelGate",
    "check_resolved_target",
    "emission_name",
    "entry_scope",
    "entry_write_root",
    "holder_index",
    "home_backup_relative",
    "home_namespace",
    "locked_for_harness",
    "path_key",
    "retained_result",
    "same_location",
    "shared_scope",
    "user_level_entries",
]
