# SPDX-License-Identifier: MIT

"""Comparison keys for the paths and roots the install ledger records.

:func:`path_key` keys a path an install writes, so two spellings of one shared
user-level folder (a home reached through a link and the folder it leads to)
count as one folder. :func:`same_folder` and :func:`same_folder_roots` tell
when two recorded install roots are one folder, so an uninstall treats the
same harness recorded under both spellings as one install
(:func:`one_install`). :func:`made_keys` says which shared paths an install
made and nothing has changed since.
"""

from __future__ import annotations

import contextlib
import os
import re
from dataclasses import replace
from pathlib import Path

from apothem.lib import install_ledger
from apothem.lib.harness_registry import SUPPORTED_PACKAGE_KEYS
from apothem.lib.install_ledger import LedgerRecord, LedgerTarget, created_here
from apothem.lib.propagation import USER_LEVEL_PREFIXES, user_home

from .install_driver_pathsafety import _normalized
from .install_driver_sharedlock import writes_user_level


def _folded(path: str | Path) -> str:
    """Return *path* normalized and case-folded where the OS is, without following links."""
    return os.path.normcase(os.path.normpath(str(path)))


#: The user-level folders as folded key endings. Only a path that is one of
#: them, or lies inside one, can be shared between installs, so only such a
#: path has its links followed; any other path is keyed by its spelling.
_SHARED_TAILS: tuple[str, ...] = tuple(
    os.sep + _folded(prefix) for prefix in sorted(USER_LEVEL_PREFIXES)
)
#: Matches a folded folder that is a user-level folder or lies inside one.
_SHARED_FOLDER = re.compile(
    "|".join(re.escape(tail) + f"(?:{re.escape(os.sep)}|$)" for tail in _SHARED_TAILS)
)


def path_key(path: str | Path, memo: dict[str, str] | None = None) -> str:
    """Return the comparison key of *path*: the place it names, case-folded where the OS is.

    The spelling is folded lexically first, ``..`` by name as Windows does,
    before any link is followed. Ledger records written before
    ``${USER_HOME}`` name Codex's skills as ``<root>/.codex/../.agents/skills/x``,
    which keys as ``<home>/.agents/skills/x`` even when ``.codex`` is a link.
    For a path that is a user-level folder (``.agents/skills``,
    ``.config/apothem/rules``, ...) or lies inside one, the links in the folder
    that holds it are then followed, so a home spelled through a link
    (``/home`` leading to ``/var/home``, a profile moved behind a junction)
    and the home's own path give one key. The test is on the folder names as
    the manifest spells them, not on the current home, so a record made under
    the other spelling qualifies too. The last part stays as spelled: a path
    that is itself a link is keyed as that entry, not as the place it leads
    to. Any other path, and a relative one, is only folded, which costs no
    filesystem call. Case is folded the way the OS folds it, not the way the
    folder does: a case-sensitive folder on Windows and a case-insensitive
    volume on macOS are not told apart.

    *memo* maps a holding folder, as spelled, to its key prefix, for a caller
    that keys many paths in one pass, so each folder that holds a path is
    tested and resolved once (a user-level folder itself is resolved on each
    call). Nothing is kept between calls without it, since a link can be made
    or removed at any time.
    """
    # Text, not Path objects: an index keys a few thousand paths per pass, so
    # the folder test runs once per holding folder, not once per path.
    lexical = os.path.normpath(str(path))
    parent, leaf = os.path.split(lexical)
    if not leaf:
        return os.path.normcase(lexical)
    prefix = memo.get(parent) if memo is not None else None
    if prefix is None:
        prefix = os.path.normcase(os.path.join(parent, ""))  # noqa: PTH118
        if _SHARED_FOLDER.search(prefix) is not None:  # inside a user-level folder
            prefix = _key_prefix(parent)
        if memo is not None:
            memo[parent] = prefix
    key = prefix + os.path.normcase(leaf)
    if key.endswith(_SHARED_TAILS):  # a user-level folder itself
        key = _key_prefix(parent) + os.path.normcase(leaf)
    return key


def _key_prefix(folder: str) -> str:
    """Return *folder*, its links followed when absolute, case-folded, ending in a separator."""
    if os.path.isabs(folder):  # noqa: PTH117
        with contextlib.suppress(OSError, ValueError):
            folder = os.path.realpath(folder)
    return os.path.normcase(os.path.join(folder, ""))  # noqa: PTH118


def same_location(left: str | Path, right: str | Path) -> bool:
    """Return True when *left* and *right* name the same location, case-folded where the OS is."""
    return os.path.normcase(str(_normalized(Path(left)))) == os.path.normcase(
        str(_normalized(Path(right)))
    )


def same_folder(left: str | Path, right: str | Path) -> bool:
    """Return True when the install roots *left* and *right* are one folder.

    Both must be absolute. They are one folder when they are the same text,
    or the same text with their links followed. Two that then differ only
    in case are one folder when both exist with one file ID (``st_dev`` and
    ``st_ino``, neither 0): on a volume that ignores case but keeps it, as
    macOS does, following the links keeps the case as spelled, while a
    case-sensitive folder (``Proj`` and ``proj``) holds two IDs. Case is
    never folded as text, and two names that differ otherwise are never
    joined by ID, since some network and cloud drives give every folder the
    same one. A pair this cannot tell apart counts as two folders, the side
    that keeps files. A link pointed at another folder after an install was
    recorded through it is not detected: its root and that folder's then
    count as one folder.
    """
    if not (os.path.isabs(left) and os.path.isabs(right)):  # noqa: PTH117
        return False
    if str(left) == str(right):
        return True
    try:
        first, second = os.path.realpath(left), os.path.realpath(right)
        if first == second:
            return True
        if first.lower() != second.lower():
            return False
        one, two = Path(first).stat(), Path(second).stat()
    except (OSError, ValueError):
        return False
    return bool(one.st_ino and one.st_dev) and os.path.samestat(one, two)


def same_folder_roots(harness: str, root: Path) -> tuple[str, ...]:
    """Return the other roots *harness*'s records spell *root*'s folder with.

    Each is a recorded root, as recorded, that is not *root*'s exact text,
    names the same folder (see :func:`same_folder`) and has an install still
    in place. The ledger finds an install's records by the root's exact text,
    so these are the same harness installed in the same folder under another
    spelling: the home reached through a link and the folder it leads to.
    They matter only as holders of the shared user-level folders, so a
    harness that writes none gets none (OpenCode closes its own other
    spelling). Empty when the ledger cannot be read; the caller that reads
    it next reports that.
    """
    if not writes_user_level(harness):
        return ()
    own = str(root)
    try:
        records = install_ledger.read_records(harness)
    except (install_ledger.LedgerError, OSError):
        return ()
    by_root: dict[str, list[install_ledger.LedgerRecord]] = {}
    for record in records:
        by_root.setdefault(record.root, []).append(record)
    return tuple(
        spelling
        for spelling, group in by_root.items()
        if spelling != own
        and install_ledger.active_install_ids(group)
        and same_folder(spelling, own)
    )


def _moves(other: str, root: Path) -> list[tuple[str, str]]:
    """Return the ``(from, to)`` folder pairs that spell a path of *other*'s under *root*.

    In order: *root* as spelled, *other*, *root* with its links followed,
    the home as spelled, the home with its links followed. A record keeps
    some paths resolved (the directories an install created), so both
    spellings of each folder are tried.
    """
    home, spelled = str(user_home()), str(root)
    pairs = [(spelled, spelled), (other, spelled)]
    with contextlib.suppress(OSError, ValueError):
        pairs.append((os.path.realpath(spelled), spelled))
    pairs.append((home, home))
    with contextlib.suppress(OSError, ValueError):
        pairs.append((os.path.realpath(home), home))
    return [(os.path.normcase(os.path.normpath(folder)), to) for folder, to in pairs]


def _respelled(path: str, moves: list[tuple[str, str]]) -> str | None:
    """Return *path* spelled under the folder of the first of *moves* that holds it.

    A path in a user-level folder that none holds moves under the current
    home, where the gate looks for it; ``None`` for any other path. The
    folded text only finds the folder: the parts below it keep their case.
    """
    lexical = os.path.normpath(path)
    folded = os.path.normcase(lexical)
    parts = Path(lexical).parts
    for folder, to in moves:
        base = folder.rstrip(os.sep)
        if folded in (folder, base):
            return to
        if folded.startswith(base + os.sep):
            return str(Path(to, *parts[len(Path(base).parts) :]))
    found = _SHARED_FOLDER.search(folded)
    if found is None:
        return None
    depth = len(Path(folded[: found.start()]).parts)
    return str(Path(user_home(), *parts[depth:]))


def _respelled_record(record: LedgerRecord, root: Path) -> LedgerRecord:
    """Return *record*, made under another spelling of *root*, spelled under *root*.

    A path that cannot be spelled under *root* or the home is left out.
    """
    moves = _moves(record.root, root)
    targets = []
    for target in record.targets:
        path = _respelled(target.path, moves)
        if path is not None:
            targets.append(replace(target, path=path))
    dirs = (_respelled(path, moves) for path in record.created_dirs)
    return replace(
        record,
        root=str(root),
        targets=tuple(targets),
        created_dirs=tuple(path for path in dirs if path is not None),
    )


def _with_provenance(target: LedgerTarget, maker: LedgerTarget | None) -> LedgerTarget:
    """Return *target* described by *maker*, the record entry that made it, if any.

    The entry of the install that made the file says what Apothem added
    (``created``, and the ``owned`` entries, containers included); the
    entries only *target* lists are added to them. *target*'s own path, and
    its digests, which describe the file as last written, are kept.
    """
    if maker is None or created_here(target):
        return target
    owned = maker.owned
    if target.owned:
        known = maker.owned or ()
        owned = (*known, *(entry for entry in target.owned if entry not in known))
    return replace(
        maker,
        path=target.path,
        digest=maker.digest if target.digest is None else target.digest,
        files=maker.files if target.files is None else target.files,
        owned=owned,
    )


def one_install(harness: str, root: Path) -> tuple[list[LedgerRecord], tuple[str, ...]]:
    """Return *harness*'s install at *root*, with its records under other spellings.

    The install is its records in place at *root*, oldest first. The records
    in place under each other spelling of the folder (see
    :func:`same_folder_roots`) are spelled under *root* and put first. The
    newest record at *root* stays last; it gains every file they list that it
    does not, and for a file one of them made (see
    :func:`~apothem.lib.install_ledger.created_here`) that entry's word of
    what Apothem added. The uninstall then removes what any of them shows
    Apothem wrote. Also returns those spellings, whose records the uninstall
    ends.
    """
    active = install_ledger.active_install_records(harness, root=root)
    same = same_folder_roots(harness, root) if active else ()
    if not same:
        return active, ()
    others = [
        _respelled_record(record, root)
        for spelling in same
        for record in install_ledger.active_install_records(harness, root=spelling)
    ]
    memo: dict[str, str] = {}
    makers = {
        path_key(target.path, memo): target
        for record in others
        for target in record.targets
        if created_here(target)
    }
    targets = [
        _with_provenance(target, makers.get(path_key(target.path, memo)))
        for target in active[-1].targets
    ]
    listed = {path_key(target.path, memo) for target in targets}
    for record in others:
        for target in record.targets:
            key = path_key(target.path, memo)
            if key not in listed:
                listed.add(key)
                targets.append(target)
    merged = replace(active[-1], targets=tuple(targets))
    return [*others, *active[:-1], merged], same


def made_keys(memo: dict[str, str] | None = None) -> frozenset[str]:
    """Return the keys of the paths an install made that nothing changed since.

    Across every harness that writes a user-level folder: a path an install
    record made (see :func:`~apothem.lib.install_ledger.created_here`) that
    no uninstall or rollback record lists from that record's time on. Such a
    record lists what its pass backed up before changing or removing it, so
    a folder Apothem made, then removed, and someone put back is not counted.

    Raises:
        apothem.lib.install_ledger.LedgerError: A ledger is corrupted.
        OSError: A ledger cannot be read.
    """
    memo = {} if memo is None else memo
    made: dict[str, str] = {}
    changed: dict[str, str] = {}
    for package_key in SUPPORTED_PACKAGE_KEYS:
        if not writes_user_level(package_key):
            continue
        for record in install_ledger.read_records(package_key):
            for target in record.targets:
                key = path_key(target.path, memo)
                if record.kind == "install":
                    if created_here(target):
                        made[key] = max(made.get(key, ""), record.timestamp)
                elif target.outcome not in {"skipped", "error"}:
                    changed[key] = max(changed.get(key, ""), record.timestamp)
    return frozenset(key for key, stamp in made.items() if changed.get(key, "") < stamp)


__all__ = [
    "made_keys",
    "one_install",
    "path_key",
    "same_folder",
    "same_folder_roots",
    "same_location",
]
