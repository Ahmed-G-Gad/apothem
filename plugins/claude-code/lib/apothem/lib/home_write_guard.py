# SPDX-License-Identifier: MIT

"""Refuse writes into the account's real home while pytest runs.

The repository's ``tests/conftest.py`` points every test at temporary folders,
but a test run that does not load it (a test file copied out of ``tests/`` and
run with ``-c``, ``-o addopts=`` or ``--rootdir`` elsewhere) runs Apothem
against the account's real home. This module stops such a write before it
happens.

While ``PYTEST_CURRENT_TEST`` is set, or ``PYTEST_VERSION`` holds the version
of the pytest that runs in this process (pytest sets the first for each test's
setup, call and teardown, and pytest 8.2 and later the second, to its own
version, for the whole session, so collection, module-level code and session
hooks count too), :func:`refuse_real_home_write` raises
:class:`RealHomeWriteError` for a path at or inside one of these folders of
the account's home:

- ``.apothem`` (install records, locks, backup sets, a user-scope data home);
- ``.config/apothem``;
- the tools' own folders that the harness registry's ``~/`` targets and shared
  roots name (``.claude``, ``.codex``, ``.agents``, ``.config/opencode`` and the
  rest);
- each path outside those folders that the propagation manifest's installs
  and stale sweeps change in the home, by itself: the file an earlier release
  wrote, ``.antigravity/profile.yaml``, which the Antigravity stale sweep
  removes (:data:`FALLBACK_ROOTS` lists these and the tools' folders).

With ``tree=True`` (removing or moving a whole folder) a path that holds one of
those folders is refused too. :func:`refuse_project_root_at_home` refuses a
project root that is the home itself, which a project-scope pass calls before
its first write, and :func:`refuse_data_home_in_home` a data home right in
the home under any name (a profile with the ``user-home`` workspace scope and
its own ``directory_name``), or one that is a link to the home itself, before
it is created or its stores are removed.
Nothing else is refused: reads, dry runs and previews, the
temporary folder, the checkout, and the rest of the home all stay allowed.

The running pytest's version is the ``__version__`` of its ``_pytest``
package, the string pytest puts in ``PYTEST_VERSION``, so a stale
``pytest-*.dist-info`` earlier on ``sys.path``, or a pytest run from a source
tree that names itself ``unknown``, changes nothing. In a process that has not
imported pytest (a child process a session started, say), ``PYTEST_VERSION``
counts when it holds the version of the pytest installed for this Python,
read from its package metadata only while ``PYTEST_VERSION`` is set; the
answer is kept for the process, a failed lookup (no pytest installed)
included. A ``PYTEST_VERSION`` with any other value (an empty one, or a pin
such as ``8.2`` that a shell or a CI job exports) does not count. One that a shell or a CI job exports with the
installed pytest's exact version (``9.1.0`` beside ``pip install
pytest==9.1.0``) counts all the same, outside pytest too: the refusal message
then says that ``PYTEST_VERSION`` alone turned the guard on, in a process that
runs no pytest. With both variables unset a check is two environment lookups.
A ``PYTEST_VERSION`` that does not count adds a comparison with that version,
and, in a process that runs no pytest, one package metadata lookup on the
first check. The refusal message names the variable that turned the guard on.

A path is compared as written and as resolved through links, afresh on every
check, so a folder swapped for a link during a test counts at once. The
protected folders' own resolved spellings are kept only while each home and
its ``.config``, and the folder either leads to when it is a link, stay as
they were (see :func:`_layout`).

On Windows a ``\\\\?\\``, ``\\\\.\\`` or ``\\??\\`` prefix (with either
slash), a loopback admin share (``\\\\localhost\\C$``, ``\\\\127.0.0.1\\C$``,
``\\\\--1.ipv6-literal.net\\C$``, the machine's own name), a short (8.3) name
and an alternate data stream (``.apothem:name``) all read as the plain
drive-letter path. A device path behind one of those prefixes
(``GLOBALROOT\\Device\\HarddiskVolume2\\x``, ``Volume{GUID}\\x``) is resolved
to the drive-letter path it names. Any other share path, written so or
reached through a mapped drive, is compared by file identity with the
protected folders and the folders above them, folder by folder up to the
share, so one of this machine's own addresses counts too. Only the string
rules make no network contact: resolving a share path (a path on a mapped
drive included) asks its host, and so does comparing it by identity, which
reads each share folder at most once in a check and stops at the first error
that says the host or the share cannot be reached.

On macOS letter case and Unicode normalization are ignored, as the default
volume format does, and ``/System/Volumes/Data/<path>``, the data volume that
``/Users`` and the rest of it are firmlinked from, reads as ``/<path>``.
Linux compares names as they are. On Linux and macOS no file identity is
compared, so a bind mount of the home or a case-insensitive Linux mount is
judged by its spelling.

The account home comes from the operating system (``FOLDERID_Profile`` on
Windows, the ``passwd`` entry elsewhere), never from ``HOME`` or ``USERPROFILE``:
under ``tests/conftest.py`` those name a temporary folder. The system functions
the lookup calls are bound when this module is imported, so a test that later
replaces ``pwd.getpwuid``, part of ``ctypes`` or ``winreg`` cannot change the
home found or poison its cache. When the system has no answer (a container user
with no ``passwd`` entry, say), the account home is not protected at all: only
the homes a test added with :func:`also_protect_home` are, and the failed lookup
is tried again on the next check. ``HOME`` is no fallback, because under
``tests/conftest.py`` it can already name a test's temporary folder. No
environment variable, setting or flag turns the refusal off; a test that runs a
real install on purpose starts Apothem without ``PYTEST_CURRENT_TEST`` and
``PYTEST_VERSION`` in the child's environment.

Every refusal is logged in this process (:func:`refusals`,
:func:`drain_refusals`) and written to ``stderr`` once per protected folder in
each test (or, outside any test, in the pytest session), so a caller that
absorbs the error still leaves a trace that ``tests/conftest.py`` reports.
The log is per process: a refusal a child process absorbs shows only as the
child's ``stderr`` line. A child process that inherits only
``PYTEST_VERSION`` (one started outside any test) is guarded only when its
Python has the same pytest installed. The check runs before the write and by
path, so a folder swapped for a link between the two is not seen.

Nothing here holds a path at module level, and nothing is looked up at import:
the suite's scan for module-level paths naming the real home stays clean.
"""

from __future__ import annotations

import contextlib
import functools
import importlib
import ipaddress
import ntpath
import os
import posixpath
import re
import stat
import sys
import time
import unicodedata
from collections.abc import Callable, Iterable, Mapping
from typing import Any, TypeGuard

#: The variable pytest sets for each test's setup, call and teardown.
PYTEST_VARIABLE = "PYTEST_CURRENT_TEST"

#: The variable pytest 8.2 and later sets, to its own version, for the whole
#: session: collection, module-level code and session hooks run with it,
#: outside any test. It counts only while it holds the version of the pytest
#: installed for this Python (see :func:`active`).
PYTEST_SESSION_VARIABLE = "PYTEST_VERSION"

#: What a refusal outside any test names in place of the test.
_SESSION = "the pytest session"

#: Apothem's own folders in the home, relative to it.
APOTHEM_ROOTS: tuple[str, ...] = (".apothem", ".config/apothem")

#: The tools' folders in the home the harness registry names, and the paths
#: outside them the propagation manifest changes there, used when the registry
#: or the manifest cannot be loaded. A unit test pins it equal to the derived
#: set.
FALLBACK_ROOTS: tuple[str, ...] = (
    ".agents",
    ".antigravity/profile.yaml",
    ".claude",
    ".codebuddy",
    ".codex",
    ".config/apothem",
    ".config/opencode",
    ".gemini",
    ".hermes",
    ".kiro",
    ".openclaw",
    ".qwen",
    ".trae",
)

#: How many refusals the in-process log keeps.
_LOG_LIMIT = 100

#: ``FOLDERID_Profile``, the account's profile folder on Windows.
_FOLDERID_PROFILE = "5E6C858F-0E22-4760-9AFE-EA3317B67173"

#: What one home lookup may raise when the system, or a test's stand-in for
#: part of ``ctypes`` or ``winreg``, cannot answer: the next lookup is tried.
_LOOKUP_ERRORS = (
    ImportError,
    LookupError,
    OSError,
    AttributeError,
    TypeError,
    ValueError,
    RuntimeError,
)

#: Fold letter case and Unicode normalization on both sides of a match. macOS
#: volumes ignore both by default and ``os.path.normcase`` folds nothing on
#: POSIX; Windows folds case through ``normcase``, and Linux compares names as
#: they are. Tests switch it.
_FOLD_CASE: bool = sys.platform == "darwin"

#: Read ``/System/Volumes/Data/<path>`` as ``/<path>``. From macOS 10.15 the
#: data volume is mounted there and firmlinked into ``/`` (``/Users`` among
#: the rest), so both spellings name one folder, and ``os.path.realpath``
#: leaves the first as written. Tests switch it.
_DATA_VOLUME_FIRMLINK: bool = sys.platform == "darwin"

#: Where macOS mounts the data volume.
_DATA_VOLUME = "/System/Volumes/Data"

#: An admin share of a drive (``C$``) and a loopback IPv4 host (``127.x.y.z``).
_ADMIN_SHARE = re.compile(r"[a-z]\$", re.IGNORECASE)
_LOOPBACK_V4 = re.compile(r"127\.\d{1,3}\.\d{1,3}\.\d{1,3}")

#: The domain Windows ends an IPv6 address with in a UNC host name.
_IPV6_LITERAL = ".ipv6-literal.net"

#: How long, in nanoseconds, a home and its ``.config`` must have stayed
#: unchanged before the protected folders resolved under them are reused. A
#: change within one tick of the file system clock (up to about 16 ms) can
#: leave a folder's timestamp as it was.
_SETTLE_NS = 100_000_000

#: The NT object-namespace prefixes, lower case, with what replaces each. A
#: file call passes ``\\??\\C:\\x`` through to the NT path ``C:\\x`` as written,
#: while ``os.path.abspath`` reads it as a folder ``??`` on the current drive.
#: ``\\\\?\\`` passes a path through the same way, so a device path after the
#: prefix (``GLOBALROOT\\Device\\HarddiskVolume2``, ``Volume{GUID}``) stays
#: absolute and is resolved like any other path.
_NT_PREFIXES: tuple[tuple[str, str], ...] = (
    ("\\??\\unc\\", "\\\\"),
    ("\\??\\", "\\\\?\\"),
)

#: The path prefixes that name the same file as the plain path after them,
#: lower case, with what replaces each.
_PREFIXES: tuple[tuple[str, str], ...] = (
    ("\\\\?\\unc\\", "\\\\"),
    ("\\\\.\\unc\\", "\\\\"),
    ("\\\\?\\", ""),
    ("\\\\.\\", ""),
    ("\\??\\unc\\", "\\\\"),
    ("\\??\\", ""),
)

#: The Windows errors that say a share's host, or the share itself, cannot be
#: reached: bad network path or name, no network, host or network
#: unreachable, a dropped or timed-out connection, a mapped drive not
#: connected.
_UNREACHABLE_ERRORS = frozenset({51, 53, 59, 64, 67, 121, 1222, 1231, 1232, 2250})

#: Homes a test added with :func:`also_protect_home` (temporary folders only).
_extra_homes: list[str] = []
#: The refusal log, a list of exceptions.
_refusals: list[RealHomeWriteError] = []
#: The test whose refusals were last written to ``stderr``, and the protected
#: folders already written for it.
_announced: dict[str, set[str]] = {}


def _bind_system() -> dict[str, Any]:
    """Return the system functions the home lookup calls, bound at import.

    Binding a function object looks nothing up. A test that replaces one of
    them in its module later cannot change what the lookup calls.
    """
    wanted = (
        {
            "ctypes": (
                "WinDLL",
                "Structure",
                "c_uint32",
                "c_uint16",
                "c_ubyte",
                "c_long",
                "c_wchar_p",
                "byref",
            ),
            "uuid": ("UUID",),
            "winreg": ("OpenKey", "QueryValueEx", "HKEY_CURRENT_USER"),
        }
        if os.name == "nt"
        else {"pwd": ("getpwuid",), "os": ("geteuid", "getuid")}
    )
    bound: dict[str, Any] = {}
    for module_name, names in wanted.items():
        try:
            module = importlib.import_module(module_name)
        except ImportError:
            continue
        for name in names:
            if hasattr(module, name):
                bound[f"{module_name}.{name}"] = getattr(module, name)
    return bound


#: ``module.name`` -> the function or constant the home lookup calls.
_SYSTEM: dict[str, Any] = _bind_system()


class RealHomeWriteError(OSError):
    """A write into the account's real home, refused while pytest runs.

    It is an :class:`OSError` built from its message alone, so ``errno`` and
    ``winerror`` stay ``None`` and no retry on a sharing violation picks it up.
    The keyword arguments default to ``""`` so that a copy, or a pickle that
    crosses a process boundary, can rebuild the error from its message; the
    attributes then come back from the instance dictionary.
    """

    def __init__(
        self,
        message: str,
        *,
        path: str = "",
        protected_root: str = "",
        operation: str = "",
    ) -> None:
        super().__init__(message)
        self.path = path
        self.protected_root = protected_root
        self.operation = operation


class _HomeLookupError(Exception):
    """The system has no record of this account's home."""


class _UnreachableShareError(Exception):
    """A share's host, or the share itself, cannot be reached."""


def active() -> bool:
    """Return True while pytest runs.

    That is while ``PYTEST_CURRENT_TEST`` is set, whatever its value (a test),
    or while ``PYTEST_VERSION`` holds the version of the pytest that runs in
    this process (the whole session, pytest 8.2 and later), or, in a process
    that has not imported pytest, of the pytest installed for this Python.
    Any other ``PYTEST_VERSION`` (an empty one, or a pin such as ``8.2``) does
    not count: a shell or a CI job may export that name for its own use. An
    exported value equal to the installed version counts, outside pytest too.
    """
    return _turned_on_by() is not None


def _turned_on_by() -> str | None:
    """Return the variable that turns the guard on now, or None.

    The pytest version is looked up only while ``PYTEST_VERSION`` is set and
    not empty, so with both variables unset this is two environment lookups.
    """
    environ = os.environ
    if PYTEST_VARIABLE in environ:
        return PYTEST_VARIABLE
    if _session_counts(environ.get(PYTEST_SESSION_VARIABLE)):
        return PYTEST_SESSION_VARIABLE
    return None


def _session_counts(value: str | None) -> bool:
    """Return True when *value*, as ``PYTEST_VERSION``, turns the guard on.

    That is when it is the version :func:`_pytest_version` returns.
    """
    return bool(value) and value == _pytest_version()


def _pytest_version() -> str | None:
    """Return the version ``PYTEST_VERSION`` has to hold to turn the guard on.

    In a process that has imported pytest, that is the ``__version__`` of its
    ``_pytest`` package: the string pytest's ``main`` puts in the variable,
    whatever the package metadata says. In any other process (a child process
    a session started, say) it is the version of the pytest installed for
    this Python (:func:`_installed_pytest_version`). None when the one it
    needs is not known: then no ``PYTEST_VERSION`` counts.
    """
    running = sys.modules.get("_pytest")
    if running is None:
        return _installed_pytest_version()
    found: object = getattr(running, "__version__", None)
    return found if isinstance(found, str) and found else None


@functools.cache
def _installed_pytest_version() -> str | None:
    """Return the version of the pytest installed for this Python, or None.

    It comes from the package metadata (``importlib.metadata``), looked up on
    first use, never at import. The answer is kept for the process, a failed
    lookup (no pytest installed, or metadata that cannot be read) included:
    a process that runs no pytest does not gain one, and an installer's copy
    of Apothem in a Python with no pytest would otherwise read the metadata
    again on each of the thousands of checks a run makes.
    """
    try:
        metadata = importlib.import_module("importlib.metadata")
        found: object = metadata.version("pytest")
    except _LOOKUP_ERRORS:
        return None
    return found if isinstance(found, str) and found else None


def account_home() -> str | None:
    """Return the account's home as the operating system records it, or None."""
    try:
        return _os_account_home()
    except _HomeLookupError:
        return None


def protected_roots() -> tuple[str, ...]:
    """Return every protected folder, under the account home and added homes."""
    seen: dict[str, None] = {}
    for _keys, shown in _roots(account_home(), tuple(_extra_homes)):
        seen[shown] = None
    return tuple(seen)


def refusals() -> tuple[RealHomeWriteError, ...]:
    """Return the refusals logged in this process, oldest first."""
    return tuple(_refusals)


def drain_refusals() -> tuple[RealHomeWriteError, ...]:
    """Return the logged refusals and empty the log."""
    drained = tuple(_refusals)
    _refusals.clear()
    return drained


def also_protect_home(path: str | os.PathLike[str]) -> None:
    """Protect the same folders under *path* as under the account home.

    A test seam: it only adds a home and can never replace or remove the
    account's own, so no test can weaken the refusal.
    """
    _extra_homes.append(_absolute(os.fspath(path)))
    _resolved_roots.cache_clear()


def clear_extra_homes() -> None:
    """Forget every home added with :func:`also_protect_home`."""
    _extra_homes.clear()
    _resolved_roots.cache_clear()


def would_refuse(path: str | os.PathLike[str], *, tree: bool = False) -> bool:
    """Return True when :func:`refuse_real_home_write` would refuse *path*.

    It never raises and logs nothing, for code that must not raise.
    """
    try:
        return _protected_root_of(os.fspath(path), tree=tree) is not None
    except (OSError, ValueError, TypeError):
        return False


def refuse_real_home_write(
    *paths: str | os.PathLike[str], operation: str, tree: bool = False
) -> None:
    """Raise :class:`RealHomeWriteError` for the first path that may not change.

    A path may not change while pytest runs when it is at or inside a
    protected folder (see the module docstring); with *tree* also when a
    protected folder is at or below it. *operation* is a verb phrase for the
    message (``write``, ``create the lock file``, ``remove``).
    """
    for path in paths:
        text = os.fspath(path)
        root = _protected_root_of(text, tree=tree)
        if root is not None:
            _refuse(
                f"Apothem refused to {operation} {text}: it is inside or holds "
                f"{root}, a protected path in this account's real home, while "
                f"{_running()}. Nothing in {root} was changed. Fix: {_FIX}",
                path=text,
                root=root,
                operation=operation,
            )


def would_refuse_project_root(project_root: str | os.PathLike[str]) -> bool:
    """Return True when :func:`refuse_project_root_at_home` would refuse.

    It never raises and logs nothing, for code that must not raise.
    """
    try:
        return _home_at(os.fspath(project_root)) is not None
    except (OSError, ValueError, TypeError):
        return False


def refuse_project_root_at_home(
    project_root: str | os.PathLike[str], *, operation: str
) -> None:
    """Raise :class:`RealHomeWriteError` when *project_root* is an account home.

    While pytest runs, a project-scope pass (install, update, uninstall,
    rollback) whose project root is the account home, or a home added with
    :func:`also_protect_home`, would write project files straight into that
    home. The pass calls this before its first write, so a refusal leaves the
    project untouched. Every spelling the write checks recognise counts (a link
    to the home, a short name, a loopback admin share). Only the home itself
    is refused: a project folder inside the home stays allowed, and one inside
    a protected folder is refused by the write checks. *operation* names the
    pass for the message (``install``, ``update``, ``uninstall``,
    ``roll back``).
    """
    text = os.fspath(project_root)
    home = _home_at(text)
    if home is not None:
        _refuse(
            f"Apothem refused to {operation} with the project root {text}: it is "
            f"{home}, this account's real home, while {_running()}. It stopped "
            "before writing anything for this project. Fix: pass a temporary "
            f"folder as the project root; or {_FIX}",
            path=text,
            root=home,
            operation=operation,
        )


def refuse_data_home_in_home(
    data_home: str | os.PathLike[str], *, operation: str
) -> None:
    """Raise :class:`RealHomeWriteError` when *data_home* sits right in a home.

    A profile with the ``user-home`` workspace scope puts the data home at
    ``<home>/<directory_name>``, and the name is the profile's to choose, so
    no fixed protected folder covers it: ``.apothem`` is one, any other name
    is not. While pytest runs, a data home whose folder is the account home
    or a home added with :func:`also_protect_home` (any spelling
    :func:`refuse_project_root_at_home` accepts) is refused before it is
    created or its stores are removed. The data home itself is resolved too,
    as the project-root check resolves a root, so one that is a link (a
    junction on Windows) to a folder right in a home is refused as well, and
    so is one that leads to a home itself, directly or through a chain of
    links, whose stores would land right in that home. One that does not
    exist yet is judged by its folder alone, and a data home written as a
    home itself is left alone. A data home anywhere else, in a project or a
    tool folder, is left to the write checks. *operation* is a verb phrase
    for the message. Outside pytest it returns before any path work, so it
    costs what :func:`active` costs.
    """
    if not active():
        return
    text = os.fspath(data_home)
    absolute = _absolute(text)
    folder, leaf = os.path.split(absolute)
    real_folder = _real_target(folder)
    real = _real_target(absolute)
    home = _home_among((_canonical(folder), real_folder, os.path.dirname(real)))
    reason = "is a data home right in"
    if home is None and real not in (
        _canonical(absolute),
        _canonical(os.path.join(real_folder, leaf)),
    ):
        # The data home is a link, or reached through one: where it leads
        # counts as well.
        home = _home_among((real,))
        reason = "leads to"
    if home is not None:
        _refuse(
            f"Apothem refused to {operation} {text}: it {reason} {home}, this "
            f"account's real home, while {_running()}. Nothing in {text} was "
            f"changed. Fix: {_FIX}",
            path=text,
            root=home,
            operation=operation,
        )


#: The fix every refusal message ends with.
_FIX = (
    "run the test from the repository's tests/ folder so tests/conftest.py "
    "loads; or, before the test writes, point HOME and USERPROFILE at a "
    "temporary folder and set apothem.lib.install_ledger.STATE_ROOT and "
    "apothem.harnesses._shared.install_driver.BACKUP_ROOT to temporary folders. "
    "To run a real install on purpose, start Apothem without "
    f"{PYTEST_VARIABLE} and {PYTEST_SESSION_VARIABLE} in its environment."
)


def _running() -> str:
    """Return what is running, for a message, and the variable that says so.

    That is the test, while ``PYTEST_CURRENT_TEST`` is set, and otherwise the
    pytest session, outside any test, whose ``PYTEST_VERSION`` matches the
    running pytest (:func:`active`). In a process that has not imported
    pytest (one a session started, or one whose shell or CI job exports the
    installed pytest's exact version), no pytest is running: the message says
    that ``PYTEST_VERSION`` alone turned the guard on.

    Each variable is read once. pytest takes ``PYTEST_CURRENT_TEST`` out of the
    environment at the end of each test's teardown, so a check made just before
    (in a test's background thread, say) can find it set and this find it gone;
    with ``PYTEST_VERSION`` not counting either, the message then names the
    pytest session alone, and the refusal is still raised as it is.
    """
    environ = os.environ
    test = environ.get(PYTEST_VARIABLE)
    if test is not None:
        shown = f": {test}" if test else ""
        return f"a pytest test is running ({PYTEST_VARIABLE} is set{shown})"
    version = environ.get(PYTEST_SESSION_VARIABLE, "")
    if not _session_counts(version):
        return f"pytest is running ({_SESSION}, outside any test)"
    if "_pytest" not in sys.modules:
        return (
            f"{PYTEST_SESSION_VARIABLE} holds the installed pytest's version, "
            f"{version}, though no pytest runs in this process"
        )
    return (
        f"pytest is running ({_SESSION}, outside any test: "
        f"{PYTEST_SESSION_VARIABLE} matches the running pytest {version})"
    )


def _refuse(message: str, *, path: str, root: str, operation: str) -> None:
    """Log, report once per protected folder and test, and raise the refusal."""
    error = RealHomeWriteError(
        message, path=path, protected_root=root, operation=operation
    )
    if len(_refusals) < _LOG_LIMIT:
        _refusals.append(error)
    test = _test_id(os.environ.get(PYTEST_VARIABLE, "")) or _SESSION
    if test not in _announced:
        _announced.clear()
        _announced[test] = set()
    if root not in _announced[test]:
        _announced[test].add(root)
        with contextlib.suppress(OSError, ValueError, AttributeError):
            sys.stderr.write(f"{type(error).__name__}: {message}\n")
    raise error


def _test_id(current: str) -> str:
    """Return the test id of a ``PYTEST_CURRENT_TEST`` value, without its phase."""
    for phase in (" (setup)", " (call)", " (teardown)"):
        if current.endswith(phase):
            return current[: -len(phase)]
    return current


def _protected_root_of(path: str, *, tree: bool) -> str | None:
    """Return the protected folder *path* is in (or, with *tree*, holds)."""
    if not active():
        return None
    roots = _roots(account_home(), tuple(_extra_homes))
    if not roots:
        return None
    absolute = _absolute(path)
    lexical = _canonical(absolute)
    found = _match(lexical, roots, tree=tree)
    if found is not None:
        return found
    real = _real_target(absolute)
    found = _match(real, roots, tree=tree)
    if found is not None:
        return found
    for twin in _local_twins((lexical, real), roots):
        found = _match(twin, roots, tree=tree)
        if found is not None:
            return found
    return None


def _home_at(path: str) -> str | None:
    """Return the account home, or added home, that *path* names, or None."""
    if not active():
        return None
    absolute = _absolute(path)
    return _home_among((_canonical(absolute), _real_target(absolute)))


def _home_among(spellings: tuple[str, ...]) -> str | None:
    """Return the account home, or added home, one of *spellings* names.

    *spellings* are canonical (:func:`_canonical`). A share path among them
    is placed by file identity as well (:func:`_local_twins`), each share
    folder read at most once for all of them.
    """
    homes = [
        (home, {_folded(_canonical(home)), _folded(_canonical(_realpath(home)))})
        for home in (account_home(), *_extra_homes)
        if home is not None
    ]
    found = list(dict.fromkeys(spellings))
    if any(_is_share(spelling) for spelling in found):
        roots = _roots(account_home(), tuple(_extra_homes))
        found += _local_twins(tuple(found), roots)
    for spelling in found:
        for home, keys in homes:
            if _folded(spelling) in keys:
                return home
    return None


def _absolute(path: str) -> str:
    """Return *path* made absolute, with an NT object-namespace prefix read first.

    On Windows ``\\??\\UNC\\host\\share\\x`` (with either slash) reads as
    ``\\\\host\\share\\x`` and any other ``\\??\\x`` as ``\\\\?\\x``, which a file
    call passes through to the same NT path. So ``\\??\\C:\\x`` reads as
    ``C:\\x``, and a device path such as
    ``\\??\\GLOBALROOT\\Device\\HarddiskVolume2\\x`` or ``\\??\\Volume{GUID}\\x``
    stays absolute and is resolved to the drive path it names.
    ``os.path.abspath`` alone would read each as a folder ``??`` on the current
    drive, and dropping the prefix would leave a device path relative to the
    current folder.
    """
    if os.name == "nt":
        flipped = path.replace("/", "\\")
        lowered = flipped[:8].lower()
        for prefix, replacement in _NT_PREFIXES:
            if lowered.startswith(prefix):
                path = replacement + flipped[len(prefix) :]
                break
    return os.path.abspath(path)


def _folded(path: str) -> str:
    """Return *path* folded when :data:`_FOLD_CASE` is set.

    That is letter case and Unicode normalization (``é`` written as one
    character or as ``e`` and an accent), both of which a macOS volume
    ignores by default.
    """
    if not _FOLD_CASE:
        return path
    return unicodedata.normalize("NFD", unicodedata.normalize("NFD", path).casefold())


def _match(
    target: str, roots: tuple[tuple[tuple[str, ...], str], ...], *, tree: bool
) -> str | None:
    """Return the shown root whose spelling holds *target* (or *target* holds)."""
    target = _folded(target)
    for keys, shown in roots:
        for raw in keys:
            key = _folded(raw)
            if target == key or target.startswith(key + os.sep):
                return shown
            if tree and key.startswith(target.rstrip(os.sep) + os.sep):
                return shown
    return None


def _real_target(absolute: str) -> str:
    """Return *absolute* resolved through links, canonical.

    A path that exists is resolved whole, so a link at its leaf and a short
    (8.3) name in its last part count too; for one that does not exist yet
    its folder is resolved and the leaf kept as written. Nothing is cached: a
    folder swapped for a link (or back) during a test is judged by what it is
    now. A path whose share host cannot be reached is not resolved: asking
    again, folder by folder, would only wait on the network once more.
    """
    try:
        os.lstat(absolute)
    except (OSError, ValueError) as error:
        if isinstance(error, OSError) and _unreachable(error):
            return _canonical(absolute)
        folder, leaf = os.path.split(absolute)
        real_folder = _realpath(folder)
        return _canonical(os.path.join(real_folder, leaf) if leaf else real_folder)
    return _canonical(_realpath(absolute))


def _is_share(canonical: str) -> bool:
    """Return True for a canonical Windows path on a share (``\\\\host\\share``)."""
    return os.name == "nt" and canonical.startswith("\\\\")


def _local_twins(
    spellings: tuple[str, ...], roots: tuple[tuple[tuple[str, ...], str], ...]
) -> list[str]:
    """Return the local paths that the share paths among *spellings* name.

    A share of this machine reached by a host name the string rules do not
    know (one of the machine's own addresses, a link-local IPv6 literal, a
    full domain name), through a share that is not an admin share, or through
    a mapped drive (whose resolved spelling is the share) names a local folder
    all the same. Each folder of a share path that exists, from the path up to
    the share, is compared by device and file number with each protected
    folder and every folder above one; at the first match the rest of the path
    is joined to that local folder.

    Only a path that the string checks did not place pays for this, and it
    asks the share's host: each share folder is read at most once in a check,
    and an error that says the host or the share cannot be reached ends the
    walk for that share, which then matches nothing.
    """
    shares = [spelling for spelling in dict.fromkeys(spellings) if _is_share(spelling)]
    seen: dict[str, tuple[int, int] | None] = {}
    local: dict[tuple[int, int], str] = {}
    unreachable: set[str] = set()
    twins: list[str] = []
    for share in shares:
        if ntpath.splitdrive(share)[0] in unreachable:
            continue
        if not local:
            local = _local_identities(roots)
        try:
            twin = _local_twin(share, local, seen)
        except _UnreachableShareError:
            unreachable.add(ntpath.splitdrive(share)[0])
            continue
        if twin is not None:
            twins.append(twin)
    return twins


def _local_twin(
    share_path: str,
    local: dict[tuple[int, int], str],
    seen: dict[str, tuple[int, int] | None],
) -> str | None:
    """Return the local folder of *local* that *share_path* is in, or None.

    *local* maps a device and file number to a local folder; *seen* holds the
    share folders already read in this check.
    """
    current, rest = share_path, list[str]()
    while True:
        wanted = _share_identity(current, seen)
        if wanted is not None and wanted in local:
            return _canonical(ntpath.join(local[wanted], *reversed(rest)))
        parent, leaf = ntpath.split(current)
        if not leaf or parent == current:
            return None
        rest.append(leaf)
        current = parent


def _local_identities(
    roots: tuple[tuple[tuple[str, ...], str], ...],
) -> dict[tuple[int, int], str]:
    """Return the protected folders and the folders above them, by identity."""
    found: dict[tuple[int, int], str] = {}
    for folder in _folders_above(roots):
        identity = _identity(folder)
        if identity is not None:
            found.setdefault(identity, folder)
    return found


def _share_identity(
    path: str, seen: dict[str, tuple[int, int] | None]
) -> tuple[int, int] | None:
    """Return the device and file number of the share path *path*, read once.

    Raises :class:`_UnreachableShareError` when the error says the host or the
    share cannot be reached.
    """
    if path in seen:
        return seen[path]
    try:
        info = os.stat(path)  # noqa: PTH116 - the guard works on str paths
    except OSError as error:
        if _unreachable(error):
            raise _UnreachableShareError(path) from None
        info = None
    except ValueError:
        info = None
    found = (info.st_dev, info.st_ino) if info is not None and info.st_ino else None
    seen[path] = found
    return found


def _unreachable(error: OSError) -> bool:
    """Return True when *error* says a share's host or the share is unreachable."""
    return getattr(error, "winerror", None) in _UNREACHABLE_ERRORS


def _identity(path: str) -> tuple[int, int] | None:
    """Return the device and file number of *path*, or None when unknown."""
    try:
        info = os.stat(path)  # noqa: PTH116 - the guard works on str paths
    except (OSError, ValueError):
        return None
    return (info.st_dev, info.st_ino) if info.st_ino else None


def _folders_above(
    roots: tuple[tuple[tuple[str, ...], str], ...],
) -> dict[str, None]:
    """Return every spelling of every protected folder and each folder above it."""
    folders: dict[str, None] = {}
    for keys, _shown in roots:
        for key in keys:
            folder = key
            while folder not in folders:
                folders[folder] = None
                parent = ntpath.dirname(folder)
                if parent == folder:
                    break
                folder = parent
    return folders


def _realpath(path: str) -> str:
    """Return ``os.path.realpath`` of *path*, or *path* when it cannot."""
    try:
        return os.path.realpath(path)
    except (OSError, ValueError, RuntimeError):
        return path


def _canonical(path: str) -> str:
    """Return *path* in the one spelling every comparison uses.

    That is ``os.path.normcase`` of it, on Windows also
    :func:`_windows_spelling`, and on macOS :func:`_data_volume_spelling`.
    """
    path = os.path.normcase(path)
    if os.name == "nt":
        path = _windows_spelling(path)
    elif _DATA_VOLUME_FIRMLINK:
        path = _data_volume_spelling(path)
    return path


def _data_volume_spelling(path: str) -> str:
    """Return a macOS *path* on the data volume as the path it is firmlinked to.

    ``/System/Volumes/Data/Users/me`` reads as ``/Users/me``, and the volume
    itself as ``/``. Letter case in the prefix counts only when
    :data:`_FOLD_CASE` says so. It is string work on *path* alone.
    """
    head, rest = path[: len(_DATA_VOLUME)], path[len(_DATA_VOLUME) :]
    if rest and not rest.startswith("/"):
        return path
    if head == _DATA_VOLUME or (
        _FOLD_CASE and head.casefold() == _DATA_VOLUME.casefold()
    ):
        return rest or "/"
    return path


def _windows_spelling(path: str) -> str:
    """Return a Windows *path* as the plain drive-letter path it names.

    - ``\\\\?\\C:\\x`` and ``\\\\.\\C:\\x`` read as ``C:\\x``;
      ``\\\\?\\UNC\\host\\share`` and ``\\\\.\\UNC\\host\\share`` as
      ``\\\\host\\share``. ``\\??\\`` (the NT object namespace) reads the same.
    - A loopback admin share reads as its drive: ``\\\\localhost\\C$\\x``,
      ``\\\\127.0.0.1\\C$\\x``, ``\\\\--1.ipv6-literal.net\\C$\\x`` and
      ``\\\\<this machine>\\C$\\x`` as ``C:\\x``.
    - A component ``name:stream`` or ``name::$TYPE`` (an alternate data
      stream) reads as ``name``.

    It is string work on *path* alone, so it runs the same on every system:
    nothing touches the disk, and no host name is looked up on the network.
    """
    path = path.replace("/", "\\")
    lowered = path.lower()
    for prefix, replacement in _PREFIXES:
        if lowered.startswith(prefix):
            path = replacement + path[len(prefix) :]
            break
    if path.startswith("\\\\"):
        host, _sep, rest = path[2:].partition("\\")
        share, _sep, tail = rest.partition("\\")
        if _ADMIN_SHARE.fullmatch(share) and _is_loopback(host):
            path = f"{share[0]}:\\{tail}"
    drive, tail = ntpath.splitdrive(path)
    return drive + "\\".join(part.split(":", 1)[0] for part in tail.split("\\"))


def _is_loopback(host: str) -> bool:
    """Return True for a UNC host name that is this machine."""
    name = host.lower()
    return (
        name == "localhost"
        or _LOOPBACK_V4.fullmatch(name) is not None
        or _is_ipv6_loopback(name)
        or name in _machine_names()
    )


def _is_ipv6_loopback(name: str) -> bool:
    """Return True for the ``ipv6-literal.net`` name of the IPv6 loopback.

    A UNC host cannot hold ``:``, so Windows writes an IPv6 address there with
    ``-`` for ``:``, ``s`` before a zone, and ``.ipv6-literal.net`` after it:
    ``--1.ipv6-literal.net`` and ``0--1.ipv6-literal.net`` are ``::1``.
    """
    if not name.endswith(_IPV6_LITERAL):
        return False
    text = name[: -len(_IPV6_LITERAL)].replace("-", ":").partition("s")[0]
    try:
        address = ipaddress.IPv6Address(text)
    except ValueError:
        return False
    mapped = address.ipv4_mapped
    return address.is_loopback or (mapped is not None and mapped.is_loopback)


def _machine_names() -> frozenset[str]:
    """Return this machine's own names, lower case, from the system alone.

    ``socket.gethostname()`` and ``platform.node()``, each with its first label
    as well; there is no DNS lookup. Asked for only when a UNC path is checked.
    """
    names: set[str] = set()
    for module_name, function in (("socket", "gethostname"), ("platform", "node")):
        try:
            value: object = getattr(importlib.import_module(module_name), function)()
        except _LOOKUP_ERRORS:
            continue
        if isinstance(value, str) and value:
            lowered = value.lower()
            names.update((lowered, lowered.split(".", 1)[0]))
    names.discard("")
    return frozenset(names)


def _roots(
    home: str | None, extra: tuple[str, ...]
) -> tuple[tuple[tuple[str, ...], str], ...]:
    """Return ``(spellings, shown)`` for every protected folder, as they are now.

    The resolved spellings are reused while :func:`_layout` finds each home
    and its ``.config`` as they were, and built afresh otherwise.
    """
    homes = (*([home] if home else []), *extra)
    layout, settled = _layout(homes)
    if settled:
        return _resolved_roots(homes, layout)
    return _resolved_roots.__wrapped__(homes, layout)


def _layout(homes: tuple[str, ...]) -> tuple[tuple[object, ...], bool]:
    """Return what each home and its ``.config`` are now, and whether it settled.

    A protected folder sits in a home or in its ``.config``. Swapping one of
    them, or ``.config``, for a link (or back) changes the folder that holds
    it: its timestamp, or, for a home swapped itself, its identity. A change
    within the same tick of the file system clock can leave the timestamp as
    it was, so a folder changed less than :data:`_SETTLE_NS` ago has not
    settled, and nothing resolved under it is reused.

    A home or a ``.config`` that is itself a link (a dotfiles folder, say)
    records the link, so the folder it leads to is read as well: a protected
    folder swapped inside it, or the link pointed elsewhere, changes that
    folder's timestamp or identity. Links above a home are not looked at.
    """
    now = time.time_ns()
    found: list[object] = []
    settled = True
    for home in homes:
        for folder in (home, os.path.join(home, ".config")):
            link = _read(os.lstat, folder)
            infos = [link]
            if link is not None and _is_link(link):
                infos.append(_read(os.stat, folder))
            for info in infos:
                if info is None:
                    found.append(None)
                    continue
                found.append((info.st_dev, info.st_ino, info.st_mode, info.st_mtime_ns))
                settled = settled and now - info.st_mtime_ns >= _SETTLE_NS
    return tuple(found), settled


def _read(read: Callable[[str], os.stat_result], folder: str) -> os.stat_result | None:
    """Return ``read(folder)`` (``os.lstat`` or ``os.stat``), or None on error."""
    try:
        return read(folder)
    except (OSError, ValueError):
        return None


def _is_link(info: os.stat_result) -> bool:
    """Return True for the ``lstat`` of a link: a symlink, or a junction."""
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_reparse_tag", 0))


@functools.lru_cache(maxsize=8)
def _resolved_roots(
    homes: tuple[str, ...], layout: tuple[object, ...]
) -> tuple[tuple[tuple[str, ...], str], ...]:
    """Return ``(spellings, shown)`` for every protected folder of *homes*.

    Each folder is compared as written and as resolved through links, and the
    home is resolved as well, so a link inside the home (a ``.config`` that
    leads elsewhere) or a link to the home both count. *layout* only keys the
    cache (see :func:`_layout`).
    """
    del layout
    relative = dict.fromkeys((*APOTHEM_ROOTS, *_registry_roots()))
    found: list[tuple[tuple[str, ...], str]] = []
    for base in homes:
        real_base = _realpath(base)
        for name in relative:
            parts = name.split("/")
            shown = os.path.join(base, *parts)
            spellings = dict.fromkeys(
                (
                    _canonical(shown),
                    _canonical(os.path.join(real_base, *parts)),
                    _canonical(_realpath(shown)),
                )
            )
            found.append((tuple(spellings), shown))
    return tuple(found)


def _registry_roots() -> tuple[str, ...]:
    """Return the home folders and paths the registry and the manifest name.

    They are read once per process (:func:`_derived_roots`). When either
    cannot be loaded, :data:`FALLBACK_ROOTS` stands in, and the next check
    reads them again.
    """
    try:
        return _derived_roots()
    except _DERIVE_ERRORS:
        return FALLBACK_ROOTS


#: What reading the registry or the manifest may raise.
_DERIVE_ERRORS = (ImportError, AttributeError, OSError, ValueError, TypeError)


@functools.lru_cache(maxsize=1)
def _derived_roots() -> tuple[str, ...]:
    """Return the protected home folders and paths, read once from the sources.

    The folders come from the registry (:func:`derive_roots`), the paths
    outside them from the manifest (:func:`manifest_paths`). ``lru_cache``
    keeps no failure.
    """
    registry = importlib.import_module("apothem.lib.harness_registry_data")
    propagation = importlib.import_module("apothem.lib.propagation")
    entries = tuple(registry.HARNESS_REGISTRY)
    folders = derive_roots(
        [
            *(path for entry in entries for path in entry.target_paths),
            *(root.path for root in registry.SHARED_ROOTS),
        ]
    )
    paths = manifest_paths(propagation.load_manifest(), entries)
    return narrowest_roots(folders, paths)


def derive_roots(paths: list[str]) -> tuple[str, ...]:
    """Return the home folders that registry-style *paths* (``~/...``) name."""
    names: dict[str, None] = {}
    for path in paths:
        if not path.startswith("~/"):
            continue
        parts = [part for part in path[2:].split("/") if part]
        if not parts or "{" in parts[0] or " " in parts[0]:
            continue
        if parts[0] == ".config":
            if len(parts) > 1 and "{" not in parts[1]:
                names[f".config/{parts[1]}"] = None
            continue
        names[parts[0]] = None
    return tuple(sorted(names))


def manifest_paths(manifest: Mapping[str, Any], entries: Iterable[Any]) -> list[str]:
    """Return the home paths (``~/...``) the propagation *manifest* changes.

    *manifest* maps a harness's package key to its rules (``install`` entries
    with a ``target``, and ``stale_sweep``); *entries* are the registry's. A
    ``${USER_HOME}`` target is a home path. A ``${HARNESS_ROOT}`` target and a
    stale-sweep entry are joined to the harness root of a user-scope harness,
    the folder of its first registry target (``~/.gemini`` for Antigravity),
    so ``../.antigravity/profile.yaml`` names ``~/.antigravity/profile.yaml``.
    A project-scope harness's paths are in the project, and a path that
    leaves the home is not the home's: neither is returned. A path is cut
    before its first part that holds a pattern or a placeholder.
    """
    roots: dict[str, str] = {}
    for entry in entries:
        first = entry.target_paths[0] if entry.target_paths else ""
        if entry.scope == "user" and first.startswith("~/"):
            roots[entry.package_key] = posixpath.dirname(first[2:].rstrip("/"))
    found: dict[str, None] = {}
    for key, rules in manifest.items():
        root = roots.get(key)
        relative = [_relative_target(item.target, root) for item in rules.install]
        if root is not None:
            relative += [posixpath.join(root, item) for item in rules.stale_sweep]
        for path in relative:
            inside = _inside_home(path)
            if inside is not None:
                found[f"~/{inside}"] = None
    return list(found)


def _relative_target(target: str, root: str | None) -> str | None:
    """Return a manifest *target* relative to the home, or None outside it."""
    for token, base in (("${USER_HOME}/", ""), ("${HARNESS_ROOT}/", root)):
        if target.startswith(token) and base is not None:
            return posixpath.join(base, target[len(token) :])
    return None


def _inside_home(path: str | None) -> str | None:
    """Return *path* (relative to the home) normalized, or None outside it."""
    if path is None:
        return None
    kept: list[str] = []
    for part in posixpath.normpath(path).split("/"):
        if any(mark in part for mark in "*?[{$"):
            break
        kept.append(part)
    text = "/".join(kept)
    if not text or text in {".", ".."} or text.startswith(("../", "/")):
        return None
    return text


def narrowest_roots(folders: tuple[str, ...], paths: list[str]) -> tuple[str, ...]:
    """Return *folders* and each of *paths* (``~/...``) outside every folder.

    A path inside one of *folders* or :data:`APOTHEM_ROOTS` is protected
    already. Any other is protected by itself, not by the folder that holds
    it, which may hold the tool's own files.
    """
    covered = (*APOTHEM_ROOTS, *folders)
    names = dict.fromkeys(folders)
    for path in paths:
        relative = path[2:] if path.startswith("~/") else path
        if not any(
            relative == folder or relative.startswith(f"{folder}/")
            for folder in covered
        ):
            names[relative] = None
    return tuple(sorted(names))


@functools.lru_cache(maxsize=1)
def _os_account_home() -> str:
    """Return the account's home from the operating system, looked up once.

    Raises :class:`_HomeLookupError` when every lookup fails; ``lru_cache`` keeps
    no failure, so the next call tries again. An error from one lookup (a
    broken system library, say) moves on to the next lookup, so a broken step
    never stops the check itself. The lookups call the system functions bound
    at import (:data:`_SYSTEM`; a missing one is a ``KeyError``), so a test's
    later fake cannot reach them.
    """
    lookups = (
        (_windows_profile, _volatile_profile)
        if os.name == "nt"
        else (_passwd_home_effective, _passwd_home_real)
    )
    for lookup in lookups:
        try:
            found: object = lookup()
        except _LOOKUP_ERRORS:
            found = None
        if _usable_home(found):
            return os.path.abspath(found)
    raise _HomeLookupError("the system has no record of this account's home")


def _usable_home(found: object) -> TypeGuard[str]:
    """Return True for a non-empty absolute path that is not a filesystem root."""
    if not isinstance(found, str) or not found or not os.path.isabs(found):
        return False
    absolute = os.path.abspath(found)
    return os.path.dirname(absolute) != absolute


def _windows_profile() -> str:
    """Return ``FOLDERID_Profile`` from ``SHGetKnownFolderPath``."""
    dll_type = _SYSTEM["ctypes.WinDLL"]
    structure = _SYSTEM["ctypes.Structure"]
    c_uint32 = _SYSTEM["ctypes.c_uint32"]
    c_uint16 = _SYSTEM["ctypes.c_uint16"]
    c_ubyte = _SYSTEM["ctypes.c_ubyte"]
    byref = _SYSTEM["ctypes.byref"]
    shell32 = dll_type("shell32")
    ole32 = dll_type("ole32")

    class _Guid(structure):  # type: ignore[misc,valid-type]
        _fields_ = (
            ("data1", c_uint32),
            ("data2", c_uint16),
            ("data3", c_uint16),
            ("data4", c_ubyte * 8),
        )

    folder = _SYSTEM["uuid.UUID"](_FOLDERID_PROFILE)
    guid = _Guid(
        folder.time_low,
        folder.time_mid,
        folder.time_hi_version,
        (c_ubyte * 8)(*folder.bytes[8:]),
    )
    pointer = _SYSTEM["ctypes.c_wchar_p"]()
    get_path = shell32.SHGetKnownFolderPath
    get_path.restype = _SYSTEM["ctypes.c_long"]
    free = ole32.CoTaskMemFree
    free.restype = None
    try:
        status = get_path(byref(guid), 0, None, byref(pointer))
        if status != 0:
            raise OSError(f"SHGetKnownFolderPath failed: {status & 0xFFFFFFFF:#x}")
        return str(pointer.value or "")
    finally:
        free(pointer)


def _volatile_profile() -> str:
    """Return ``USERPROFILE`` from the logon session's registry key."""
    open_key = _SYSTEM["winreg.OpenKey"]
    current_user = _SYSTEM["winreg.HKEY_CURRENT_USER"]
    with open_key(current_user, "Volatile Environment") as key:
        value, _kind = _SYSTEM["winreg.QueryValueEx"](key, "USERPROFILE")
    return str(value)


def _passwd_home_effective() -> str:
    """Return the ``passwd`` home of the process's effective user."""
    return str(_SYSTEM["pwd.getpwuid"](_SYSTEM["os.geteuid"]()).pw_dir)


def _passwd_home_real() -> str:
    """Return the ``passwd`` home of the process's real user."""
    return str(_SYSTEM["pwd.getpwuid"](_SYSTEM["os.getuid"]()).pw_dir)
