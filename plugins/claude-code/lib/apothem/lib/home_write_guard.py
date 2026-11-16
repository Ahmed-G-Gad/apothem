# SPDX-License-Identifier: MIT

"""Refuse writes into the account's real home while a pytest test runs.

The repository's ``tests/conftest.py`` points every test at temporary folders,
but a test run that does not load it (a test file copied out of ``tests/`` and
run with ``-c``, ``-o addopts=`` or ``--rootdir`` elsewhere) runs Apothem
against the account's real home. This module stops such a write before it
happens.

While ``PYTEST_CURRENT_TEST`` is set (pytest sets it for each test's setup, call
and teardown), :func:`refuse_real_home_write` raises :class:`RealHomeWriteError`
for a path at or inside one of these folders of the account's home:

- ``.apothem`` (install records, locks, backup sets, a user-scope data home);
- ``.config/apothem``;
- the tools' own folders that the harness registry's ``~/`` targets and shared
  roots name (``.claude``, ``.codex``, ``.agents``, ``.config/opencode`` and the
  rest; :data:`FALLBACK_ROOTS` lists them).

With ``tree=True`` (removing or moving a whole folder) a path that holds one of
those folders is refused too. Nothing else is refused: reads, dry runs and
previews, the temporary folder, the checkout, and the rest of the home all stay
allowed. With ``PYTEST_CURRENT_TEST`` unset the check is one environment lookup.

The account home comes from the operating system (``FOLDERID_Profile`` on
Windows, the ``passwd`` entry elsewhere), never from ``HOME`` or ``USERPROFILE``:
under ``tests/conftest.py`` those name a temporary folder. When the system has
no answer, only the homes a test added with :func:`also_protect_home` are
protected, and the failed lookup is tried again on the next check. No
environment variable, setting or flag turns the refusal off; a test that runs a
real install on purpose starts Apothem without ``PYTEST_CURRENT_TEST`` in the
child's environment.

Every refusal is logged in this process (:func:`refusals`,
:func:`drain_refusals`) and written once per protected folder to ``stderr``, so
a caller that absorbs the error still leaves a trace that ``tests/conftest.py``
reports.

Nothing here holds a path at module level, and nothing is looked up at import:
the suite's scan for module-level paths naming the real home stays clean.
"""

from __future__ import annotations

import contextlib
import functools
import importlib
import os
import stat
import sys
from typing import Any, TypeGuard

#: The variable pytest sets for each test's setup, call and teardown.
PYTEST_VARIABLE = "PYTEST_CURRENT_TEST"

#: Apothem's own folders in the home, relative to it.
APOTHEM_ROOTS: tuple[str, ...] = (".apothem", ".config/apothem")

#: The tools' folders in the home the harness registry names, used when the
#: registry cannot be imported. A unit test pins it equal to the derived set.
FALLBACK_ROOTS: tuple[str, ...] = (
    ".agents",
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

#: Homes a test added with :func:`also_protect_home` (temporary folders only).
_extra_homes: list[str] = []
#: The refusal log, a list of exceptions.
_refusals: list[RealHomeWriteError] = []
#: The first refusal written to ``stderr`` for each protected folder.
_announced: list[RealHomeWriteError] = []


class RealHomeWriteError(OSError):
    """A write into the account's real home, refused while a pytest test runs.

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


def active() -> bool:
    """Return True while a pytest test runs (``PYTEST_CURRENT_TEST`` is set)."""
    return PYTEST_VARIABLE in os.environ


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
    _extra_homes.append(os.path.abspath(os.fspath(path)))
    _roots.cache_clear()


def clear_extra_homes() -> None:
    """Forget every home added with :func:`also_protect_home`."""
    _extra_homes.clear()
    _roots.cache_clear()


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

    A path may not change while a pytest test runs when it is at or inside a
    protected folder (see the module docstring); with *tree* also when a
    protected folder is at or below it. *operation* is a verb phrase for the
    message (``write``, ``create the lock file``, ``remove``).
    """
    for path in paths:
        text = os.fspath(path)
        root = _protected_root_of(text, tree=tree)
        if root is not None:
            _refuse(text, root, operation)


def _refuse(path: str, root: str, operation: str) -> None:
    """Log, report once per protected folder, and raise the refusal."""
    test = os.environ.get(PYTEST_VARIABLE, "")
    message = (
        f"Apothem refused to {operation} {path}: it is inside or holds {root}, a "
        "folder in this account's real home, while a pytest test is running "
        f"({test}). Nothing was changed. Fix: run the test from the repository's "
        "tests/ folder so tests/conftest.py loads; or, before the test writes, "
        "point HOME and USERPROFILE at a temporary folder and set "
        "apothem.lib.install_ledger.STATE_ROOT and "
        "apothem.harnesses._shared.install_driver.BACKUP_ROOT to temporary "
        "folders. To run a real install on purpose, start Apothem without "
        f"{PYTEST_VARIABLE} in its environment."
    )
    error = RealHomeWriteError(
        message, path=path, protected_root=root, operation=operation
    )
    if len(_refusals) < _LOG_LIMIT:
        _refusals.append(error)
    if not any(seen.protected_root == root for seen in _announced):
        _announced.append(error)
        with contextlib.suppress(OSError, ValueError, AttributeError):
            sys.stderr.write(f"{type(error).__name__}: {message}\n")
    raise error


def _protected_root_of(path: str, *, tree: bool) -> str | None:
    """Return the protected folder *path* is in (or, with *tree*, holds)."""
    if PYTEST_VARIABLE not in os.environ:
        return None
    roots = _roots(account_home(), tuple(_extra_homes))
    if not roots:
        return None
    absolute = os.path.abspath(path)
    lexical = _canonical(absolute)
    found = _match(lexical, roots, tree=tree)
    if found is not None:
        return found
    return _match(_real_target(absolute), roots, tree=tree)


def _match(
    target: str, roots: tuple[tuple[tuple[str, ...], str], ...], *, tree: bool
) -> str | None:
    """Return the shown root whose spelling holds *target* (or *target* holds)."""
    for keys, shown in roots:
        for key in keys:
            if target == key or target.startswith(key + os.sep):
                return shown
            if tree and key.startswith(target.rstrip(os.sep) + os.sep):
                return shown
    return None


def _real_target(absolute: str) -> str:
    """Return *absolute* with its folder resolved through links, case-folded.

    A leaf that is itself a link (or a Windows reparse point) is resolved too.
    """
    try:
        info = os.lstat(absolute)
    except (OSError, ValueError):
        is_link = False
    else:
        attributes = getattr(info, "st_file_attributes", 0)
        is_link = stat.S_ISLNK(info.st_mode) or bool(
            attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT
        )
    if is_link:
        return _canonical(_realpath(absolute))
    folder, leaf = os.path.split(absolute)
    real_folder = _real_dir(folder, os.environ.get(PYTEST_VARIABLE, ""))
    return os.path.normcase(os.path.join(real_folder, leaf)) if leaf else real_folder


@functools.lru_cache(maxsize=4096)
def _real_dir(absolute_dir: str, epoch: str) -> str:
    """Return the canonical spelling of a folder, cached per test phase.

    *epoch* is the current ``PYTEST_CURRENT_TEST`` value, so entries age out
    as pytest moves from one test phase to the next.
    """
    del epoch
    return _canonical(_realpath(absolute_dir))


def _realpath(path: str) -> str:
    """Return ``os.path.realpath`` of *path*, or *path* when it cannot."""
    try:
        return os.path.realpath(path)
    except (OSError, ValueError, RuntimeError):
        return path


def _canonical(path: str) -> str:
    """Return *path* without a ``\\\\?\\`` prefix, case-folded as the system does."""
    if path.startswith("\\\\?\\UNC\\"):
        path = "\\\\" + path[len("\\\\?\\UNC\\") :]
    elif path.startswith("\\\\?\\"):
        path = path[len("\\\\?\\") :]
    return os.path.normcase(path)


@functools.lru_cache(maxsize=8)
def _roots(
    home: str | None, extra: tuple[str, ...]
) -> tuple[tuple[tuple[str, ...], str], ...]:
    """Return ``(spellings, shown)`` for every protected folder.

    Each folder is compared as written and as resolved through links, and the
    home is resolved as well, so a link inside the home (a ``.config`` that
    leads elsewhere) or a link to the home both count.
    """
    homes = [*([home] if home else []), *extra]
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
    """Return the home folders the harness registry's ``~/`` paths name.

    ``~/.claude/CLAUDE.md`` names ``.claude``; a path under ``~/.config`` names
    the tool's own folder there (``.config/opencode``), not all of ``.config``.
    """
    try:
        registry = importlib.import_module("apothem.lib.harness_registry_data")
        paths = [
            *(
                path
                for entry in registry.HARNESS_REGISTRY
                for path in entry.target_paths
            ),
            *(root.path for root in registry.SHARED_ROOTS),
        ]
    except (ImportError, AttributeError):
        return FALLBACK_ROOTS
    return derive_roots(paths)


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


@functools.lru_cache(maxsize=1)
def _os_account_home() -> str:
    """Return the account's home from the operating system, looked up once.

    Raises :class:`_HomeLookupError` when every lookup fails; ``lru_cache`` keeps
    no failure, so the next call tries again. Any exception from one lookup (a
    test that replaced part of ``ctypes`` with a fake, say) moves on to the
    next lookup, so a broken step never stops the check itself.
    """
    lookups = (
        (_windows_profile, _volatile_profile)
        if os.name == "nt"
        else (_passwd_home_effective, _passwd_home_real)
    )
    for lookup in lookups:
        try:
            found: object = lookup()
        except Exception:  # any failure falls through to the next lookup
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
    ctypes: Any = importlib.import_module("ctypes")
    uuid: Any = importlib.import_module("uuid")
    # Private library objects of the class ``windll`` was built with when
    # ``ctypes`` was imported: a test may replace ``ctypes.WinDLL``, and the
    # shared ``windll`` functions may be retyped.
    dll_type = ctypes.windll._dlltype
    shell32 = dll_type("shell32")
    ole32 = dll_type("ole32")

    class _Guid(ctypes.Structure):  # type: ignore[misc]
        _fields_ = (
            ("data1", ctypes.c_uint32),
            ("data2", ctypes.c_uint16),
            ("data3", ctypes.c_uint16),
            ("data4", ctypes.c_ubyte * 8),
        )

    folder = uuid.UUID(_FOLDERID_PROFILE)
    guid = _Guid(
        folder.time_low,
        folder.time_mid,
        folder.time_hi_version,
        (ctypes.c_ubyte * 8)(*folder.bytes[8:]),
    )
    pointer = ctypes.c_wchar_p()
    get_path = shell32.SHGetKnownFolderPath
    get_path.restype = ctypes.c_long
    free = ole32.CoTaskMemFree
    free.restype = None
    try:
        status = get_path(ctypes.byref(guid), 0, None, ctypes.byref(pointer))
        if status != 0:
            raise OSError(f"SHGetKnownFolderPath failed: {status & 0xFFFFFFFF:#x}")
        return str(pointer.value or "")
    finally:
        free(pointer)


def _volatile_profile() -> str:
    """Return ``USERPROFILE`` from the logon session's registry key."""
    winreg: Any = importlib.import_module("winreg")
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Volatile Environment") as key:
        value, _kind = winreg.QueryValueEx(key, "USERPROFILE")
    return str(value)


def _passwd_home_effective() -> str:
    """Return the ``passwd`` home of the process's effective user."""
    pwd: Any = importlib.import_module("pwd")
    system: Any = os  # ``geteuid`` exists only on POSIX
    return str(pwd.getpwuid(system.geteuid()).pw_dir)


def _passwd_home_real() -> str:
    """Return the ``passwd`` home of the process's real user."""
    pwd: Any = importlib.import_module("pwd")
    system: Any = os  # ``getuid`` exists only on POSIX
    return str(pwd.getpwuid(system.getuid()).pw_dir)
