# SPDX-License-Identifier: MIT

"""Guards for the skill folders in a user-level folder.

A user-level skills folder is read by many tools, so a folder this driver is
about to write may belong to the operator. :class:`SkillGuard` keeps an install
from replacing one it did not write, and :func:`user_level_folders_ok` is the
presence test ``verify`` applies to the folders an entry should hold.
"""

from __future__ import annotations

import os
import stat
from collections.abc import Iterable
from pathlib import Path

from apothem.lib import install_ledger
from apothem.lib.harness_materializer import extract_managed_block
from apothem.lib.propagation import InstallEntry

from .install_driver_digests import file_digest
from .install_driver_pathsafety import _is_link, _walk_without_links
from .install_driver_shared import (
    SKILL_MODES,
    Holder,
    HolderIndex,
    holder_index,
    path_key,
)
from .install_driver_types import MaterializationResult, _result

#: :meth:`SkillGuard.verdict` for a folder no install record lists.
UNLISTED = "unlisted"
#: :meth:`SkillGuard.verdict` for a folder only gone installs list, unproven.
UNPROVEN = "unproven"

_PRESENT, _GONE, _UNKNOWN = "present", "gone", "unknown"

_REASONS = {
    UNLISTED: "a skill folder with this name is not one Apothem wrote",
    UNPROVEN: (
        "the Apothem installs that list it are in folders that are gone, hold "
        "no Apothem files or cannot be read, and this folder has changed since "
        "they wrote it, or they (from an earlier release) did not record its files"
    ),
}


def root_state(root: Path) -> str:
    """Return ``"present"``, ``"gone"`` or ``"unknown"`` for the install folder *root*.

    ``"gone"``: the drive or network share that holds *root* answers, and
    *root* is missing (``FileNotFoundError``, ``NotADirectoryError``) or is not
    a folder. ``"unknown"``: the drive or share does not answer (checked
    through the stat of ``root.anchor``, so on POSIX only ``/``), or *root*
    cannot be read (a permission error).

    :class:`SkillGuard` lets only a ``"present"`` install folder vouch without
    proof. An unknown one says nothing about whether the operator replaced a
    shared folder since, so its record must prove the folder, as a gone one's
    must.
    """
    try:
        Path(root.anchor or ".").stat()
    except OSError:
        return _UNKNOWN
    try:
        info = root.stat()
    except (FileNotFoundError, NotADirectoryError):
        return _GONE
    except OSError:
        return _UNKNOWN
    return _PRESENT if stat.S_ISDIR(info.st_mode) else _GONE


def holds_apothem_files(root: Path, record: install_ledger.LedgerRecord) -> bool:
    """Return True when *root* still holds a file of its install *record* that is Apothem's.

    Only the record's root-local targets count: the paths under *root*, not
    the user-level folders it shares (the support files an install writes
    under ``.apothem/support/`` are root-local targets, the data stores under
    ``.apothem/`` are not). A target counts only while neither it nor a folder
    between *root* and it is a link (Apothem never writes through a link;
    *root* itself may be one, a project kept behind a junction) and it still
    shows Apothem's content (:func:`_still_apothems`). A record with no
    root-local target leaves only the folder to go by, so it counts as holding
    them. A file that cannot be read shows nothing.
    """
    base = Path(os.path.normpath(root))
    prefix = path_key(base).rstrip(os.sep) + os.sep
    local = [t for t in record.targets if path_key(t.path).startswith(prefix)]
    try:
        return not local or any(_still_apothems(base, target) for target in local)
    except OSError:
        return False


def _still_apothems(base: Path, target: install_ledger.LedgerTarget) -> bool:
    """Return True when the root-local *target* is still in place as Apothem's.

    A target Apothem owns counts while it exists. A file the operator owns
    (an instruction file Apothem merged its block into, a hooks config a
    repository may track itself) counts only while it still shows Apothem's
    part: a ``sentinel_merge`` file its managed block, any other its recorded
    SHA-256 (a folder: one listed file with its recorded SHA-256). Without that
    proof a re-cloned or cleaned project that keeps its own file of that name
    would still read as an install.
    """
    path = Path(os.path.normpath(target.path))
    if not _reached_without_links(base, path.parts[len(base.parts) :]):
        return False
    if target.ownership_class == "apothem-owned":
        return True
    if target.mode == "sentinel_merge":
        try:
            text = path.read_text(encoding="utf-8")
        except ValueError:  # not UTF-8 text: not the file Apothem merged into
            return False
        return extract_managed_block(text) is not None
    if target.digest is not None:
        return path.is_file() and file_digest(path) == target.digest
    return any(
        _reached_without_links(path, Path(name).parts)
        and file_digest(path / name) == digest
        for name, digest in (target.files or {}).items()
    )


def _reached_without_links(base: Path, parts: tuple[str, ...]) -> bool:
    """Return True when ``base/parts`` exists and no step below *base* is a link."""
    current = base
    for part in parts:
        current = current / part
        if _is_link(current):
            return False
    return current.exists()


class SkillGuard:
    """Keeps an install from replacing a skill folder Apothem did not write.

    A user-level skills folder is read by many tools, so a folder with an
    Apothem skill's name that no ledger record lists belongs to the operator or
    to another tool (``npx skills`` for one). It is left alone and reported. A
    folder that already matches the emission is adopted, and one the active
    record of a live install lists (a legacy Codex record included) is replaced
    with a backup as before.

    A record vouches without proof only while its install folder is there and
    still holds Apothem files (:meth:`_live`). Any other record proves less:
    the operator may have put a folder of their own there since. That covers a
    folder that no longer exists, one whose drive or share does not answer or
    that cannot be read (:func:`root_state`), and one that still exists but
    holds none of that record's files with Apothem's content in them
    (:func:`holds_apothem_files`): a deleted project, a removed
    ``CODEX_HOME``, a re-cloned or cleaned project. Such a record counts only
    while the skill folder holds exactly the files it lists, with the content
    it recorded, and no other file and no link. A record from an earlier
    release, with no file digests, cannot show that, so it does not count. A
    folder only such records list is left alone too, with a warning that says
    so and names the way out (move it aside, then update).
    """

    def __init__(self, evidence: HolderIndex | None) -> None:
        """Bind the ledger *evidence*; ``None`` means it could not be read."""
        self._evidence = evidence
        self.conflicts: list[MaterializationResult] = []
        self._records: dict[Holder, install_ledger.LedgerRecord | None] = {}
        self._lives: dict[Holder, bool] = {}

    @property
    def readable(self) -> bool:
        """Return True when the ledger evidence could be read."""
        return self._evidence is not None

    @classmethod
    def load(cls) -> SkillGuard:
        """Read the ledger evidence; an unreadable ledger proves nothing."""
        try:
            return cls(holder_index())
        except (install_ledger.LedgerError, OSError, ValueError):
            return cls(None)

    def check(self, directory: Path, matches: bool) -> MaterializationResult | None:
        """Return a ``warning`` result when *directory* must be left alone, else ``None``.

        *matches* says the folder already holds exactly what would be written.
        """
        if matches or not (directory.exists() or directory.is_symlink()):
            return None
        verdict = self.verdict(directory)
        if verdict is None:
            return None
        conflict = _result(
            "warning",
            "skill_conflict",
            directory,
            f"skipped {directory}: {_REASONS[verdict]}; rename or move it, then "
            "run apothem update",
            detail={"code": "skill_conflict"},
        )
        self.conflicts.append(conflict)
        return conflict

    def verdict(self, directory: Path) -> str | None:
        """Return why *directory* is not provably Apothem's, or ``None`` when it is.

        :data:`UNLISTED` when no install record lists it (or the ledger cannot
        be read), :data:`UNPROVEN` when no install that lists it is live and
        none of their records shows it as written. Whether the folder already
        matches the emission is the caller's test.
        """
        holders = self._holders(directory)
        if not holders:
            return UNLISTED
        if any(
            self._live(holder) or self._still_as_recorded(holder, directory)
            for holder in holders
        ):
            return None
        return UNPROVEN

    def _holders(self, directory: Path) -> tuple[Holder, ...]:
        """Return every install record listing *directory*, deleted roots included."""
        if self._evidence is None:
            return ()
        return self._evidence.holders_of(directory, live_only=False)

    def _live(self, holder: Holder) -> bool:
        """Return True when *holder*'s install folder is there and holds Apothem files.

        A folder that is gone, cannot be reached or read, or whose record
        cannot be read is not live: what it shows proves nothing.
        """
        if holder not in self._lives:
            root = Path(holder.root)
            record = self._record_of(holder)
            self._lives[holder] = (
                record is not None
                and root_state(root) == _PRESENT
                and holds_apothem_files(root, record)
            )
        return self._lives[holder]

    def _still_as_recorded(self, holder: Holder, directory: Path) -> bool:
        """Return True when *directory* holds exactly what *holder*'s record says it wrote.

        The folder must hold every file the record lists, with the recorded
        SHA-256, and nothing else: a file the operator added would be moved
        into the backup by the replace, so it makes the folder unproven. A
        link anywhere in it, a folder that cannot be read, a record with no
        digests and a record that cannot be read show nothing.
        """
        record = self._record_of(holder)
        if record is None or _is_link(directory):
            return False
        wanted = path_key(directory)
        target = next((t for t in record.targets if path_key(t.path) == wanted), None)
        if target is None or not target.files:
            return False
        walk = _walk_without_links(directory)
        if walk.links or walk.unreadable:
            return False
        found = {path.relative_to(directory).as_posix(): path for path in walk.files}
        if found.keys() != target.files.keys():
            return False
        return all(
            file_digest(found[name]) == digest for name, digest in target.files.items()
        )

    def _record_of(self, holder: Holder) -> install_ledger.LedgerRecord | None:
        """Return *holder*'s current install record, read once per guard."""
        if holder not in self._records:
            try:
                record = install_ledger.current_install_record(
                    holder.harness, root=holder.root
                )
            except (install_ledger.LedgerError, OSError):
                record = None
            self._records[holder] = record
        return self._records[holder]


def user_level_folders_ok(entry: InstallEntry, folders: Iterable[Path]) -> bool:
    """Return True when every folder a user-level *entry* should hold is in place.

    A skill folder must hold a regular ``SKILL.md``; a corpus folder just has to
    exist. That passes when a different adapter wrote the folder and fails after
    a partial write or a manual deletion. (Whether the folder is Apothem's is a
    separate test, :class:`SkillGuard`.)
    """
    if entry.mode in SKILL_MODES:
        return all((folder / "SKILL.md").is_file() for folder in folders)
    return all(folder.exists() for folder in folders)


__all__ = [
    "UNLISTED",
    "UNPROVEN",
    "SkillGuard",
    "holds_apothem_files",
    "root_state",
    "user_level_folders_ok",
]
