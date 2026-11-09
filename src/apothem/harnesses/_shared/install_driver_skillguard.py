# SPDX-License-Identifier: MIT

"""Guards for the skill folders in a user-level folder.

A user-level skills folder is read by many tools, so a folder this driver is
about to write may belong to the operator. :class:`SkillGuard` keeps an install
from replacing one it did not write, and :func:`user_level_folders_ok` is the
presence test ``verify`` applies to the folders an entry should hold.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from apothem.lib import install_ledger
from apothem.lib.propagation import InstallEntry

from .install_driver_digests import folder_digests
from .install_driver_pathsafety import _is_link
from .install_driver_shared import (
    SKILL_MODES,
    Holder,
    HolderIndex,
    holder_index,
    path_key,
)
from .install_driver_types import MaterializationResult, _result


class SkillGuard:
    """Keeps an install from replacing a skill folder Apothem did not write.

    A user-level skills folder is read by many tools, so a folder with an
    Apothem skill's name that no ledger record lists belongs to the operator or
    to another tool (``npx skills`` for one). It is left alone and reported. A
    folder that already matches the emission is adopted, and one the active
    record of a live install lists (a legacy Codex record included) is replaced
    with a backup as before.

    A record whose root folder is gone (a deleted project, a removed
    ``CODEX_HOME``) proves less: the operator may have put a folder of their
    own there since. It counts only while the folder still holds every file
    that record lists, with the content it recorded. A record from an earlier
    release, with no file digests, cannot show that, so it does not count. A
    folder only such records list is left alone too, with a warning that says
    so and names the way out (move it aside, then update).
    """

    def __init__(self, evidence: HolderIndex | None) -> None:
        """Bind the ledger *evidence*; ``None`` means it could not be read."""
        self._evidence = evidence
        self.conflicts: list[MaterializationResult] = []
        self._records: dict[Holder, install_ledger.LedgerRecord | None] = {}

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
        holders = self._holders(directory)
        if any(
            not holder.stale or self._still_as_recorded(holder, directory)
            for holder in holders
        ):
            return None
        reason = (
            "an Apothem install in a folder that no longer exists lists it, but "
            "the folder has changed since, or that install (from an earlier "
            "release) did not record its files"
            if holders
            else "a skill folder with this name is not one Apothem wrote"
        )
        conflict = _result(
            "warning",
            "skill_conflict",
            directory,
            f"skipped {directory}: {reason}; rename or move it, then run "
            "apothem update",
            detail={"code": "skill_conflict"},
        )
        self.conflicts.append(conflict)
        return conflict

    def _holders(self, directory: Path) -> tuple[Holder, ...]:
        """Return every install record listing *directory*, deleted roots included."""
        if self._evidence is None:
            return ()
        return self._evidence.holders_of(directory, live_only=False)

    def _still_as_recorded(self, holder: Holder, directory: Path) -> bool:
        """Return True when *directory* holds what *holder*'s record says it wrote.

        Every file the record lists must be there, outside any link, with the
        recorded SHA-256; files added since do not matter. A record with no
        digests, or one that cannot be read, shows nothing.
        """
        record = self._record_of(holder)
        if record is None or _is_link(directory):
            return False
        wanted = path_key(directory)
        target = next((t for t in record.targets if path_key(t.path) == wanted), None)
        if target is None or not target.files:
            return False
        found = folder_digests(directory)
        return all(found.get(name) == digest for name, digest in target.files.items())

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


__all__ = ["SkillGuard", "user_level_folders_ok"]
