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

from .install_driver_shared import SKILL_MODES, HolderIndex, holder_index
from .install_driver_types import MaterializationResult, _result


class SkillGuard:
    """Keeps an install from replacing a skill folder Apothem did not write.

    A user-level skills folder is read by many tools, so a folder with an
    Apothem skill's name that no ledger record lists belongs to the operator or
    to another tool (``npx skills`` for one). It is left alone and reported. A
    folder that already matches the emission is adopted, and one any active
    record lists (a legacy Codex record included) is replaced with a backup as
    before.
    """

    def __init__(self, evidence: HolderIndex | None) -> None:
        """Bind the ledger *evidence*; ``None`` means it could not be read."""
        self._evidence = evidence
        self.conflicts: list[MaterializationResult] = []

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
        if self._evidence is not None and self._evidence.lists(directory):
            return None
        conflict = _result(
            "warning",
            "skill_conflict",
            directory,
            f"skipped {directory}: a skill folder with this name is not one "
            "Apothem wrote; rename or move it, then run apothem update",
            detail={"code": "skill_conflict"},
        )
        self.conflicts.append(conflict)
        return conflict


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
