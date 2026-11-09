# SPDX-License-Identifier: MIT

"""What the shared user-level folders mean for the CLI's output.

Seven project-scope adapters (``github-copilot``, ``cursor``, ``windsurf``,
``zed``, ``codebuddy``, ``kiro`` and ``trae``) write Apothem's skills, and the
rules and templates they cite, to folders in the user home. ``codex`` writes
the same folders. Several installs, in several projects, can hold one folder, so
the install ledger is the reference counter and this module reads it to say, in
the operator's words:

* where an install writes outside ``--project`` (:func:`user_level_write_advisory`,
  :func:`shared_folders`);
* which installs use a shared folder now, and which one is its owner of record
  (:func:`ledger_holders`);
* what an uninstall keeps because another install still uses it, and what it
  removes (:func:`preview_uninstall`, :func:`uninstall_advisories`);
* why ``verify`` failed for a user-level folder (:func:`verify_hint`).

Everything here reads the ledger and the filesystem and writes nothing. A ledger
that cannot be read never turns into a claim that a folder is unused: the
callers keep the folder and say so.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path

from apothem.harnesses._shared import install_driver
from apothem.harnesses._shared.install_driver_keys import same_folder
from apothem.harnesses._shared.install_driver_shared import SKILL_MODES, path_key
from apothem.lib import install_ledger
from apothem.lib.harness_registry import (
    SHARED_ROOTS,
    SUPPORTED_PACKAGE_KEYS,
    get_harness_entry,
    public_id_for_package_key,
)
from apothem.lib.propagation import resolve_target, user_home

_SHOWN = 3  # Installs named in one message before "and N more".
_LEDGER_ERRORS = (install_ledger.LedgerError, OSError, ValueError)


def _tilde(path: Path) -> str:
    """Return *path* as ``~/...`` when it is under the home, else as written.

    Messages name ``~`` rather than the operator's home so a copied report holds
    no username.
    """
    try:
        relative = path.relative_to(user_home())
    except ValueError:
        return str(path)
    return f"~/{relative.as_posix()}/"


def _names(labels: Sequence[str]) -> str:
    """Return *labels* joined for a message, with a count past :data:`_SHOWN`."""
    shown = ", ".join(labels[:_SHOWN])
    extra = len(labels) - _SHOWN
    return f"{shown} and {extra} more" if extra > 0 else shown


def user_level_dirs(harness_id: str) -> tuple[Path, ...]:
    """Return the distinct user-home folders *harness_id*'s install writes.

    Read from the harness's manifest block; empty for a harness with no
    ``${USER_HOME}`` entry. The folders resolve against the real home, so the
    order is the manifest's.
    """
    try:
        rules = install_driver.load_rules(get_harness_entry(harness_id).package_key)
    except (RuntimeError, KeyError):
        return ()
    found: dict[str, Path] = {}
    for entry in rules.install:
        if entry.user_level:
            folder = resolve_target(entry.target, harness_root=None, project_root=None)
            found.setdefault(path_key(folder), folder)
    return tuple(found.values())


def is_project_scope(adapter: object) -> bool:
    """Return True for an adapter whose install root is the ``--project`` folder."""
    return callable(getattr(adapter, "resolve_output_path", None))


# --- the ledger as holders see it -------------------------------------------


@dataclass(frozen=True)
class _Install:
    """One active install, as its current ledger record lists it."""

    harness: str
    root: str
    since: str
    pairs: frozenset[tuple[str, str]]  # (target key, key of its folder)
    live: bool

    @cached_property
    def targets(self) -> frozenset[str]:
        """Return the keys of the targets this install lists."""
        return frozenset(key for key, _ in self.pairs)

    @cached_property
    def parents(self) -> frozenset[str]:
        """Return the keys of the folders that hold those targets."""
        return frozenset(parent for _, parent in self.pairs)

    @property
    def label(self) -> str:
        """Return ``<harness id> (<root>)``."""
        return f"{self.harness} ({self.root})"

    def lists(self, key: str) -> bool:
        """Return True when this install lists *key*, or a direct child of it."""
        return key in self.targets or key in self.parents


@dataclass(frozen=True)
class LedgerView:
    """Every active install, across all harnesses and roots, oldest first."""

    installs: tuple[_Install, ...]
    #: The folders resolved while the view was read (see :func:`path_key`),
    #: reused by its lookups; it lives as long as this view.
    memo: dict[str, str] = field(default_factory=dict, compare=False, repr=False)

    @classmethod
    def load(cls) -> LedgerView | None:
        """Read the ledgers; ``None`` when one cannot be read."""
        found: list[_Install] = []
        memo: dict[str, str] = {}  # one pass: each holding folder is resolved once
        try:
            for package_key in SUPPORTED_PACKAGE_KEYS:
                roots = dict.fromkeys(
                    record.root for record in install_ledger.read_records(package_key)
                )
                for root in roots:
                    record = install_ledger.current_install_record(
                        package_key, root=root
                    )
                    if record is None:
                        continue
                    pairs = frozenset(
                        (path_key(t.path, memo), path_key(Path(t.path).parent, memo))
                        for t in record.targets
                    )
                    found.append(
                        _Install(
                            harness=public_id_for_package_key(package_key),
                            root=root,
                            since=record.timestamp,
                            pairs=pairs,
                            live=Path(root).is_dir(),
                        )
                    )
        except _LEDGER_ERRORS:
            return None
        return cls(tuple(sorted(found, key=lambda install: install.since)), memo)

    def users_of(
        self, location: Path, *, exclude: _Install | None = None
    ) -> list[_Install]:
        """Return the installs that list *location* or a child of it, oldest first."""
        key = path_key(location, self.memo)
        return [i for i in self.installs if i is not exclude and i.lists(key)]

    def find(self, harness: str, root: Path) -> _Install | None:
        """Return the active install of *harness* at *root*, or ``None``.

        The root is matched by exact text, never with the case folded, as the
        ledger finds the uninstall's own install record. The same harness
        recorded under another spelling of the folder is the same install to
        an uninstall (see :meth:`others`), so the preview reports what the
        uninstall does.
        """
        for install in self.installs:
            if install.harness == harness and install.root == str(root):
                return install
        return None

    def others(self, own: _Install) -> list[_Install]:
        """Return the installs other than *own*, oldest first.

        A record of *own*'s harness under another spelling of its folder is
        left out: the uninstall ends it with *own* (see
        :func:`~apothem.harnesses._shared.install_driver_keys.same_folder_roots`).
        """
        return [
            install
            for install in self.installs
            if install is not own
            and not (
                install.harness == own.harness and same_folder(install.root, own.root)
            )
        ]


def ledger_holders() -> Callable[[Path], Sequence[str]] | None:
    """Return a function mapping a folder to the installs that use it, or ``None``.

    The function gives the public ids of the installs whose current ledger
    record lists the folder or a child of it, oldest first, one per harness. An
    install whose project folder no longer exists is left out, as an uninstall
    leaves it out. ``None`` when a ledger cannot be read; the advisories then say
    only what the registry knows.
    """
    view = LedgerView.load()
    if view is None:
        return None
    ledger = view

    def holders(location: Path) -> Sequence[str]:
        return list(
            dict.fromkeys(i.harness for i in ledger.users_of(location) if i.live)
        )

    return holders


# --- disclosure at install, update and dry run ------------------------------


def shared_folders(
    adapters: Sequence[tuple[str, object]],
) -> list[tuple[str, Path]]:
    """Return ``(harness id, folder)`` for the user-home folders project-scope *adapters* write.

    A project-scope install writes these outside ``--project``; the blast-radius
    preview lists them apart from the project files and the home-rooted adapters.
    """
    return [
        (harness_id, folder)
        for harness_id, adapter in adapters
        if is_project_scope(adapter)
        for folder in user_level_dirs(harness_id)
    ]


def user_level_write_advisory(harness_id: str) -> dict[str, object] | None:
    """Return the ``user_level_write`` advisory for a project-scope install, or ``None``.

    Names the folders the install writes outside ``--project``, so the operator
    learns about the home writes on every install, update and dry run and not
    only in a batch. Never blocking.
    """
    folders = user_level_dirs(harness_id)
    if not folders:
        return None
    tools = any(
        path_key(folder) == path_key(_registry_path(root.path))
        for folder in folders
        for root in SHARED_ROOTS
        if root.kind == "load" and root.path.startswith("~/")
    )
    shown = ", ".join(_tilde(folder) for folder in folders)
    audience = (
        "every project and by the other tools that load them"
        if tools
        else ("every project that installs it")
    )
    name = get_harness_entry(harness_id).display_name
    return {
        "harness": harness_id,
        "outcome": "advisory",
        "operation": "user_level_write",
        "paths": [str(folder) for folder in folders],
        "message": (
            f"{name} also writes outside --project: {shown} (shared by {audience}). "
            "A write failure there stops this install before the project changes. "
            "An uninstall keeps them while another Apothem install uses them."
        ),
    }


def _registry_path(path: str) -> Path:
    """Return the home path of a registry ``~/...`` *path*."""
    return user_home() / path[2:].rstrip("/")


# --- uninstall ---------------------------------------------------------------


@dataclass(frozen=True)
class FolderUse:
    """How the other installs use one user-level folder an uninstall would release."""

    folder: Path
    total: int
    kept: int
    holders: tuple[str, ...]
    stale: tuple[str, ...]


@dataclass(frozen=True)
class UninstallPreview:
    """What an uninstall of one install keeps and removes in the user home."""

    uses: tuple[FolderUse, ...]
    unreadable: bool = False


def preview_uninstall(harness_id: str, root: Path) -> UninstallPreview | None:
    """Return what uninstalling *harness_id* at *root* keeps in the user home.

    Computed from the ledger before the uninstall, with the same rule the
    uninstall applies: a recorded target goes unless another active install
    lists it. ``None`` when the harness writes no user-level folder or has no
    install record (an uninstall then removes nothing in the home).
    """
    folders = user_level_dirs(harness_id)
    if not folders:
        return None
    view = LedgerView.load()
    if view is None:
        return UninstallPreview(
            tuple(FolderUse(folder, 0, 0, (), ()) for folder in folders), True
        )
    own = view.find(harness_id, root)
    if own is None:
        return None
    others = view.others(own)
    live_keys = frozenset().union(*(o.targets for o in others if o.live))
    uses: list[FolderUse] = []
    for folder in folders:
        key = path_key(folder, view.memo)
        recorded = [t for t, parent in own.pairs if parent == key]
        if not recorded:
            continue
        kept = sum(1 for target in recorded if target in live_keys)
        under = [o for o in others if key in o.parents]
        uses.append(
            FolderUse(
                folder=folder,
                total=len(recorded),
                kept=kept,
                holders=tuple(o.label for o in under if o.live),
                stale=tuple(o.label for o in under if not o.live),
            )
        )
    return UninstallPreview(tuple(uses))


def uninstall_advisories(
    harness_id: str, preview: UninstallPreview | None
) -> list[dict[str, object]]:
    """Return the ``retained`` and ``released`` advisories for a finished uninstall.

    One entry per user-level folder the install held. ``retained`` says another
    install still uses the folder (all of it, or part: ``kept`` of ``total``
    entries) and names those installs; ``released`` says no other install did,
    so the uninstall removed it. An install whose project folder is gone is
    ignored and named. Entries carry ``outcome: "advisory"`` and
    ``operation: "shared_root"`` like the install advisories.
    """
    if preview is None:
        return []
    advisories: list[dict[str, object]] = []
    for use in preview.uses:
        shown = _tilde(use.folder)
        if preview.unreadable:
            role = "retained"
            message = (
                f"{shown} was kept: the install ledger could not be read, so "
                "another Apothem install may still use it. Run apothem verify, "
                "then remove the folder by hand if nothing uses it."
            )
        elif use.kept == 0:
            role = "released"
            message = f"{shown} was removed: no other Apothem install uses it."
        elif use.kept == use.total:
            role = "retained"
            message = (
                f"{shown} was kept: still used by {_names(use.holders)}. It is "
                "removed when the last Apothem install that uses it is uninstalled."
            )
        else:
            role = "retained"
            message = (
                f"{shown}: kept {use.kept} of {use.total} entries that "
                f"{_names(use.holders)} still use, and removed the rest."
            )
        if use.stale:
            message += (
                f" Ignored because its project folder no longer exists: "
                f"{_names(use.stale)}."
            )
        advisories.append(
            {
                "harness": harness_id,
                "outcome": "advisory",
                "operation": "shared_root",
                "role": role,
                "path": str(use.folder),
                "holders": list(use.holders),
                "stale": list(use.stale),
                "kept": use.kept,
                "total": use.total,
                "message": message,
            }
        )
    return advisories


# --- verify ------------------------------------------------------------------


def verify_hint(harness_id: str) -> dict[str, object] | None:
    """Return why ``verify`` failed for the user-level folders of *harness_id*, or ``None``.

    Looks for the two causes an operator can act on: an expected folder that is
    missing (or holds no ``SKILL.md``), which ``apothem install`` restores, and a
    folder no Apothem install record lists, which belongs to someone else until
    it is renamed or moved. The result has ``missing`` and ``unlisted`` path
    lists and a ``message``; ``None`` when neither applies.
    """
    try:
        rules = install_driver.load_rules(get_harness_entry(harness_id).package_key)
    except (RuntimeError, KeyError):
        return None
    view = LedgerView.load()
    memo = view.memo if view is not None else {}  # each folder resolved once
    missing: dict[str, Path] = {}
    unlisted: dict[str, Path] = {}
    for entry in rules.install:
        if not entry.user_level:
            continue
        for folder in install_driver.generated_targets_for_entry(
            entry, harness_root=None, project_root=None, exclude=rules.exclude
        ):
            key = path_key(folder, memo)
            skill = entry.mode in SKILL_MODES
            if not (folder / "SKILL.md" if skill else folder).exists():
                missing[key] = folder
            elif skill and view is not None and not view.users_of(folder):
                unlisted[key] = folder
    if not missing and not unlisted:
        return None
    parts: list[str] = []
    if missing:
        parts.append(
            f"{len(missing)} expected folder(s) are missing under "
            f"{_parents(missing.values())}; run apothem install to restore them"
        )
    if unlisted:
        parts.append(
            f"{len(unlisted)} skill folder(s) under {_parents(unlisted.values())} "
            "are not listed by any Apothem install and may belong to another "
            "tool; rename or move them, then run apothem update"
        )
    return {
        "missing": [str(p) for p in missing.values()],
        "unlisted": [str(p) for p in unlisted.values()],
        "message": "; ".join(parts),
    }


def _parents(folders: Iterable[Path]) -> str:
    """Return the distinct parent folders of *folders* as ``~/...`` text."""
    return ", ".join(dict.fromkeys(_tilde(folder.parent) for folder in folders))
