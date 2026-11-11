# SPDX-License-Identifier: MIT

"""Where an install's shared data stores live, as recorded on its ledger record.

Uninstall, rollback and the last-harness guard read the data home an install
recorded, so they reverse the stores where the install actually wrote them.
"""

from __future__ import annotations

import os
import unicodedata
from pathlib import Path

from apothem.lib import install_ledger
from apothem.lib.data_home import DataHome, DataHomeError, resolve_shared_data_home
from apothem.lib.harness_registry import SUPPORTED_PACKAGE_KEYS, get_harness_entry

from .install_driver_backup import backup_existing
from .install_driver_pathsafety import (
    _normalized,
    _remove_tree_keeping_links,
    _validate_target_path,
    _within_allowed_root,
    kept_links_detail,
)
from .install_driver_types import MaterializationResult, _result


def _same_path(left: Path, right: Path) -> bool:
    """Return True when *left* and *right* name the same location."""
    return os.path.normcase(str(_normalized(left))) == os.path.normcase(
        str(_normalized(right))
    )


def _same_home(left: Path, right: Path) -> bool:
    """Return True when the data homes *left* and *right* are one folder.

    As :func:`_same_path`, except that two existing folders the file system
    tells apart are two homes: in a case-sensitive folder ``Proj/.apothem``
    and ``proj/.apothem`` are two. Any doubt keeps them one, which keeps a
    store rather than removing it.
    """
    if not _same_path(left, right):
        return False
    try:
        return left.samefile(right)
    except OSError:
        return True


def _same_root(recorded: str, root: Path) -> bool:
    """Return True when the recorded root *recorded* is the install root *root*.

    The same text, or the same text once both are resolved (a link an
    earlier release recorded beside the folder it leads to). Case is never
    folded: in a case-sensitive folder ``Proj`` and ``proj`` resolve to two
    texts, and a folder that no longer exists keeps its case as typed, so
    any doubt counts the other root, which keeps a store rather than
    removing it.
    """
    if recorded == str(root):
        return True
    try:
        return str(Path(recorded).resolve()) == str(root.resolve())
    except (OSError, RuntimeError):
        return False


def _data_home_for(record: install_ledger.LedgerRecord | None, *, root: Path) -> Path:
    """Return the shared working directory the install recorded under *root*.

    An install pass writes its data stores under the home its profile resolved
    (see :func:`apothem.lib.data_home.resolve_install_data_home`) and records that
    home on its ledger record. Uninstall and rollback reverse the stores there,
    so the removal always targets what the install wrote.

    The recorded home is trusted only when it is ``<base>/<name>``, with *base*
    the install root or the user home and *name* a single path component. A
    ledger entry that names anything else falls through to the default. A record
    with no home (written before the field existed) and an absent record resolve
    to the default ``<root>/.apothem``, the location every install used before
    the field was recorded.
    """
    recorded = record.data_home if record is not None else None
    if recorded:
        home = Path(recorded)
        base = home.parent
        if _same_path(base, root) or _same_path(base, Path.home()):
            try:
                return resolve_shared_data_home(
                    base=base, directory_name=home.name
                ).root
            except DataHomeError:
                pass
    return resolve_shared_data_home(base=root).root


def _store_boundary(home: Path, *, allowed_root: Path) -> Path:
    """Return the write boundary the data stores under *home* are removed within.

    The install write root guards the default home, which sits inside it. A
    user-home store sits outside a project-scope write root by design, so the
    boundary widens to the base the home sits beneath. That base is already
    pinned to the install root or the user home by :func:`_data_home_for`.
    """
    if _within_allowed_root(_normalized(home), _normalized(allowed_root)):
        return allowed_root
    return home.parent


def _other_harness_shares_home(
    *, current_harness: str, shared_home: Path, current_root: Path | None = None
) -> bool:
    """Report whether another installed harness still shares *shared_home*.

    The shared data home is collapsed across harnesses, so removing it on the
    first uninstall would destroy data the remaining harnesses depend on. This
    consults the install ledger across every package key and returns ``True``
    when any other install is still in place at a root whose data home is
    *shared_home*. Only the install being removed (*current_harness* at
    *current_root*) is left out: the same harness installed at another root
    (a second project sharing the user-home store) still counts. That root is
    matched by its text, resolved or not, never with the case folded (see
    :func:`_same_root`), so a case-only sibling (``Proj`` beside ``proj`` in
    a case-sensitive folder) counts too.

    A harness is "still installed at a root" when its most recent ledger
    record of any kind for that root is an ``install``. The records are grouped
    by install root before the latest is taken. Grouping by home instead would
    let an ``uninstall`` marker (which carries no home) go unmatched, leaving the
    guard stuck on "retain". The home of each latest install record comes from
    :func:`_data_home_for`, so two roots that share a user-home store are both
    counted. The install being removed is excluded explicitly because its own
    ``uninstall`` record is appended only AFTER this guard runs (see
    :func:`run_uninstall`); with no *current_root*, every root of
    *current_harness* is left out.

    The check is fail-safe: any error reading the ledger raises out to the
    caller, which treats it as "cannot prove last-harness" and retains the
    shared home rather than risk a destructive removal on an uncertain count.
    """
    for package_key in SUPPORTED_PACKAGE_KEYS:
        if package_key == current_harness and current_root is None:
            continue
        # An install is in place at a root while the ledger's replay keeps it
        # active: a rollback of a later install, or an uninstall that did not
        # finish, leaves the earlier one active, and its home still in use.
        roots = {record.root for record in install_ledger.read_records(package_key)}
        for raw_root in sorted(roots):
            if package_key == current_harness and (
                current_root is None or _same_root(raw_root, current_root)
            ):
                continue
            current = install_ledger.current_install_record(package_key, root=raw_root)
            if current is None:
                continue
            if _same_home(_data_home_for(current, root=Path(raw_root)), shared_home):
                return True
    return False


def _holder(
    *, current_harness: str, shared_home: Path, current_root: Path
) -> tuple[str, str, bool] | None:
    """Return an install, other than the one being removed, that uses *shared_home*.

    The result is ``(package key, install root, whether that root is gone)``.
    An install whose folder still exists is returned first, so a gone one is
    returned only when every holder's folder is gone. ``None`` when none is
    found.
    """
    gone: list[tuple[str, str, bool]] = []
    for package_key in SUPPORTED_PACKAGE_KEYS:
        roots = {record.root for record in install_ledger.read_records(package_key)}
        for raw_root in sorted(roots):
            if package_key == current_harness and _same_root(raw_root, current_root):
                continue
            current = install_ledger.current_install_record(package_key, root=raw_root)
            if current is None or not _same_home(
                _data_home_for(current, root=Path(raw_root)), shared_home
            ):
                continue
            if Path(raw_root).exists():
                return (package_key, raw_root, False)
            gone.append((package_key, raw_root, True))
    # A project install's steps are plain commands; a user-scope one's folder
    # may have come from a setting the steps cannot repeat, so it goes last.
    gone.sort(key=lambda holder: get_harness_entry(holder[0]).scope != "project")
    return gone[0] if gone else None


#: What the quotes around a printed folder cannot carry, besides a control
#: character. Windows prints double quotes, inside which PowerShell expands
#: ``$`` and the backquote (and also reads the curly double quotes as quotes)
#: and cmd expands ``%`` and ``!``. Elsewhere single quotes, which a single
#: quote ends, and in PowerShell also the curly single quotes.
_UNQUOTABLE = {
    True: frozenset('$`%!"' + "".join(map(chr, (0x201C, 0x201D, 0x201E)))),
    False: frozenset("'" + "".join(map(chr, (0x2018, 0x2019, 0x201A, 0x201B)))),
}


def shell_quoted(path: str, *, windows: bool | None = None) -> str | None:
    """Return *path* quoted for a command the operator pastes into a shell.

    On Windows (*windows*, by default this host) the path goes in double
    quotes, with each trailing backslash doubled so the closing quote stays a
    quote (``C:\\`` becomes ``"C:\\\\"``); elsewhere in single quotes. ``None``
    when those quotes cannot carry the path (see :data:`_UNQUOTABLE`), and on
    Windows also when two backslashes stand together before its end, as at
    the start of a network share (``\\\\server\\share``): Git Bash reads them
    as one inside double quotes.
    """
    windows = os.name == "nt" if windows is None else windows
    if any(
        char in _UNQUOTABLE[windows] or unicodedata.category(char) == "Cc"
        for char in path
    ):
        return None
    if not windows:
        return f"'{path}'"
    bare = path.rstrip("\\")
    if "\\\\" in bare:
        return None
    return '"' + bare + "\\" * (2 * (len(path) - len(bare))) + '"'


def _release_steps(home: Path, package_key: str, root: str) -> str:
    """Say why the stores in *home* stayed and give the steps that release them.

    The install at *root* keeps them, and *root* no longer exists. Uninstalling
    in an empty recreated folder finds nothing installed, so the steps install
    there again, then uninstall there. The stores sit outside *root*, so that
    install used a profile whose workspace puts them in *home*: the reinstall
    needs that profile too, or it writes stores of its own and leaves these
    with no install that uses them. A project install gets the exact commands,
    the folder quoted for the shell (see :func:`shell_quoted`), or the steps
    in words, naming the folder as it is, when the quotes cannot carry it. A
    user-scope install's folder may have come from a setting (``CODEX_HOME``,
    ``XDG_CONFIG_HOME``) the commands cannot repeat, so it gets the steps in
    words: a bare command would act on the default folder.
    """
    entry = get_harness_entry(package_key)
    stores = "its memory, contexts and learning folders"
    quoted = shell_quoted(root) if entry.scope == "project" else None
    if quoted is not None:
        where = f" --project {quoted}"
        steps = (
            f"create {quoted} again, then run apothem install "
            f"--harness {entry.public_id}{where} --profile <the profile it "
            f"used>, then apothem uninstall --harness {entry.public_id}{where} "
            "--yes"
        )
    elif entry.scope == "project":
        steps = (
            f"recreate {root}, run apothem install --harness {entry.public_id} "
            "with --project set to that folder and --profile set to the "
            "profile it used, then apothem uninstall with the same --harness "
            "and --project"
        )
    else:
        steps = (
            f"recreate {root} with the settings that install ran with, if any "
            f"(such as CODEX_HOME or XDG_CONFIG_HOME), install {entry.public_id} "
            "there with the profile it used, then uninstall it there"
        )
    return (
        f"{home} was kept: {entry.public_id} installed at {root} still uses "
        f"{stores}, and that folder no longer exists. To release them, {steps}. "
        f"The profile is the one whose workspace puts the stores in {home}. Or "
        f"remove {stores} by hand"
    )


def _remove_data_home(
    harness_name: str,
    *,
    root: Path,
    allowed_root: Path,
    home: Path | None = None,
) -> MaterializationResult | None:
    """Back up and remove the shared data home only when it is last-referenced.

    *home* is the shared Apothem working directory the install under *root*
    wrote its data stores into, as :func:`_data_home_for` resolves it from the
    install record. When omitted it is the default ``<root>/.apothem/``. The
    directory is shared across every harness that resolves to the same home,
    holding the operator's memory records, context fragments, and learning
    signals (see :func:`apothem.lib.data_home.resolve_shared_data_home`).
    Because it is SHARED, removing it on the first harness uninstall would
    destroy data the other still-installed harnesses depend on. The removal is
    therefore conditional:

    * If another installed harness still shares this home, the home is RETAINED
      and an informational ``unchanged`` result is returned.
    * If this is the last harness referencing the home, only the data stores
      (``memory/``, ``contexts/``, ``learning/``) are backed up and removed.
      ``plans/`` is NEVER auto-removed — it is operator planning state, not
      Apothem-materialized config — and the working directory itself is left
      in place so any operator ``plans/`` survives. Each removed child is copied
      into the Apothem backup root first, so the data stays recoverable.

    Returns ``None`` when no data store exists (nothing to remove) or the home
    path falls outside the write boundary (see :func:`_store_boundary`).
    """
    if home is None:
        home = _data_home_for(None, root=root)
    if not home.exists():
        return None
    boundary = _store_boundary(home, allowed_root=allowed_root)
    if (
        _validate_target_path(home, allowed_root=boundary, operation="remove_data_home")
        is not None
    ):
        return None

    # Last-harness guard: retain the shared home while another harness still
    # references it. An uncertain ledger read raises and is caught here, falling
    # back to RETAIN — the safe default that never risks shared-data loss.
    try:
        retain = _other_harness_shares_home(
            current_harness=harness_name, shared_home=home, current_root=root
        )
    except Exception:  # pragma: no cover - defensive: ledger read is robust
        retain = True
    if retain:
        try:
            holder = _holder(
                current_harness=harness_name, shared_home=home, current_root=root
            )
        except Exception:  # pragma: no cover - defensive: ledger read is robust
            holder = None
        if holder is not None and holder[2]:
            # The install that keeps the store cannot be uninstalled where it
            # was, so say why the store stayed and what removes it.
            return _result(
                "warning",
                "remove_data_home",
                home,
                _release_steps(home, holder[0], holder[1]),
            )
        return _result(
            "unchanged",
            "remove_data_home",
            home,
            "shared data home retained — another harness is still installed"
            + (f" ({holder[0]} installed at {holder[1]})" if holder else ""),
        )

    spec = DataHome.from_root(home)
    backups: list[Path] = []
    kept: list[Path] = []
    removed_any = False
    # plans/ is intentionally excluded — operator planning state is never
    # auto-removed by uninstall.
    for child in (spec.memory, spec.contexts, spec.learning):
        if not child.exists():
            continue
        backup = backup_existing(
            child,
            install_root=root,
            harness_name=harness_name,
            allowed_root=boundary,
        )
        if backup is not None:
            backups.append(backup)
        kept.extend(_remove_tree_keeping_links(child))
        removed_any = True
    if not removed_any:
        return None
    return _result(
        "updated",
        "remove_data_home",
        home,
        "removed shared data stores (memory, contexts, learning); plans retained",
        backup_path=backups[0] if backups else None,
        detail=kept_links_detail(kept),
    )
