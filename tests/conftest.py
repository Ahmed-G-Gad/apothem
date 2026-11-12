# SPDX-License-Identifier: MIT

"""Suite-wide pytest configuration: source bootstrap + state and HOME isolation.

The ``sys.path`` inserts make ``apothem`` importable from a plain checkout
(no editable install) for every test subtree — unit, integration, property,
packaging, hooks, conformity, scripts — instead of only the two subtrees
that used to carry their own copy of the insert, and make the repo root
importable so the cross-subtree test helpers under ``tests/_shared/``
resolve as ``tests._shared`` namespace-package imports regardless of how
pytest is invoked. The autouse ledger isolation applies suite-wide for the
same reason: any subtree's test may exercise an install path, and none may
write a real ledger under the developer's home.

The user home is isolated too. Some manifest targets sit in the user home
whatever the install root is (``${USER_HOME}/.agents/skills/``), so an install
into a temporary root still writes there. ``HOME`` and ``USERPROFILE`` are
redirected for the whole session and again for every test; ``Path.home()`` then
resolves under the temporary root. The session-wide redirect covers every fixture
of a narrower scope (module, class, package), because pytest sets up
higher-scoped fixtures first. It does not cover a session-scoped fixture that
pytest sets up before it: pytest sets up session-scoped autouse fixtures in the
order they were registered (a plugin's first, then a conftest's by name), not by
intent, so a session-scoped fixture that runs an install has to request
``_isolate_session_home`` as a parameter. ``apothem.lib.propagation.USER_HOME``
stays unset on purpose: ``Path.home`` is the one seam, so a test that patches it
keeps working.

Two install state roots are bound from ``Path.home()`` when their modules are
imported, which is while this file loads and before any fixture runs, so
redirecting ``HOME`` does not move them: ``install_ledger.STATE_ROOT``
(``~/.apothem/state``, which holds the ledgers and the install lock files) and
``install_driver.BACKUP_ROOT`` (``~/.apothem/backups``; the binding in
``install_driver_types`` that it re-exports moves with it). They are re-pointed
explicitly, twice. ``_isolate_session_home`` moves them into the session home for
the whole session, which covers module-scoped fixtures: those are built before
any function-scoped autouse fixture, and one that runs an install would
otherwise write its lock files, ledger lines and backups under the developer's
real ``~/.apothem``. ``_isolate_install_ledger`` and ``_isolate_backup_root``
then give each test its own. The one other home-derived module constant,
``apothem.conformity.gate._DEFAULT_CLAUDE_SCOPE``, only names a scope the gate
compares paths against; nothing writes through it.

Three environment variables decide where a write or a read lands whatever
``HOME`` says, and they are set twice in the same way. ``CODEX_HOME`` moves the
Codex root, so a developer's own setting would send a Codex install into their
real Codex home; it is cleared. ``CLAUDE_CONFIG_DIR`` moves the Claude Code
folder the session-start hook reads the memory index from; it is cleared too.
``APOTHEM_HOOK_STATE_DIR`` overrides the folder where the
session-end gate and the compaction tracker keep their per-session counters.
Without it that folder comes from ``CLAUDE_PLUGIN_DATA``, ``XDG_STATE_HOME`` or,
on Windows, ``LOCALAPPDATA``, none of which follows a redirected ``HOME``, so it
names a temporary folder. ``_isolate_session_home`` does all three for the whole
session; ``_isolate_user_home`` and ``_isolate_hook_state`` do them again for
each test. ``LOCALAPPDATA`` stays as it is: every Windows tool a test launches
reads it, and Apothem reads it only for that hook state folder. Every home
redirect also clears the four XDG base directories (``XDG_CONFIG_HOME``,
``XDG_STATE_HOME``, ``XDG_DATA_HOME``, ``XDG_CACHE_HOME``), so code and child
processes that read them fall back to the temporary home.

``tests/unit/test_suite_state_isolation.py`` pins the session-level redirect and
fails on any module-level path that still names the real home, so a root added
later fails the suite until it is redirected here or listed there as read-only.
Writes made before any fixture runs (collection-time code, a plugin's
session-scoped fixture) are outside both redirects; the check for those is to run
pytest with ``HOME`` and ``USERPROFILE`` pointing at an empty folder and confirm
nothing appears in it afterwards. The ``home-isolation`` job in
``.github/workflows/ci.yml`` does that for the whole suite, with the XDG base
directories on empty folders too.

The isolation fixtures above are all named with a leading underscore, and a
``from <this module> import *`` skips such names unless the module lists them in
``__all__``. A probe folder whose conftest star-imported this file before it had
an ``__all__`` got none of them, and its tests ran Apothem against the
developer's real home: that once deleted a real install ledger and overwrote a
file under ``~/.config/apothem``. Two things now stop that.

``__all__`` lists the five isolation fixtures, the guard's names and every
other public name, so a star import of this file carries the isolation with it.

``real_home_guard``, an instance of ``RealHomeGuard``, is a plugin object.
Importing this file inside a pytest session registers it with that session,
whatever the import binds: pytest loading this file as a conftest, ``-p
tests.conftest``, a star import, or a conftest that imports single names (some
isolation fixtures, say, and no guard name). The import finds the session's
plugin manager on the call stack, which depends on pytest importing a conftest
or a ``-p`` plugin from a method of its plugin manager; the self-tests fail if
a pytest release changes that. When the file was imported before the session
started, ``pytest_register_real_home_guard``, a ``pytest_configure`` hook a star
import carries, registers it instead; ``pytest_configure`` is historic, so pytest
calls it for a conftest it loads late too. It is registered once per session,
under ``apothem-real-home-guard``, and pytest calls its hooks on the object, so
deleting or rebinding a name in a conftest does not remove them. Its hooks:

- ``pytest_runtest_setup``, first (``tryfirst``) and not a wrapper, before
  pytest sets up any fixture of the test. It fails the test when one of
  ``_isolate_session_home``, ``_isolate_user_home``, ``_isolate_install_ledger``
  or ``_isolate_backup_root`` is not among its fixtures, whichever import brought
  the others in; when ``_isolate_session_home`` is a fixture of the same name
  defined elsewhere, or a direct parametrization of that name; and when a
  session-scoped fixture would be set up before ``_isolate_session_home``
  without requesting it. pytest sets up session-scoped autouse fixtures in the
  order they were registered, a ``-p`` plugin's and a parent conftest's first and
  then a conftest's own by name, so ``_install_x`` comes before it. The test's
  own fixtures would otherwise write while they are set up, before any check of
  the environment could run, and under ``--setup-only`` no test call runs at all.
  Fixtures of a plugin installed as a package (loaded through its entry point)
  are not checked for their order: they are the developer's tools, and every
  test would fail.
- ``pytest_pyfunc_call`` and ``pytest_runtest_call``, plain hooks, neither
  ``tryfirst`` nor ``trylast``. pytest starts every wrapper of a hook before it
  calls a plain implementation, and calls the most recently registered plain
  implementation first. A test function is checked in ``pytest_pyfunc_call``,
  which ``Function.runtest`` calls after every ``pytest_runtest_call``
  implementation has run: after every wrapper of either hook has started, after
  the plain hooks of a conftest that imported this file (pytest registers that
  conftest after the import), and right before pytest's own ``trylast``
  implementation calls the function. Any other item (a ``unittest`` case, a
  doctest) is checked in ``pytest_runtest_call``, right before pytest's own
  implementation runs it. The check sees the environment the body will see and
  fails the test before the body starts.
- ``pytest_runtest_makereport``, a wrapper around every other: a test the guard
  stopped stays failed when it is marked ``xfail``, which would otherwise turn the
  failure into XFAIL and let the run pass.

The guard fails a test with ``RealHomeGuardFailure``, ``pytest.fail``'s exception
under a type of its own, so the report hook can tell it apart. ``-p
no:apothem-real-home-guard`` turns the guard off. They are hooks, not autouse
fixtures: a fixture runs at a point in the setup that depends on its scope, its
name and the order the conftests were registered.

The guard captures the real home once, when this file is imported and
before any fixture runs: ``HOME``, ``USERPROFILE``, ``HOMEDRIVE`` with
``HOMEPATH``, ``~`` and, on POSIX, the account's home from ``pwd``. When a job
points ``HOME`` at a temporary folder for the whole run, that folder is the real
home. It also captures the real folders Apothem writes or reads in a home: the
``.apothem``, ``.config/apothem`` and ``.local/state/apothem`` folders, the
``.codex``, ``.claude`` and ``.config`` folders, the folders that ``CODEX_HOME``,
``CLAUDE_CONFIG_DIR`` and ``XDG_CONFIG_HOME`` named at import, and the
``apothem`` folders in ``XDG_STATE_HOME`` and ``LOCALAPPDATA``. Before each test
body it fails the test when ``HOME``, ``USERPROFILE``, ``Path.home()``,
``propagation.user_home()``, the data home, the ``~/.config/apothem`` folder, the
install ledger root, the backup root, ``CODEX_HOME``, ``CLAUDE_CONFIG_DIR``,
``XDG_CONFIG_HOME``, the hook state folder or, when it decides that folder,
``CLAUDE_PLUGIN_DATA`` or ``XDG_STATE_HOME``, as Apothem computes them at that
moment, resolves to a real home, or to one of those folders or into it. A folder
that only sits somewhere below a real home stays allowed: the Windows temporary
folder is under ``C:\\Users\\<name>``, and every test's temporary home is in it.
``LOCALAPPDATA`` itself is not compared, for the same reason: the temporary folder
is inside it, and every test inherits it. It counts when Apothem would use it,
which is when the hook state folder falls back to it. The guard uses ``os.path``
rather than ``Path.resolve()``, which on Python 3.10 to 3.12 calls
``Path.stat``, a method some tests patch.

What the guard cannot see or stop:

- Writes outside a test's setup and call: while a conftest is imported, during
  collection, from a conftest's own ``tryfirst`` setup hook registered after the
  guard (pytest calls that one first) or plain setup hook (it runs after the
  check and before the fixtures), in a session-scoped fixture of a plugin
  installed as a package, and in a fixture's teardown after it undoes the
  isolation.
- What a test body changes after it starts, including a fixture it requests with
  ``request.getfixturevalue``, and the environment it builds for a child process;
  and a conftest's own plain ``pytest_pyfunc_call`` that runs the test itself.
- A fixture a conftest defines under ``_isolate_user_home``,
  ``_isolate_install_ledger`` or ``_isolate_backup_root`` (one suite test
  replaces ``_isolate_backup_root`` on purpose): the setup hook sees the name and
  passes, and the call hook checks only what that fixture left.
- A session run with ``--noconftest``, which loads no conftest, so neither the
  isolation nor the guard; one that passes ``-p no:apothem-real-home-guard`` or
  unregisters the guard; and a conftest that imports single names from this file
  after any earlier import in the same process, inside an earlier pytest session
  (a script that calls ``pytest.main`` twice) or outside any: the module is
  cached, so the import registers nothing and binds no registrar.
- Roots it does not compare: the harness folders in a home other than
  ``.codex``, ``.claude`` and ``.config`` (such as ``.cursor``, ``.gemini`` or
  ``.agents``), whether a test names one as its own install root while ``HOME``
  is isolated or ``CODEX_HOME`` or ``XDG_CONFIG_HOME`` points at one;
  ``XDG_DATA_HOME`` and ``XDG_CACHE_HOME``, which Apothem does not read but the
  tools a test launches do; ``OPENCODE_CONFIG_DIR`` and ``OPENCODE_CONFIG``,
  which only add or take away an install note; and ``APOTHEM_HOOK_STATE_DIR``,
  which counts only through the hook state folder it names.
- Code that runs outside pytest.

``tests/unit/test_real_home_guard.py`` runs the guard in a pytester session, with
this file loaded as a plugin and with probe conftests that import it.
"""

from __future__ import annotations

import contextlib
import os
import sys
import tempfile
from collections.abc import Callable, Generator, Iterable, Iterator, Mapping, Sequence
from inspect import unwrap as _unwrap
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).parents[1]))

import pytest

from apothem.harnesses._shared import install_driver, install_driver_types
from apothem.hooks.lib import state_dir
from apothem.lib import install_ledger, propagation
from apothem.lib.data_home import resolve_shared_data_home
from apothem.lib.profile import DEFAULT_PROFILE_PATH

#: What ``from tests.conftest import *`` binds. The isolation fixtures start with
#: ``_``, so a star import carries them only because they are listed here; the
#: rest are the public names a star import carried before this list existed,
#: which probe conftests use (``pytest``, ``install_ledger``, ``install_driver``,
#: ``propagation``), the guard's names and every other public name of this
#: module. One earlier name is gone on purpose: ``pytest_real_home_guard``, the
#: module-level hook the guard was before it became the ``real_home_guard``
#: plugin object; importing it by name fails with ``ImportError``.
__all__ = [
    "DEFAULT_PROFILE_PATH",
    "REAL_HOME_GUARD_PLUGIN",
    "Any",
    "Callable",
    "Generator",
    "Iterable",
    "Iterator",
    "Mapping",
    "Path",
    "RealHomeGuard",
    "RealHomeGuardFailure",
    "Sequence",
    "_isolate_backup_root",
    "_isolate_hook_state",
    "_isolate_install_ledger",
    "_isolate_session_home",
    "_isolate_user_home",
    "annotations",
    "contextlib",
    "install_driver",
    "install_driver_types",
    "install_ledger",
    "os",
    "propagation",
    "pytest",
    "pytest_register_real_home_guard",
    "real_home_guard",
    "resolve_shared_data_home",
    "state_dir",
    "sys",
    "tempfile",
]

_XDG_BASE_DIRECTORIES = (
    "XDG_CONFIG_HOME",
    "XDG_STATE_HOME",
    "XDG_DATA_HOME",
    "XDG_CACHE_HOME",
)


def _redirect_home(monkeypatch: pytest.MonkeyPatch, home: Path) -> None:
    """Point every spelling of the user home at *home* and prove it took effect."""
    home.mkdir(parents=True, exist_ok=True)
    for name in ("HOME", "USERPROFILE"):
        monkeypatch.setenv(name, str(home))
    # ``Path.home()`` reads USERPROFILE first on Windows, then HOMEDRIVE and
    # HOMEPATH; drop the latter so no fallback can name the real home.
    monkeypatch.delenv("HOMEDRIVE", raising=False)
    monkeypatch.delenv("HOMEPATH", raising=False)
    # The code under test and the tools a test launches (pwsh, git, node) read
    # the XDG base directories before they fall back to the home, so a
    # developer's own setting would send their writes out of *home*. pwsh, for
    # one, keeps its startup profile and telemetry id in $XDG_CACHE_HOME.
    for name in _XDG_BASE_DIRECTORIES:
        monkeypatch.delenv(name, raising=False)
    resolved = Path.home().resolve()
    assert resolved == home.resolve(), (
        f"test HOME isolation failed: Path.home() is {resolved}, expected {home}"
    )


@pytest.fixture(scope="session", autouse=True)
def _isolate_session_home(tmp_path_factory: pytest.TempPathFactory) -> Iterator[None]:
    """Redirect the user home and the install state roots for the whole session.

    Pytest sets this fixture up before every module-, class- and package-scoped
    fixture, and those before any function-scoped autouse fixture. A fixture of
    that kind that runs an install would otherwise write the developer's real
    ``~/.agents/skills``; this keeps those writes inside a temporary directory.
    Each test then gets its own home from ``_isolate_user_home``.

    ``HOME`` and ``USERPROFILE`` cannot move ``install_ledger.STATE_ROOT`` or
    ``install_driver.BACKUP_ROOT``: both were computed from ``Path.home()`` when
    their modules were imported, so they still name the developer's
    ``~/.apothem`` after the redirect. They are set to the same places under the
    session home here, in the same ``MonkeyPatch`` context, so the install lock
    files, ledger lines and backups of a module-scoped install fixture land in
    the temporary directory too. Each test then gets its own roots from
    ``_isolate_install_ledger`` and ``_isolate_backup_root``.

    The same goes for the environment variables that place a write or a read
    whatever ``HOME`` says. ``CODEX_HOME`` is cleared, so a module-scoped fixture
    that installs for Codex writes into the session home rather than a
    developer's own Codex root. ``CLAUDE_CONFIG_DIR`` is cleared, so the
    session-start hook reads the Claude Code folder in the session home.
    ``APOTHEM_HOOK_STATE_DIR`` names a session folder, so a fixture that runs a
    stateful hook keeps its counters there rather than in the developer's own
    hook state folder. Each test then gets the same from ``_isolate_user_home``
    and ``_isolate_hook_state``.

    A session-scoped fixture that runs an install has to request this fixture as
    a parameter. pytest sets up session-scoped autouse fixtures in the order they
    were registered, a plugin's first and then a conftest's by name, so one named
    ``_install_...`` would run before ``_isolate_session_home`` and write under
    the real home.
    """
    with pytest.MonkeyPatch.context() as monkeypatch:
        home = tmp_path_factory.mktemp("session-home")
        _redirect_home(monkeypatch, home)
        monkeypatch.delenv("CODEX_HOME", raising=False)
        monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
        # A developer's own OPENCODE_CONFIG_DIR would add an OpenCode install
        # note to every OpenCode install a fixture runs, and OPENCODE_CONFIG
        # can take the opencode.jsonc note away.
        monkeypatch.delenv("OPENCODE_CONFIG_DIR", raising=False)
        monkeypatch.delenv("OPENCODE_CONFIG", raising=False)
        monkeypatch.setenv(
            "APOTHEM_HOOK_STATE_DIR", str(tmp_path_factory.mktemp("session-hook-state"))
        )
        monkeypatch.setattr(install_ledger, "STATE_ROOT", home / ".apothem" / "state")
        # ``install_driver.BACKUP_ROOT`` is the name every reader goes through. It
        # is a copy of the binding ``install_driver_types`` defines, so that one
        # moves too: no copy of the default is left naming the real home.
        for module in (install_driver, install_driver_types):
            monkeypatch.setattr(module, "BACKUP_ROOT", home / ".apothem" / "backups")
        yield


@pytest.fixture(autouse=True)
def _isolate_user_home(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> Path:
    """Give every test its own user home, a sibling of its ``tmp_path``.

    The home is created with ``tmp_path_factory`` rather than under the
    per-test ``tmp_path`` so a file-set snapshot of ``tmp_path`` never picks it
    up. A test that wants the home reads ``Path.home()`` or requests this
    fixture. ``CODEX_HOME`` is cleared so a developer's own setting cannot move
    the Codex root; ``_isolate_session_home`` has already cleared it for the
    session, and this clears it again in case a fixture set it.
    ``CLAUDE_CONFIG_DIR`` is cleared the same way, so the Claude Code folder is
    the one in this home. ``OPENCODE_CONFIG_DIR`` and ``OPENCODE_CONFIG`` are
    cleared the same way, so a developer's own setting cannot add or take away
    an OpenCode note (``_redirect_home`` clears ``XDG_CONFIG_HOME``, which
    would move the OpenCode root).
    """
    home = tmp_path_factory.mktemp("user-home")
    _redirect_home(monkeypatch, home)
    monkeypatch.delenv("CODEX_HOME", raising=False)
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    monkeypatch.delenv("OPENCODE_CONFIG_DIR", raising=False)
    monkeypatch.delenv("OPENCODE_CONFIG", raising=False)
    return home


@pytest.fixture(autouse=True)
def _isolate_install_ledger(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Redirect the install ledger to a per-test directory.

    ``install_ledger.STATE_ROOT`` defaults to ``~/.apothem/state``; without this
    a test that installs would write a real ledger under the developer's home and
    a later test's ledger-driven uninstall could read stale cross-test records.
    Mirrors the per-test ``BACKUP_ROOT`` isolation ``_isolate_backup_root`` gives.

    The default is bound when ``install_ledger`` is imported, so it does not
    follow the redirected ``HOME``. This fixture covers the test itself; the
    module-, class- and package-scoped fixtures built before it get the
    session-wide root from ``_isolate_session_home``.
    """
    monkeypatch.setattr(install_ledger, "STATE_ROOT", tmp_path / "apothem-ledger-state")


@pytest.fixture(autouse=True)
def _isolate_backup_root(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Redirect the backup root to a per-test directory for every test.

    ``install_driver.BACKUP_ROOT`` defaults to ``~/.apothem/backups``. A test that
    triggers a write (any install/update over an existing target) captures a
    backup set there; without this redirect the suite leaks hundreds of backup
    trees into the developer's real home. Redirecting it suite-wide guarantees no
    test writes under the real home, whether or not the individual test remembered
    to monkeypatch it.

    The default is bound when ``install_driver`` is imported, so it does not
    follow the redirected ``HOME``. This fixture covers the test itself; the
    module-, class- and package-scoped fixtures built before it get the
    session-wide root from ``_isolate_session_home``.

    The redirect target comes from ``tmp_path_factory`` rather than the per-test
    ``tmp_path`` so it is a sibling of — never a child of — the tree a test walks
    for a materialized-file snapshot; a content-fidelity walk over ``tmp_path``
    therefore never picks up backup residue. Tests that set ``BACKUP_ROOT``
    themselves still override this default; their explicit target simply wins.
    """
    monkeypatch.setattr(
        install_driver,
        "BACKUP_ROOT",
        tmp_path_factory.mktemp("apothem-backups-default"),
    )


@pytest.fixture(autouse=True)
def _isolate_hook_state(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Redirect the per-user hook state directory for every test.

    The session-end gate and the proactive-compaction tracker keep per-session
    counters under ``hooks/lib/state_dir.py``'s per-user root: ``<data>/state``
    when ``CLAUDE_PLUGIN_DATA`` is set, ``$XDG_STATE_HOME/apothem`` when that is
    set, else ``%LOCALAPPDATA%\\apothem\\state`` on Windows and
    ``~/.local/state/apothem`` elsewhere. Without this redirect a hook test would
    write real state there. ``_isolate_session_home`` points the variable at a
    session folder for the fixtures built before this one. Tests that set
    ``APOTHEM_HOOK_STATE_DIR`` themselves still override this default.
    """
    monkeypatch.setenv(
        "APOTHEM_HOOK_STATE_DIR", str(tmp_path_factory.mktemp("hook-state"))
    )


# --- Real-home guard --------------------------------------------------------
#
# ``real_home_guard`` is the plugin object pytest calls; importing this module
# registers it with the session that imports it (see the end of this file). The
# helpers keep their leading underscore and stay out of ``__all__``: the guard's
# hooks reach them through this module's globals, wherever a conftest imported
# the guard's names to.

#: The isolation fixtures every test has to have, in the order they are listed in
#: a failure. ``_isolate_hook_state`` is not required: the call hook checks the
#: hook state folder itself.
_ISOLATION_FIXTURES = (
    "_isolate_session_home",
    "_isolate_user_home",
    "_isolate_install_ledger",
    "_isolate_backup_root",
)


def _isolation_message(missing: list[str]) -> str:
    return (
        "real-home guard: stopped before any fixture was set up, because the "
        "isolation fixtures of tests/conftest.py do not apply to this test.\n"
        f"missing isolation fixtures: {', '.join(missing)}\n"
        "Without them Apothem uses the real home, and the test's own fixtures "
        "would write there while they are set up. Put the probe under tests/, "
        "so tests/conftest.py applies to it. Never star-import a conftest; "
        "importing single names from tests/conftest.py does not bring these "
        "fixtures either. See tests/README.md."
    )


_SESSION_HOME = "_isolate_session_home"
#: The code of this file's ``_isolate_session_home``. Code compiled from the same
#: source compares equal, so a second copy of this module still matches; a
#: fixture of the same name defined elsewhere, or a direct parametrization of
#: the name, does not.
_SESSION_HOME_CODE = _unwrap(_isolate_session_home).__code__


def _requested(definitions: Mapping[str, Sequence[Any]], name: str) -> set[str]:
    """Return every fixture name *name* requests, directly or through another.

    Each definition of a name counts, so a fixture that overrides another and
    requests it by its own name reaches what the one it overrides requests.
    """
    seen: set[str] = set()
    todo = [name]
    while todo:
        for definition in definitions.get(todo.pop(), ()):
            for argname in definition.argnames:
                if argname not in seen:
                    seen.add(argname)
                    todo.append(argname)
    return seen


def _installed_plugin_packages(item: pytest.Item) -> set[str]:
    """Return the top-level packages of the plugins loaded through an entry point."""
    return {
        str(getattr(plugin, "__name__", "")).partition(".")[0]
        for plugin, _ in item.config.pluginmanager.list_plugin_distinfo()
    }


def _setup_order_problems(item: pytest.Item) -> list[str]:
    """Return one line per way the session home would not be in place in time.

    pytest sets the fixtures of a test up in the order of ``item.fixturenames``:
    the session-scoped ones first, in the order they were registered, which is a
    ``-p`` plugin's, then a parent conftest's, then a conftest's own by name. A
    session-scoped fixture listed before ``_isolate_session_home`` runs against
    the real home unless it requests ``_isolate_session_home``, which pytest
    then sets up first. The fixtures ``_isolate_session_home`` itself requests
    (``tmp_path_factory``) are allowed, and so are the fixtures of a plugin
    installed as a package. ``_isolate_session_home`` also has to be this
    file's own: a fixture of that name defined elsewhere, or a direct
    parametrization of the name, replaces the session redirect.
    """
    names = list(getattr(item, "fixturenames", ()))
    info = getattr(item, "_fixtureinfo", None)
    definitions: Mapping[str, Sequence[Any]] = getattr(info, "name2fixturedefs", {})
    if _SESSION_HOME not in names or not definitions.get(_SESSION_HOME):
        return []
    problems = []
    used = definitions[_SESSION_HOME][-1]
    if getattr(used.func, "__code__", None) != _SESSION_HOME_CODE:
        where = used.baseid or str(getattr(used.func, "__module__", "") or "")
        problems.append(
            f"{_SESSION_HOME} is not the fixture of tests/conftest.py: one of the "
            f"same name replaces it ({where})"
        )
    needed = _requested(definitions, _SESSION_HOME)
    installed: set[str] | None = None
    for name in names[: names.index(_SESSION_HOME)]:
        found = definitions.get(name)
        if not found or found[-1].scope != "session" or name in needed:
            continue
        if _SESSION_HOME in _requested(definitions, name):
            continue
        if installed is None:
            installed = _installed_plugin_packages(item)
        module = str(getattr(found[-1].func, "__module__", "") or "")
        if module.partition(".")[0] in installed:
            continue
        where = found[-1].baseid or module
        problems.append(
            f"{name} ({where}) is session-scoped and set up before {_SESSION_HOME}"
        )
    return problems


def _setup_order_message(problems: list[str]) -> str:
    lines = "\n".join(f"  - {problem}" for problem in problems)
    return (
        "real-home guard: stopped before any fixture was set up, because a "
        "fixture would run before the session home of tests/conftest.py is in "
        "place.\n"
        f"{lines}\n"
        "pytest sets up session-scoped autouse fixtures in the order they were "
        "registered (a plugin's, then a parent conftest's, then a conftest's own "
        "by name), so such a fixture sees the real home. Request "
        "_isolate_session_home as a parameter of that fixture, and never define a "
        "fixture named _isolate_session_home. Put probes under tests/ and never "
        "star-import a conftest. See tests/README.md."
    )


#: The harness name the guard asks ``install_ledger.ledger_path`` about. Any name
#: gives the same root; this one is not a real harness, so it cannot be mistaken
#: for a ledger the test made.
_GUARD_HARNESS = "real-home-guard"


def _resolved(path: str, known: dict[str, str] | None = None) -> str:
    """Return *path* with its links resolved and its case normalized.

    *known* maps each absolute path one check has resolved to its result. A path
    below one of them that does not exist is not passed to ``os.path.realpath``,
    which costs a few hundred microseconds on Windows: a missing folder holds no
    link, so the path resolves to its folder's result plus its own name, and one
    ``lstat`` call settles that. The data home and the ``~/.config/apothem``
    folder below a test's own home cost one or two such calls instead of a
    ``realpath`` each.

    ``os.path.realpath`` and ``os.path.lexists`` read the disk through
    ``os.lstat``; a fixture can patch that, so a failure falls back to a full
    ``realpath`` and then to the absolute path, instead of failing the test for a
    reason of its own. ``Path.resolve()`` is not used: on Python 3.10 to 3.12 it
    calls ``Path.stat``, which some tests patch.
    """
    path = os.path.abspath(path)  # noqa: PTH100 - text only, no Path.stat
    if known is None:
        return _realpath_key(path)
    if path not in known:
        folder, name = os.path.split(path)
        if name and _at_or_below(folder, known) and not _lexists(path):
            above = _resolved(folder, known).rstrip(os.sep)
            known[path] = above + os.sep + os.path.normcase(name)
        else:
            known[path] = _realpath_key(path)
    return known[path]


def _realpath_key(path: str) -> str:
    try:
        resolved = os.path.realpath(path)
    except Exception:
        resolved = path
    return os.path.normcase(resolved)


def _at_or_below(folder: str, known: dict[str, str]) -> bool:
    """Return whether *folder* or a folder above it is in *known*."""
    while folder not in known:
        folder, name = os.path.split(folder)
        if not name:
            return False
    return True


def _lexists(path: str) -> bool:
    try:
        return os.path.lexists(path)
    except Exception:
        return True  # unsure: let realpath decide


def _startup_homes() -> dict[str, str]:
    """Map each spelling of the home this process started with to how it reads.

    The keys are resolved and case-normalized for comparing; the values keep the
    resolved path's own case for the failure message.
    """
    candidates = [os.environ.get("HOME"), os.environ.get("USERPROFILE")]
    # Windows falls back to these two when USERPROFILE is unset.
    drive, path = os.environ.get("HOMEDRIVE"), os.environ.get("HOMEPATH")
    if drive and path:
        candidates.append(drive + path)
    # Path.expanduser raises RuntimeError when no home can be determined.
    with contextlib.suppress(RuntimeError):
        candidates.append(str(Path("~").expanduser()))
    if sys.platform != "win32":
        import pwd

        # POSIX falls back to the account's home when HOME is unset. KeyError:
        # the uid has no passwd entry, as in some containers.
        with contextlib.suppress(KeyError):
            candidates.append(pwd.getpwuid(os.getuid()).pw_dir)
    homes: dict[str, str] = {}
    for home in candidates:
        if home and not home.startswith("~"):
            homes.setdefault(_resolved(home), _shown(home))
    return homes


def _shown(path: str) -> str:
    """Return *path* resolved, in its own case, for a failure message."""
    try:
        return os.path.realpath(path)
    except Exception:
        return path


#: What each kind of real folder is called in a failure.
_APOTHEM = "the real Apothem folder"
_CODEX = "the real Codex home"
_CLAUDE = "the real Claude Code folder"
_CONFIG = "the real config folder"


def _startup_folders(
    homes: Iterable[str],
) -> tuple[tuple[str, str, str, str], ...]:
    """Return ``(key, key prefix, shown, label)`` for each real folder Apothem uses.

    These are, for each home: ``.apothem`` (the data home, which holds the
    ledgers and the backups), ``.config/apothem`` (the support folder the install
    manifest names, and the default profile's folder) and
    ``.local/state/apothem`` (the POSIX hook state folder); then the ``apothem``
    folders in ``XDG_STATE_HOME`` and ``LOCALAPPDATA``, the other hook state
    folders; then the Codex home, the Claude Code folder and the config folder,
    each as the home names it and as ``CODEX_HOME``, ``CLAUDE_CONFIG_DIR`` and
    ``XDG_CONFIG_HOME`` named it at import. The ledger and backup roots as the
    product bound them at import are listed too: they come from ``Path.home()``
    at that moment, which is the real home unless something imported them
    earlier under a different one. The Apothem folders come first, so a path in
    ``.config/apothem`` is named for it rather than for ``.config``.

    Each folder is listed as spelled and as resolved, in case the real folder is
    a link. A folder that is a real home, or holds one or the temporary folder,
    is left out: anything inside it would count, and every test's temporary
    folder is inside it. A variable set that way is not guarded. The key prefix
    is the key with one trailing separator, for the "inside" test.
    """
    homes = list(homes)
    spelled: list[tuple[str, str]] = []
    for home in homes:
        spelled += [
            (str(resolve_shared_data_home(base=Path(home)).root), _APOTHEM),
            (str(Path(home, ".config", "apothem")), _APOTHEM),
            (str(Path(home, ".local", "state", "apothem")), _APOTHEM),
        ]
    for name in ("XDG_STATE_HOME", "LOCALAPPDATA"):
        value = os.environ.get(name, "").strip()
        if value:
            spelled.append((str(Path(value, "apothem")), _APOTHEM))
    for home in homes:
        spelled += [
            (str(Path(home, ".codex")), _CODEX),
            (str(Path(home, ".claude")), _CLAUDE),
            (str(Path(home, ".config")), _CONFIG),
        ]
    # Read the way Apothem reads each one: see _current_locations.
    codex = os.environ.get("CODEX_HOME")
    claude = os.environ.get("CLAUDE_CONFIG_DIR", "").strip()
    claude = claude and os.path.expanduser(claude)  # noqa: PTH111 - text only
    config = os.environ.get("XDG_CONFIG_HOME")
    for value, label in ((codex, _CODEX), (claude, _CLAUDE), (config, _CONFIG)):
        if value and not value.startswith("~"):
            spelled.append((value, label))
    resolved = [
        *spelled,
        (str(install_ledger.ledger_path(_GUARD_HARNESS).parent.parent), _APOTHEM),
        (str(install_driver.BACKUP_ROOT), _APOTHEM),
    ]
    # key -> (shown, label, resolved key). A spelled key can differ from its
    # resolved one by more than a link: a Windows 8.3 short name such as
    # C:\Users\RUNNER~1, which GitHub's runners use for TEMP, or macOS's /var,
    # which resolves to /private/var. Both forms are tested against both forms
    # of each home and of the temporary folder.
    folders: dict[str, tuple[str, str, str]] = {}
    for folder, label in spelled:
        absolute = os.path.abspath(folder)  # noqa: PTH100 - text only, no Path.stat
        folders.setdefault(
            os.path.normcase(absolute), (absolute, label, _resolved(folder))
        )
    for folder, label in resolved:
        key = _resolved(folder)
        folders.setdefault(key, (_shown(folder), label, key))
    wide = [*homes, tempfile.gettempdir()]
    too_wide = {_resolved(folder) for folder in wide} | {
        os.path.normcase(os.path.abspath(folder))  # noqa: PTH100 - text only
        for folder in wide
    }
    return tuple(
        (key, key.rstrip(os.sep) + os.sep, shown, label)
        for key, (shown, label, real) in folders.items()
        if not any(
            _at_or_inside(inner, form) for inner in too_wide for form in (key, real)
        )
    )


def _at_or_inside(path: str, folder: str) -> bool:
    """Return whether the key *path* is the key *folder* or inside it."""
    return path == folder or path.startswith(folder.rstrip(os.sep) + os.sep)


_REAL_HOMES = _startup_homes()
_REAL_FOLDERS = _startup_folders(_REAL_HOMES.values())
# Bound now, so a test that patches the module attribute with a mock neither sees
# an extra call nor changes what the guard computes.
_ledger_path = install_ledger.ledger_path
_hook_state_root = state_dir._state_root


def _real_location(path: str, resolved: str) -> str | None:
    """Say which real home or real folder *path* names, else ``None``.

    *resolved* is *path* as ``_resolved`` returns it. Only an exact home counts,
    and a real folder from ``_startup_folders`` or anything inside one. A folder
    elsewhere below a real home, such as the Windows temporary folder, does not.
    """
    shown = _REAL_HOMES.get(resolved)
    if shown is not None:
        return _naming("the real home", shown, path)
    for folder, prefix, shown, label in _REAL_FOLDERS:
        if resolved == folder:
            return _naming(label, shown, path)
        if resolved.startswith(prefix):
            return f"inside {label} {shown}"
    return None


def _naming(what: str, shown: str, path: str) -> str:
    """Return *what*, followed by *shown* unless *path* already reads the same."""
    spelled = os.path.abspath(path)  # noqa: PTH100 - text only, no Path.stat
    if os.path.normcase(spelled) == os.path.normcase(shown):
        return what
    return f"{what} {shown}"


def _called(function: Callable[[], object]) -> str | None:
    """Return the path *function* gives, as text, or ``None`` when it gives none."""
    try:
        return str(os.fspath(function()))
    except Exception:  # a test patched it to fail, or removed every home variable
        return None


def _hook_state_name() -> str:
    """Name the hook state folder for the variable it comes from right now.

    ``state_dir._state_root`` takes the first of these that is set; on Windows
    the last is ``LOCALAPPDATA``, which is how a test that clears the override
    reaches the real ``LOCALAPPDATA``.
    """
    for name in (state_dir.OVERRIDE_ENV, "CLAUDE_PLUGIN_DATA", "XDG_STATE_HOME"):
        if os.environ.get(name, "").strip():
            return f"the hook state folder (from {name})"
    if sys.platform == "win32" and os.environ.get("LOCALAPPDATA", "").strip():
        return "the hook state folder (from LOCALAPPDATA)"
    return "the hook state folder (from the home)"


def _hook_state_base() -> tuple[str, str | None]:
    """Return the variable the hook state folder is built on, and its folder.

    ``CLAUDE_PLUGIN_DATA`` gives ``<it>/state`` and ``XDG_STATE_HOME`` gives
    ``<it>/apothem``. Set to a real home, either puts the hook state in a folder
    below it that is not one of the real folders, so the variable itself is
    compared when it is the one that decides (``APOTHEM_HOOK_STATE_DIR`` unset).
    ``~`` is expanded, as ``state_dir`` expands it.
    """
    if os.environ.get(state_dir.OVERRIDE_ENV, "").strip():
        return "", None
    for name in ("CLAUDE_PLUGIN_DATA", "XDG_STATE_HOME"):
        value = os.environ.get(name, "").strip()
        if value:
            return name, os.path.expanduser(value)  # noqa: PTH111 - text only
    return "", None


def _current_locations() -> list[tuple[str, str | None]]:
    """Return ``(name, path)`` for each place Apothem would use right now.

    Each comes from the function, attribute or variable the product reads at
    call time: ``Path.home()`` for the data home (``resolve_install_data_home``),
    ``propagation.user_home()`` for every ``${USER_HOME}`` target the install
    manifest names, such as ``~/.config/apothem/rules``, ``ledger_path()`` for
    the install ledgers and lock files, ``install_driver.BACKUP_ROOT`` for the
    backups, ``CODEX_HOME`` for the Codex home (``lib/codex_home.py``; a leading
    ``~`` is not expanded, so it names a folder under the current one),
    ``CLAUDE_CONFIG_DIR`` for the Claude Code folder the session-start hook
    reads (``~`` expanded), ``XDG_CONFIG_HOME`` for the OpenCode folder, and
    ``state_dir._state_root()`` for the hook state folder, which on Windows
    falls back to ``LOCALAPPDATA``, and the variable that folder is built on
    (``_hook_state_base``). A variable that is unset or empty is skipped.
    """
    home = _called(Path.home)
    user_home = _called(propagation.user_home)
    claude = os.environ.get("CLAUDE_CONFIG_DIR", "").strip()
    return [
        ("HOME", os.environ.get("HOME")),
        ("USERPROFILE", os.environ.get("USERPROFILE")),
        ("Path.home()", home),
        ("propagation.user_home()", user_home),
        (
            "the data home",
            home and _called(lambda: resolve_shared_data_home(base=Path(home)).root),
        ),
        (
            "the support folder ~/.config/apothem",
            user_home and str(Path(user_home, ".config", "apothem")),
        ),
        (
            "the default profile's folder",
            _called(lambda: DEFAULT_PROFILE_PATH.expanduser().parent),
        ),
        (
            "the install ledger root (install_ledger.STATE_ROOT)",
            _called(lambda: _ledger_path(_GUARD_HARNESS).parent.parent),
        ),
        (
            "the backup root (install_driver.BACKUP_ROOT)",
            _called(lambda: install_driver.BACKUP_ROOT),
        ),
        ("CODEX_HOME", os.environ.get("CODEX_HOME")),
        ("CLAUDE_CONFIG_DIR", claude and os.path.expanduser(claude)),  # noqa: PTH111
        ("XDG_CONFIG_HOME", os.environ.get("XDG_CONFIG_HOME")),
        (_hook_state_name(), _called(_hook_state_root)),
        _hook_state_base(),
    ]


def _real_home_findings(locations: Iterable[tuple[str, str | None]]) -> list[str]:
    """Return one line per path that names a real home or a real folder.

    Names that share a path share a line, and each path is resolved once. In a
    test with its own home that is six paths: the home, two folders below it
    (settled with ``lstat`` while they do not exist), the ledger root, the
    backup root and the hook state folder, so four ``realpath`` calls.
    """
    names_by_path: dict[str, list[str]] = {}
    for name, path in locations:
        if path and not path.startswith("~"):
            names_by_path.setdefault(path, []).append(name)
    known: dict[str, str] = {}
    findings = []
    for path, names in names_by_path.items():
        real = _real_location(path, _resolved(path, known))
        if real is not None:
            findings.append(f"{', '.join(names)}: {path} is {real}")
    return findings


def _guard_message(findings: list[str]) -> str:
    lines = "\n".join(f"  - {finding}" for finding in findings)
    return (
        "real-home guard: stopped before the test body ran, because Apothem "
        "would use the real home.\n"
        f"{lines}\n"
        "The real home and its folders are the ones this process had when "
        "tests/conftest.py was imported. Tests under tests/ get a temporary home "
        "and temporary state folders from the isolation fixtures in "
        "tests/conftest.py; a fixture or the test's own setup put one of the "
        "names above back on the real location. Point it at a folder under "
        "tmp_path instead. Put probes under tests/ and never star-import a "
        "conftest. See tests/README.md."
    )


def _checked_at_pyfunc_call(item: pytest.Item) -> bool:
    """Return whether running *item* calls ``pytest_pyfunc_call``.

    ``Function.runtest`` does; a subclass that replaces it, such as the
    ``unittest`` plugin's, may not.
    """
    return (
        isinstance(item, pytest.Function)
        and type(item).runtest is pytest.Function.runtest
    )


def _check_the_call() -> None:
    findings = _real_home_findings(_current_locations())
    if findings:
        raise RealHomeGuardFailure(_guard_message(findings), pytrace=False)


class RealHomeGuardFailure(pytest.fail.Exception):  # type: ignore[misc,name-defined]
    """How the guard fails a test: ``pytest.fail``'s exception, under a type of its own.

    The type lets ``RealHomeGuard.pytest_runtest_makereport`` tell the guard's
    failure from the test's own, and keep it failed when the test is marked
    ``xfail``.
    """


class RealHomeGuard:
    """The pytest plugin that stops a test before it can use the real home.

    One instance, ``real_home_guard``, is registered per session under
    ``REAL_HOME_GUARD_PLUGIN``. Its four hooks are ordinary methods; pytest
    finds them on the object, not in the namespace of the conftest that imported
    this module, so deleting or rebinding a name there leaves them in place.
    """

    @pytest.hookimpl(tryfirst=True)
    def pytest_runtest_setup(self, item: pytest.Item) -> None:
        """Fail the test before any fixture is set up when it lacks the isolation.

        A ``tryfirst`` implementation runs before pytest's own one in
        ``runner.py``, which sets the fixtures up, so a failure here leaves every
        fixture of the test unset, under ``--setup-only`` too. It is not a
        wrapper: a ``tryfirst`` wrapper that fails before it yields leaves
        pytest's own setup wrappers unentered, and their teardown then fails with
        a ``KeyError`` on a ``StashKey``. Every one of the four fixtures is
        checked, whichever import brought the others in, and then the order the
        session-scoped fixtures will be set up in (``_setup_order_problems``).
        """
        present = set(getattr(item, "fixturenames", ()))
        missing = [name for name in _ISOLATION_FIXTURES if name not in present]
        if missing:
            raise RealHomeGuardFailure(_isolation_message(missing), pytrace=False)
        problems = _setup_order_problems(item)
        if problems:
            raise RealHomeGuardFailure(_setup_order_message(problems), pytrace=False)

    def pytest_runtest_call(self, item: pytest.Item) -> None:
        """Check an item that is not a plain test function before it runs.

        A test function is checked later, in ``pytest_pyfunc_call``. Any other
        item (a ``unittest`` case, whose ``runtest`` does not call that hook, or
        a doctest) is checked here. Not a wrapper, and neither ``tryfirst`` nor
        ``trylast``: pytest starts every ``pytest_runtest_call`` wrapper before
        it calls any plain implementation, and among the plain ones it calls the
        most recently registered first; pytest's own, which runs the item, was
        registered before this one. So the check runs after every wrapper has
        started, after the plain and ``tryfirst`` implementations of a conftest
        that imported this module (pytest registers that conftest after the
        import), and before pytest runs the item.
        """
        if not _checked_at_pyfunc_call(item):
            _check_the_call()

    def pytest_pyfunc_call(self) -> None:
        """Fail a test function before its body runs when Apothem would use the real home.

        ``Function.runtest`` calls this hook after every ``pytest_runtest_call``
        implementation has run, a plugin's plain one registered before the guard
        included, and every ``pytest_pyfunc_call`` wrapper starts before this
        plain implementation. pytest's own, which calls the function, is
        ``trylast``, so it comes right after this one. A wrapper of either hook
        that sets ``HOME`` back before it yields is seen. Returns ``None``, so
        pytest goes on to call the function.
        """
        _check_the_call()

    @pytest.hookimpl(wrapper=True, tryfirst=True)
    def pytest_runtest_makereport(
        self, call: pytest.CallInfo[None]
    ) -> Generator[None, pytest.TestReport, pytest.TestReport]:
        """Keep a test the guard stopped failed, even when it is marked ``xfail``.

        pytest's ``skipping`` plugin turns any failure of an ``xfail`` test
        without ``raises=`` into XFAIL, so a stopped test would pass the run
        quietly. This wrapper starts first and so finishes last, after
        ``skipping`` has changed the report, and changes it back.
        """
        report = yield
        if call.excinfo is not None and isinstance(
            call.excinfo.value, RealHomeGuardFailure
        ):
            report.outcome = "failed"
            if hasattr(report, "wasxfail"):
                del report.wasxfail
        return report


#: The name the guard is registered under, once per session.
REAL_HOME_GUARD_PLUGIN = "apothem-real-home-guard"
real_home_guard = RealHomeGuard()


def _register_guard(pluginmanager: pytest.PytestPluginManager) -> None:
    """Register ``real_home_guard`` unless the session already has the guard.

    The check is by name, so a second copy of this module (imported under
    another module name) does not register a second guard. ``-p
    no:apothem-real-home-guard`` blocks the name, and ``register`` then does
    nothing.
    """
    if pluginmanager.get_plugin(REAL_HOME_GUARD_PLUGIN) is None:
        with contextlib.suppress(ValueError):  # the same object, already registered
            pluginmanager.register(real_home_guard, REAL_HOME_GUARD_PLUGIN)


def _importing_plugin_manager() -> pytest.PytestPluginManager | None:
    """Return the plugin manager of the pytest session importing this module.

    pytest imports a conftest, and a ``-p`` plugin, from a method of its plugin
    manager, so that object is a local of a frame on the stack below this
    import, the nearest one being the session doing the import; a conftest that
    imports this module sits between them. The type is checked with ``type()``,
    so a mock that only claims the type does not count. ``None`` when no pytest
    session is importing: a script that imports this module, or a session
    started after the import.
    """
    frame = sys._getframe(1)
    while True:
        with contextlib.suppress(Exception):  # a frame whose locals cannot be read
            for value in list(frame.f_locals.values()):
                if issubclass(type(value), pytest.PytestPluginManager):
                    return value
                if issubclass(type(value), pytest.Config):
                    return value.pluginmanager
        if frame.f_back is None:
            return None
        frame = frame.f_back


@pytest.hookimpl(specname="pytest_configure")
def pytest_register_real_home_guard(config: pytest.Config) -> None:
    """Register the guard with a session that started after this module was imported.

    The import registers it otherwise. ``pytest_configure`` is a historic hook,
    so pytest calls this for a conftest registered after the session was
    configured too, and a star import carries it.
    """
    _register_guard(config.pluginmanager)


_plugin_manager = _importing_plugin_manager()
if _plugin_manager is not None:
    _register_guard(_plugin_manager)
del _plugin_manager
