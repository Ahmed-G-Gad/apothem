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
from apothem.lib.harness_registry import (
    SUPPORTED_PACKAGE_KEYS,
    public_id_for_package_key,
)
from apothem.lib.propagation import InstallEntry, resolve_target, user_home

from .install_driver_digests import file_digest
from .install_driver_pathsafety import _is_link, _walk_without_links
from .install_driver_shared import (
    SKILL_MODES,
    Holder,
    HolderIndex,
    holder_index,
    path_key,
)
from .install_driver_sharedlock import rules_for, writes_user_level
from .install_driver_types import MaterializationResult, _result

#: :meth:`SkillGuard.verdict` for a folder no install record lists.
UNLISTED = "unlisted"
#: :meth:`SkillGuard.verdict` for a folder Apothem installs listed, unproven.
UNPROVEN = "unproven"

_PRESENT, _GONE, _UNKNOWN = "present", "gone", "unknown"

_UNLISTED_REASON = "a skill folder with this name is not one Apothem wrote"
_ANY_UPDATE = "apothem update for this harness"


def unproven_advice(where: str, command: str) -> str:
    """Return why a skill folder is unproven and the two ways on.

    The install warning and ``verify`` both print it, so they never disagree.
    *where* names the skills folder, *command* the update that writes
    Apothem's version once the folder is moved out of it.
    """
    return (
        "the Apothem installs that listed it are in folders that are gone, "
        "hold no Apothem files or cannot be read, or they no longer list it. "
        "It does not hold exactly the files they recorded. Either you made or "
        "edited it (your own skill), or an earlier release wrote it without "
        "recording its files. To keep it, leave it where it is: Apothem does "
        "not change it, and the harness stays not verified. To use Apothem's "
        f"version, move it out of {where}, then run {command}"
    )


def update_command(harness: str, project: str | None) -> str:
    """Return ``apothem update --harness <harness>``, with ``--project <project>``."""
    scope = "" if project is None else f" --project {project}"
    return f"apothem update --harness {harness}{scope}"


def _install_command(harness_name: str | None, project_root: Path | None) -> str:
    """Return the update an install or update warning names for *harness_name*.

    The project is named in words: the operator gave it to this run, and only
    the CLI quotes a path for a shell.
    """
    try:
        command = update_command(public_id_for_package_key(harness_name or ""), None)
    except KeyError:
        return _ANY_UPDATE
    if project_root is None:
        return command
    return f"{command} with the same --project as this run"


def home_text(folder: Path) -> str:
    """Return *folder* as ``~/.../`` when it is under the home, else as written.

    ``verify`` names a user-home folder the same way, and a copied message
    then holds no username.
    """
    try:
        relative = folder.relative_to(user_home())
    except ValueError:
        return str(folder)
    return f"~/{relative.as_posix()}/"


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
    them. A file that cannot be read shows nothing, and the next target is
    read.
    """
    base = Path(os.path.normpath(root))
    prefix = path_key(base).rstrip(os.sep) + os.sep
    shared = _user_level_prefixes()
    local = [
        target
        for target in record.targets
        if path_key(target.path).startswith(prefix)
        and not path_key(target.path).startswith(shared)
    ]
    return not local or any(_shows_apothems(base, target) for target in local)


def _user_level_prefixes() -> tuple[str, ...]:
    """Return the comparison keys, each ending in a separator, of the user-level folders.

    Every folder a user-level manifest entry writes (the shared skills
    folders, ``~/.config/apothem/rules/`` and ``templates/``) is shared by
    installs in many roots, so none of its targets says a root is still
    installed, not even for a project kept at the home folder itself.
    """
    folders: dict[str, None] = {}
    for package_key in SUPPORTED_PACKAGE_KEYS:
        rules = rules_for(package_key)
        for entry in rules.install if rules is not None else ():
            if entry.user_level:
                key = path_key(resolve_target(entry.target)).rstrip(os.sep)
                folders[key + os.sep] = None
    return tuple(folders)


def _shows_apothems(base: Path, target: install_ledger.LedgerTarget) -> bool:
    """Return :func:`_still_apothems`; a target that cannot be read shows nothing."""
    try:
        return _still_apothems(base, target)
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
    so and names the way out (move it out of the skills folder, then update).
    So is a folder that no current record lists but an earlier install
    record did: an install that ran again in the same folder after skipping
    it does not list it, and the folder is no more proven than before, unless
    it holds exactly what one of those earlier records lists.
    """

    def __init__(self, evidence: HolderIndex | None, command: str = "") -> None:
        """Bind the ledger *evidence*; ``None`` means it could not be read.

        *command* is the update an unproven folder's warning names.
        """
        self._evidence = evidence
        self._command = command or _ANY_UPDATE
        self.conflicts: list[MaterializationResult] = []
        self._records: dict[Holder, install_ledger.LedgerRecord | None] = {}
        self._lives: dict[Holder, bool] = {}
        self._listed_before: dict[str, list[dict[str, str] | None]] | None = None

    @property
    def readable(self) -> bool:
        """Return True when the ledger evidence could be read."""
        return self._evidence is not None

    @classmethod
    def for_entry(
        cls, entry: InstallEntry, harness_name: str, project_root: Path | None
    ) -> SkillGuard | None:
        """Return :meth:`load` for a user-level *entry*, ``None`` for any other."""
        return cls.load(harness_name, project_root) if entry.user_level else None

    @classmethod
    def load(
        cls, harness_name: str | None = None, project_root: Path | None = None
    ) -> SkillGuard:
        """Read the ledger evidence; an unreadable ledger proves nothing.

        *harness_name* (a package key) and *project_root* name the install
        whose warnings this guard writes, for the update they name.
        """
        command = _install_command(harness_name, project_root)
        try:
            return cls(holder_index(), command)
        except (install_ledger.LedgerError, OSError, ValueError):
            return cls(None, command)

    def check(self, directory: Path, matches: bool) -> MaterializationResult | None:
        """Return a ``warning`` result when *directory* must be left alone, else ``None``.

        *matches* says the folder already holds exactly what would be written.
        """
        if matches or not (directory.exists() or directory.is_symlink()):
            return None
        verdict = self.verdict(directory)
        if verdict is None:
            return None
        if verdict == UNPROVEN:
            message = f"skipped {directory}, which Apothem cannot prove it wrote: "
            message += unproven_advice(home_text(directory.parent), self._command)
        else:
            message = f"skipped {directory}: {_UNLISTED_REASON}; rename or move "
            message += "it, then run apothem update"
        conflict = _result(
            "warning",
            "skill_conflict",
            directory,
            message,
            detail={"code": "skill_conflict"},
        )
        self.conflicts.append(conflict)
        return conflict

    def verdict(self, directory: Path) -> str | None:
        """Return why *directory* is not provably Apothem's, or ``None`` when it is.

        :data:`UNLISTED` when no install record lists it now or listed it
        before (or the ledger cannot be read), :data:`UNPROVEN` when no install
        that lists it is live and none of their records shows it as written,
        or when only earlier install records listed it and none of them shows
        it as written. Whether the folder already matches the emission is the
        caller's test.
        """
        holders = self._holders(directory)
        if not holders:
            earlier = self._earlier_listings(directory)
            if not earlier:
                return UNLISTED
            if any(_holds_exactly(directory, files) for files in earlier):
                return None
            return UNPROVEN
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

    def _earlier_listings(self, directory: Path) -> list[dict[str, str] | None]:
        """Return the ``files`` map of each install record that listed *directory*.

        Every record still in the ledger counts, not only the current ones;
        an empty list means none listed it (or the ledger cannot be read).
        """
        if self._evidence is None:
            return []
        if self._listed_before is None:
            listed: dict[str, list[dict[str, str] | None]] = {}
            try:
                for package_key in SUPPORTED_PACKAGE_KEYS:
                    if not writes_user_level(package_key):
                        continue
                    for record in install_ledger.read_records(package_key):
                        if record.kind != "install":
                            continue
                        for target in record.targets:
                            key = path_key(target.path)
                            listed.setdefault(key, []).append(target.files)
            except (install_ledger.LedgerError, OSError, ValueError):
                listed = {}
            self._listed_before = listed
        return self._listed_before.get(path_key(directory), [])

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
        if record is None:
            return False
        wanted = path_key(directory)
        target = next((t for t in record.targets if path_key(t.path) == wanted), None)
        return target is not None and _holds_exactly(directory, target.files)

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


def _holds_exactly(directory: Path, files: dict[str, str] | None) -> bool:
    """Return True when *directory* holds exactly *files* (name to SHA-256).

    No listed file may be missing or differ, and no other file may be there.
    A link anywhere in it, a folder that cannot be read and an empty or
    missing *files* map show nothing.
    """
    if not files or _is_link(directory):
        return False
    walk = _walk_without_links(directory)
    if walk.links or walk.unreadable:
        return False
    found = {path.relative_to(directory).as_posix(): path for path in walk.files}
    if found.keys() != files.keys():
        return False
    return all(file_digest(found[name]) == digest for name, digest in files.items())


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
    "home_text",
    "root_state",
    "unproven_advice",
    "update_command",
    "user_level_folders_ok",
]
