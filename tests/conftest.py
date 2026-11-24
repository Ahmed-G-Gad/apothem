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

Apothem itself refuses the same writes in the product:
``apothem.lib.home_write_guard`` raises ``RealHomeWriteError`` for a write into
the account's real ``.apothem``, ``.config/apothem`` or a tool's folder there
while a test runs, whether or not this file loads. Some callers absorb that
error (a best-effort ledger line, a suppressed removal), so the autouse
``_report_real_home_refusals`` fails a test after which the guard logged a
refusal, also when the test is marked ``xfail``.

The isolation fixtures above are all named with a leading underscore, and a
``from <this module> import *`` skips such names unless the module lists them in
``__all__``. A probe folder whose conftest star-imported this file before it had
an ``__all__`` got none of them, and its tests ran Apothem against the
developer's real home: that once deleted a real install ledger and overwrote a
file under ``~/.config/apothem``. Two things now stop that.

``__all__`` lists the five isolation fixtures, ``_report_real_home_refusals``,
the guard's names and every other public name, so a star import of this file
carries the isolation with it, and the fixture that fails a test after which a
refusal was absorbed: without it the guard's report hook still fails such a
test, but says the refusal came while a fixture was torn down.

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
  test would fail. Before those checks it holds a refusal absorbed since the
  test before was reported (in a ``pytest_runtest_logreport`` or
  ``pytest_runtest_logfinish`` hook, a ``pytest_runtest_protocol`` wrapper, a
  ``pytest_runtest_logstart`` hook), named "between two tests, before
  <test>", or, for the first test, since the test loop started (a plain
  ``pytest_runtestloop`` implementation, which runs before pytest's own),
  named "after collection, before the first test". ``_report_real_home_refusals``
  would otherwise fail the test for it.
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
  stopped, or one after which ``_report_real_home_refusals`` found a refusal,
  stays failed when it is marked ``xfail``, which would otherwise turn the
  failure into XFAIL and let the run pass. Its teardown report also fails when
  ``apothem.lib.home_write_guard`` logged a refusal that
  ``_report_real_home_refusals`` did not see: one made while a fixture torn down
  after it (an ``_isolate_*`` fixture, a module- or session-scoped one) was
  torn down.
- ``pytest_make_collect_report``, a wrapper: the report of the node pytest was
  collecting fails when Apothem logged a refusal while it was collected (in a
  test module's module-level code, or a conftest pytest imports then), rather
  than the first test after it.
- ``pytest_sessionstart`` and ``pytest_collection_finish``, ``tryfirst``
  wrappers, which finish after every plain implementation and every wrapper
  that is not ``tryfirst``; ``pytest_runtestloop``, a ``trylast`` wrapper,
  which starts after every other wrapper and before every plain implementation
  of the hook, the one that runs the tests among them (a plain one a conftest
  registers runs before pytest's own, and the first test's setup holds what it
  logs, or, when the loop runs no test, this wrapper after its ``yield``,
  named "after collection, in a test loop that ran no test"); and the
  collect-report wrapper, before each report starts. Each holds a refusal
  absorbed outside any test before the first test, named "at the session
  start, before collection" (a conftest's import, ``pytest_configure``,
  ``pytest_sessionstart``, a ``pytest_collection`` hook), "during collection,
  before pytest collected <node>" (a hook that runs between two collect
  reports: ``pytest_itemcollected`` or ``pytest_collectreport`` for the node
  before, ``pytest_collectstart`` for that one) or "after collection, before
  the first test" (``pytest_collection_modifyitems``, a collection-finish
  hook, a ``pytest_runtestloop`` wrapper, and the last node's
  ``pytest_collectreport``). Failing the session's collection would drop
  every test, failing the next node's would blame it and stop the run before
  any test, and failing the first test would blame it; the tests run, and the
  run fails at its end.
- ``pytest_sessionfinish``, a ``trylast`` wrapper, which goes on after its
  ``yield`` once every plain implementation has run, whenever it was
  registered, and once a ``trylast`` wrapper registered after it, which pluggy
  runs inside it, has gone on after its own: it writes what is held, what such
  a wrapper absorbed included, and a refusal a plain session-finish hook
  absorbed, named "after the last test", to the terminal above the summary, and
  turns the exit code "OK" or "no tests collected" into "tests failed". A
  ``tryfirst`` ``pytest_sessionfinish`` wrapper does the same after pytest's
  terminal reporter has written the summary, calling every
  ``pytest_terminal_summary`` hook. In an xdist controller, which runs no test
  itself, that wrapper first holds, before its ``yield``, what the controller's
  own hooks logged while the workers ran the tests, named "in the xdist
  controller, during the test run"; in an xdist worker it holds there what was
  logged after the last test (in a ``pytest_runtest_logfinish`` hook, say),
  named "after the last test", so the worker writes it to its file (see below)
  before any plain session-finish hook runs. A ``tryfirst``
  ``pytest_unconfigure`` wrapper does it for a refusal absorbed in
  ``pytest_unconfigure`` ("after the session finished", or "while pytest ran no
  test session" when no session started: a ``pytest_configure`` hook ended the
  run with ``pytest.exit``, or ``--markers`` or ``--help`` ran), and in an
  xdist controller for what the workers wrote to their files (see below):
  pytest returns the session's exit status after that hook. That wrapper also
  turns "OK" or "no tests collected" into "tests failed" again once the guard
  has reported a refusal in the session, which ``pytest.exit(returncode=0)`` in
  a plain ``pytest_sessionfinish`` hook would otherwise undo: pytest sets the
  status from that call after every session-finish wrapper has finished. pytest
  catches no ``SystemExit`` around either hook, so ``sys.exit(0)`` would end
  the process with 0 whatever that status says: once the guard has reported a
  refusal, both ``tryfirst`` wrappers raise ``SystemExit(1)`` in place of a
  ``SystemExit`` with the code 0, 5 or ``None`` from a hook they wrap (or a
  code a POSIX system cuts to 0 or 5, such as 256), and the
  ``pytest_cmdline_main`` wrapper below does the same for one they do not see.
  Any other code stays. A refusal absorbed later still, in a cleanup registered
  with ``config.add_cleanup``, reaches only ``stderr``, unless such a passing
  exit follows it or one left the session finish before it. These ``tryfirst``
  wrappers finish after every wrapper except a ``tryfirst`` one that pytest
  registered after the guard (a conftest's): a refusal absorbed after such a
  ``pytest_sessionfinish`` wrapper's ``yield`` is named "after the session
  finished", and one after such a ``pytest_unconfigure`` wrapper's ``yield``
  reaches only ``stderr``, unless such a passing exit follows it or one left
  the session finish before it.
- ``pytest_cmdline_main``, a ``tryfirst`` wrapper. pytest runs the
  session-finish and unconfigure hooks and the cleanups inside that hook, so it
  sees a ``SystemExit`` after all of them: one from a ``tryfirst`` wrapper of
  either hook that pytest registered after the guard, or from a cleanup, which
  finish after the guard's other wrappers, and one from an xdist controller's
  plain session-finish hook, before the controller read its workers' files.
  When such an exit passes and the guard has reported nothing yet, it reads
  those files, holds what was logged since the guard's other hooks, named
  "after the session finished", and reports it; once the guard has reported a
  refusal, the exit becomes ``SystemExit(1)``. pytest skips
  ``pytest_unconfigure`` and the cleanups when an exception leaves the session
  finish, and calls them after this hook, where it would not see a passing
  exit they raise. So when an exception (a ``SystemExit``, or any other) leaves
  the session finish, this wrapper calls them itself
  (``config._ensure_unconfigure``, which pytest then finds done), takes a
  ``SystemExit`` they raise as the exit, and judges the exit after them: a
  passing one fails the run also when the only refusal came in
  ``pytest_unconfigure``, in a cleanup, or after the ``yield`` of such a later
  ``tryfirst`` unconfigure wrapper.
- ``pytest_testnodedown`` and ``pytest_configure_node``, optional hooks that
  only xdist defines and calls in the controller. A worker's terminal output is
  discarded and the controller does not use its exit code, so a worker sends
  what it holds to the controller. Its ``trylast`` session-finish wrapper puts
  it in ``config.workeroutput`` once every plain session-finish hook has run,
  which xdist's own wrapper then sends, and the controller's
  ``pytest_testnodedown`` holds it under the worker's name, once also for a
  worker that stopped on Ctrl-C, which xdist reports down twice. The worker
  also appends each refusal, as it holds it, to a file that the controller's
  ``pytest_configure_node`` named in the worker's ``workerinput``: one per
  worker, in a folder the controller makes for the session with
  ``tempfile.mkdtemp``, so a folder an earlier run left is never read, and
  never in a protected folder of a real home. Until the hand-off the file holds
  a copy of what the worker hands over, which the controller reports only when
  ``pytest_testnodedown`` did not take that hand-off from the worker's output:
  a hook of the controller ended its test loop with ``pytest.exit``; the
  worker's session stopped before its session finish (``pytest.exit`` in its
  ``pytest_sessionstart``, say), so it handed nothing over; a session-finish
  wrapper that encloses the guard's raised or called ``pytest.exit`` before its
  ``yield``, so the guard's never ran and xdist sent the output without the
  hand-off; or the worker crashed or was stopped before the hand-off
  (``os._exit`` in a plain session-finish hook, say), which xdist reports as a
  worker down without failing any test when none was running on it. What a
  worker finds after the hand-off, after another session-finish wrapper's
  ``yield``, in its terminal summary or in its ``pytest_unconfigure``, reaches
  the controller through the file alone. The controller's
  ``pytest_unconfigure`` wrapper reads the files, holds each refusal named "in
  xdist worker <name>, after it handed its refusals to the controller, ..."
  (without "after it handed ..." for one the worker wrote before the hand-off)
  and removes the folder. Before it reads them, every worker has been told to
  exit and its process has ended: xdist's own ``pytest_sessionfinish`` in the
  controller does that, and the wrapper does it again for a worker still
  running, as when a plain session-finish hook that pluggy calls before xdist's
  ended the run with ``pytest.exit``. A worker still running Python code 5
  seconds after it was told gets a ``KeyboardInterrupt``; on Windows one
  blocked in a sleep or another call does not, since ``_thread.interrupt_main``
  does not wake it. One still running after 10 seconds is stopped. A refusal
  that a worker neither handed over nor wrote to its file before it ended or
  was stopped reaches only ``stderr``: one it logged in a plain session-finish
  hook that then ended the process with ``os._exit``, say, or one it held while
  it could not write to the file. So does everything a worker finds after the
  hand-off when the controller could not make the folder or the worker cannot
  write to it.

The guard fails a test with ``RealHomeGuardFailure``, ``pytest.fail``'s exception
under a type of its own, so the report hook can tell it apart. The hook looks
for a mark on the class rather than for the class itself: pytest can import
this file as two modules (``conftest`` and ``tests.conftest``, when
``python -m pytest`` runs from ``tests/`` with a conftest there that imports
from ``tests.conftest``, or with ``-p tests.conftest`` and the repository root
on ``PYTHONPATH``), and the ``_report_real_home_refusals`` of one copy then
raises its own class while the guard registered from the other checks.
``-p no:apothem-real-home-guard`` turns the guard off. They are hooks, not
autouse fixtures: a fixture runs at a point in the setup that depends on its
scope, its name and the order the conftests were registered.

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
  which only add or take away an OpenCode note; and ``APOTHEM_HOOK_STATE_DIR``,
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
from json import dumps as _dumps
from json import loads as _loads
from pathlib import Path
from shutil import rmtree as _rmtree
from typing import Any

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).parents[1]))

import pytest

from apothem.harnesses._shared import install_driver, install_driver_types
from apothem.hooks.lib import state_dir
from apothem.lib import home_write_guard, install_ledger, propagation
from apothem.lib.data_home import resolve_shared_data_home
from apothem.lib.profile import DEFAULT_PROFILE_PATH

#: What ``from tests.conftest import *`` binds. The isolation fixtures and
#: ``_report_real_home_refusals`` start with ``_``, so a star import carries
#: them only because they are listed here; the rest are the public names a star
#: import carried before this list existed, which probe conftests use
#: (``pytest``, ``install_ledger``, ``install_driver``, ``propagation``), the
#: guard's names and every other public name of this module. One earlier name
#: is gone on purpose: ``pytest_real_home_guard``, the module-level hook the
#: guard was before it became the ``real_home_guard`` plugin object; importing
#: it by name fails with ``ImportError``.
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
    "_report_real_home_refusals",
    "annotations",
    "contextlib",
    "home_write_guard",
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


@pytest.fixture(autouse=True)
def _report_real_home_refusals() -> Iterator[None]:
    """Fail a test after which Apothem refused a write into the real home.

    ``apothem.lib.home_write_guard`` refuses a write into the account's real
    home while a test runs, and logs each refusal in the process. Some callers
    absorb the error (a best-effort ledger line, a suppressed removal), so a
    test can pass while the refusal fired; this fixture reads the log at
    teardown and fails the test when it holds anything. A test of the guard
    itself drains the log before it finishes. It fails with
    ``RealHomeGuardFailure``, which the guard's report hook keeps failed when
    the test is marked ``xfail``, also when this fixture comes from a second
    copy of this file (see :func:`_is_guard_failure`); a plain ``pytest.fail``
    would turn into XFAIL there and let the run pass.
    """
    yield
    refused = home_write_guard.drain_refusals()
    if refused:
        raise RealHomeGuardFailure(
            "Apothem refused a write into the account's real home during this "
            "test, and the refusal was not raised to the test:\n"
            + "\n".join(f"  - {error}" for error in refused),
            pytrace=False,
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
    ``xfail``. It tells them apart by the mark below, not by the class: every
    copy of this module makes a class of its own (see
    :func:`_is_guard_failure`).
    """

    #: The mark :func:`_is_guard_failure` looks for. Every copy of this module
    #: sets it the same way, so a failure from any copy carries it.
    _apothem_real_home_guard_failure = True


class RealHomeGuard:
    """The pytest plugin that stops a test before it can use the real home.

    One instance, ``real_home_guard``, is registered per session under
    ``REAL_HOME_GUARD_PLUGIN``. Its hooks are ordinary methods; pytest
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

        First it holds what the refusal log took since the test before was
        reported (see :func:`_hold_before_the_test`).
        """
        _hold_before_the_test(item)
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
        without ``raises=`` into XFAIL, in its setup, call or teardown, so a
        stopped test, or an absorbed refusal ``_report_real_home_refusals``
        found, would pass the run quietly. This wrapper starts first and so
        finishes last, after ``skipping`` has changed the report, and changes it
        back for a ``RealHomeGuardFailure`` from any copy of this module (see
        :func:`_is_guard_failure`). A teardown report also fails on a refusal
        logged too late for ``_report_real_home_refusals`` (see
        :func:`_fail_on_late_refusals`).
        """
        report = yield
        if call.excinfo is not None and _is_guard_failure(call.excinfo.value):
            _keep_failed(report)
        if report.when == "teardown":
            _fail_on_late_refusals(report)
        return report

    @pytest.hookimpl(wrapper=True, tryfirst=True)
    def pytest_sessionstart(
        self, session: pytest.Session
    ) -> Generator[None, None, None]:
        """Hold a refusal Apothem logged before the session collected anything.

        One absorbed while a conftest was imported, while pytest was configured
        or in a ``pytest_sessionstart`` hook would otherwise fail the session's
        collection, which drops every test, and the xdist controller, which
        collects nothing, would report it as made after the last test. As a
        ``tryfirst`` wrapper this finishes after every plain implementation and
        every wrapper that is not ``tryfirst``. It holds the refusal, and
        :meth:`pytest_sessionfinish` reports it and fails the run once the tests
        have run.
        """
        session.config.stash[_HELD_SESSION] = session
        try:
            return (yield)
        finally:
            _hold(session.config, _AT_SESSION_START)

    @pytest.hookimpl(wrapper=True)
    def pytest_make_collect_report(
        self, collector: pytest.Collector
    ) -> Generator[None, pytest.CollectReport, pytest.CollectReport]:
        """Fail the collection of a node after which Apothem logged a refusal.

        A refusal absorbed while a collector ran, in a test module's
        module-level code or a conftest pytest imports during collection, say,
        would otherwise stay in the log until the first test's teardown and fail
        that test. The report of the node pytest was collecting then fails
        instead. A report that failed already keeps its own error, with the
        refusal added.

        What was logged before the report starts is held for the end of the
        run, as at the session start (see :meth:`pytest_sessionstart`), so
        only a refusal logged while this node was collected fails it. Before
        the session's own report, that is one from a ``pytest_collection``
        hook, named as from the session start: failing the session's report
        would drop every test. Before any other node's, it is one from a hook
        that runs between two collect reports (``pytest_itemcollected`` or
        ``pytest_collectreport`` for the node before, ``pytest_collectstart``
        for this one), named for the node pytest collects next: failing that
        node's report would blame it, and stop the run before any test.
        """
        if isinstance(collector, pytest.Session):
            _hold(collector.config, _AT_SESSION_START)
        else:
            where = f"{_DURING_COLLECTION}, before pytest collected {collector.nodeid}"
            _hold(collector.config, where)
        report = yield
        refused = home_write_guard.drain_refusals()
        if refused:
            where = f"while pytest collected {collector.nodeid or 'the session'}"
            message = _outside_any_test(refused, where)
            if report.outcome == "failed":
                message = f"{report.longrepr}\n\n{message}"
            report.outcome = "failed"
            report.longrepr = message
        return report

    @pytest.hookimpl(wrapper=True, tryfirst=True)
    def pytest_collection_finish(
        self, session: pytest.Session
    ) -> Generator[None, None, None]:
        """Hold a refusal Apothem logged after the last collect report.

        One absorbed in a ``pytest_collection_modifyitems``,
        ``pytest_collection_finish`` or ``pytest_report_collectionfinish`` hook
        would otherwise fail the first test, as made during it. As a
        ``tryfirst`` wrapper this finishes after every plain implementation and
        every wrapper that is not ``tryfirst``. pytest calls the hook even when
        the collection stops on an error, so the refusal is named for where it
        happened also when no test runs.
        """
        try:
            return (yield)
        finally:
            _hold(session.config, _BEFORE_THE_FIRST_TEST)

    @pytest.hookimpl(wrapper=True, trylast=True)
    def pytest_runtestloop(
        self, session: pytest.Session
    ) -> Generator[None, object, object]:
        """Hold a refusal Apothem logged after collection, before the first test.

        A ``trylast`` wrapper starts after every other wrapper of the hook and
        before every plain implementation, the one that runs the tests
        (pytest's own, or xdist's) among them, so this sees one absorbed after
        :meth:`pytest_collection_finish`: by another ``pytest_runtestloop``
        wrapper before it yields, or by a ``pytest_collection`` wrapper after it
        yields. A plain implementation a conftest registers runs before
        pytest's own, after this: the first test's setup holds what it logs
        (:func:`_hold_before_the_test`).

        When the loop ran no test (``--co``, every test deselected, or a
        collection error that stops the run), no setup took what such a plain
        implementation logged, so this holds it after its ``yield``, named
        "after collection, in a test loop that ran no test" rather than, at
        the session finish, "after the last test". An xdist controller runs
        no test itself: what it logged in the loop is named for the run, in
        :meth:`pytest_sessionfinish_after_the_summary`.
        """
        config = session.config
        _hold(config, _BEFORE_THE_FIRST_TEST)
        try:
            return (yield)
        finally:
            ran_a_test = config.stash.get(_A_TEST_STARTED, False)
            if not ran_a_test and not _is_controller(config):
                _hold(config, _IN_A_LOOP_WITHOUT_TESTS)

    @pytest.hookimpl(wrapper=True, trylast=True)
    def pytest_sessionfinish(
        self, session: pytest.Session
    ) -> Generator[None, None, None]:
        """Fail the run when Apothem logged a refusal after the last test.

        A ``pytest_sessionfinish`` hook can absorb a refusal after the last
        teardown report. As a ``trylast`` wrapper it goes on after its
        ``yield`` once every plain implementation has run, whenever it was
        registered (a ``trylast`` one of a conftest that pytest found during
        collection included), and before every wrapper registered before it
        goes on after its own. pluggy runs a ``trylast`` wrapper registered
        after it (a conftest's) inside it, so this still holds what that
        wrapper absorbs after its ``yield``. The refusal is written there to
        the terminal above the summary, with every refusal the guard holds for
        the end of the run (one from before the first test, see
        :meth:`pytest_sessionstart` and :meth:`pytest_collection_finish`, one
        from a test loop that ran no test, see :meth:`pytest_runtestloop`, or
        one an xdist worker sent, see :meth:`pytest_testnodedown`), and the
        run's exit code becomes "tests failed". An xdist worker hands them to
        the controller instead, in ``config.workeroutput``: the worker's
        terminal output is discarded and the controller does not use its exit
        code. xdist's own wrapper sends that output after its ``yield``, so
        after this one, and sends it also when another wrapper stopped the
        session finish before this one started. The worker wrote each of them
        to a file as it held it (:func:`_write_ahead`), which the controller
        reads when this hand-off never reached it, and what the worker finds
        after the hand-off reaches the controller in that file alone (see
        :meth:`pytest_configure_node`).
        """
        try:
            return (yield)
        finally:
            _hold(session.config, _AFTER_THE_LAST_TEST)
            _report_held(session.config, session, to_the_controller=True)
            session.config.stash[_HANDED_OFF] = True

    @pytest.hookimpl(wrapper=True, tryfirst=True, specname="pytest_sessionfinish")
    def pytest_sessionfinish_after_the_summary(
        self, session: pytest.Session
    ) -> Generator[None, None, None]:
        """Fail the run on a refusal absorbed after :meth:`pytest_sessionfinish`.

        pytest's terminal reporter writes the summary after it yields in its
        own ``pytest_sessionfinish`` wrapper, and calls every
        ``pytest_terminal_summary`` hook there; any wrapper's code after its
        ``yield`` runs after every plain implementation too. As a ``tryfirst``
        wrapper this finishes after every plain implementation and every
        wrapper that is not ``tryfirst``, the terminal reporter's included, so
        it sees a refusal absorbed in any of them. The refusal is written below
        the summary and the run's exit code becomes "tests failed". An xdist
        worker has handed its refusals to the controller by then, so it appends
        this one to the file the controller gave it, which the controller reads
        in :meth:`pytest_unconfigure` (see :meth:`pytest_configure_node`).
        pytest catches no ``SystemExit`` around the hook, so ``sys.exit(0)`` in
        any of them would end the process with 0 after the guard reported a
        refusal; such an exit becomes ``SystemExit(1)`` here
        (:func:`_a_passing_exit_fails`), and one from a wrapper that finishes
        after this one does in :meth:`pytest_cmdline_main`.

        Before its ``yield`` it holds what an xdist controller logged since the
        test loop started. The controller runs no test itself, so that came
        from one of its own hooks while its workers ran the tests (a
        ``pytest_runtest_logreport`` hook of a reporting plugin, say), not
        after the last test. In an xdist worker it holds there what was
        logged after the last test (in a ``pytest_runtest_logreport`` or
        ``pytest_runtest_logfinish`` hook, say), named as
        :meth:`pytest_sessionfinish` names it, so the worker writes it to its
        file (:func:`_write_ahead`) before any plain session-finish hook runs:
        one that crashes the worker or ends it with ``os._exit`` leaves it in
        the file.
        """
        session.config.stash[_HELD_SESSION] = session
        if _is_controller(session.config):
            _hold(session.config, _IN_THE_CONTROLLER_DURING_THE_RUN)
        elif _is_worker(session.config):
            _hold(session.config, _AFTER_THE_LAST_TEST)
        with _a_passing_exit_fails(session.config):
            try:
                return (yield)
            finally:
                _hold(session.config, _AFTER_THE_LAST_TEST)
                _report_held(session.config, session)

    @pytest.hookimpl(wrapper=True, tryfirst=True)
    def pytest_unconfigure(self, config: pytest.Config) -> Generator[None, None, None]:
        """Fail the run on a refusal absorbed in ``pytest_unconfigure``.

        pytest calls the hook after the session finished and returns the
        session's exit status after it, so the status set here is the run's. As
        a ``tryfirst`` wrapper this finishes after every plain implementation
        and every wrapper that is not ``tryfirst``, and after every ``tryfirst``
        one registered before the guard. A ``tryfirst`` wrapper registered
        after it (a conftest's) finishes later still: a refusal absorbed after
        its ``yield`` reaches only ``stderr``, as one in a cleanup registered
        with ``config.add_cleanup`` does. An xdist worker appends the refusal
        to the file the controller gave it, as after the summary.

        In an xdist controller this also reports what each worker wrote to
        that file (:func:`_take_late`), once every worker process has ended:
        xdist's own ``pytest_sessionfinish`` in the controller waits for
        that, and :func:`_take_late` waits again for a worker still running
        (:func:`_end_the_workers`), which a plain session-finish hook called
        before xdist's leaves when it ends the run with ``pytest.exit``.

        Last, once the guard has reported a refusal in this session, it sets
        "tests failed" again when the exit status is "OK" or "no tests
        collected". A plain ``pytest_sessionfinish`` hook that calls
        ``pytest.exit(returncode=0)`` would otherwise pass the run: pytest
        catches that call after every session-finish wrapper has finished, the
        guard's included, and sets the status to its code. A code other than 0
        or 5 is kept. pytest catches no ``SystemExit`` around this hook, so
        ``sys.exit(0)`` in a plain ``pytest_unconfigure`` hook would pass the
        run too; it becomes ``SystemExit(1)`` (:func:`_a_passing_exit_fails`),
        as one from a session-finish hook does in
        :meth:`pytest_sessionfinish_after_the_summary`. When an exception
        left the session finish, :meth:`pytest_cmdline_main` calls this hook
        while that exception is under way, and then judges a ``SystemExit``
        with what was reported here too.

        When no session started, what it holds is named "while pytest ran
        no test session": a refusal from a conftest's import or a
        ``pytest_configure`` hook that then ended the run with
        ``pytest.exit``, or one under ``--markers`` or ``--help``, which
        start none. pytest made a session before it configured and returns
        its exit status after this hook, so that status is set too; the
        session registered itself as the plugin ``session``. ``--markers``
        and ``--help`` make none, and exit 0.
        """
        with _a_passing_exit_fails(config):
            try:
                return (yield)
            finally:
                _take_late(config)
                session = config.stash.get(_HELD_SESSION, None)
                if session is not None:
                    _hold(config, _AFTER_THE_SESSION)
                else:
                    _hold(config, _WITHOUT_A_SESSION)
                    # A session pytest made but never started (pytest.exit in
                    # pytest_configure, say) registered itself as "session".
                    session = config.pluginmanager.get_plugin("session")
                _report_held(config, session)
                if config.stash.get(_REPORTED, False):
                    _fail_the_run(session)

    @pytest.hookimpl(wrapper=True, tryfirst=True)
    def pytest_cmdline_main(
        self, config: pytest.Config
    ) -> Generator[None, object, object]:
        """Fail a run that a passing ``SystemExit`` ends after a refusal.

        pytest runs the session-finish and unconfigure hooks, and the
        cleanups registered with ``config.add_cleanup``, inside this hook,
        and catches no ``SystemExit`` around them. The guard's ``tryfirst``
        wrappers of the first two turn a passing one into ``SystemExit(1)``
        (:func:`_a_passing_exit_fails`), but they finish before a
        ``tryfirst`` wrapper of either hook that pytest registered after the
        guard (a conftest's) and before every cleanup, and an xdist
        controller reads its workers' files only in ``pytest_unconfigure``,
        after a plain session-finish hook that ended the run. As a
        ``tryfirst`` wrapper this sees such an exit last. When it passes (see
        :func:`_a_passing_code`) and the guard has reported nothing yet, it
        reads the workers' files (:func:`_take_late`), holds what was logged
        since the guard's other hooks, named "after the session finished",
        and reports it. Once the guard has reported a refusal in the session,
        such an exit becomes ``SystemExit(1)``.

        An exception that leaves the session finish (a ``SystemExit``, or
        any other) skips pytest's own call of ``pytest_unconfigure`` and the
        cleanups, which pytest's ``main`` then makes after this hook, where
        this wrapper would not see what they raise: a passing ``SystemExit``
        from a cleanup or from a ``tryfirst`` unconfigure wrapper that pytest
        registered after the guard would end the process with 0 after the
        guard reported a refusal. So this wrapper makes that call itself
        (``config._ensure_unconfigure``, which pytest's ``main`` then finds
        done) and treats a ``SystemExit`` it raises as the exit, as pytest
        would. The exit the session finish raised is judged after it, so a
        passing one fails the run also when the only refusal came in
        ``pytest_unconfigure``, in a cleanup, or after the ``yield`` of such
        a later unconfigure wrapper. Without that call (a pytest that no longer
        has it) the exit is judged as it left the session finish.
        """
        try:
            return (yield)
        except BaseException as error:
            ended = error
            unconfigure = getattr(config, "_ensure_unconfigure", None)
            if getattr(config, "_configured", False) and callable(unconfigure):
                try:
                    unconfigure()
                except SystemExit as later:
                    ended = later
            if not isinstance(ended, SystemExit):
                raise
            passing = _a_passing_code(ended.code)
            if passing and not config.stash.get(_REPORTED, False):
                _take_late(config)
                _hold(config, _AFTER_THE_SESSION)
                _report_held(config, config.stash.get(_HELD_SESSION, None))
            if passing and config.stash.get(_REPORTED, False):
                raise SystemExit(pytest.ExitCode.TESTS_FAILED) from ended
            if ended is error:
                raise
            raise ended from error

    @pytest.hookimpl(optionalhook=True)
    def pytest_testnodedown(self, node: object) -> None:
        """Hold the refusals an xdist worker sent, for the controller to report.

        xdist calls this in the controller when a worker has finished, with
        the ``config.workeroutput`` the worker sent (see
        :meth:`pytest_sessionfinish`), and when one crashed, which sent none.
        For a worker that stopped on Ctrl-C it calls this twice, so the
        refusals are taken out of that output the first time. What a worker
        finds after it sent that output reaches the controller in a file
        instead (see :meth:`pytest_configure_node`). The worker also writes
        each refusal it sends to that file as it holds it
        (:func:`_write_ahead`), for a controller whose test loop ended before
        it took the output (a hook that called ``pytest.exit``, say) and for
        a worker that crashed or was stopped before it sent any. A worker
        is noted here only when its output holds the refusals it handed
        over, and :func:`_take_late` then skips that copy; so is whether
        that output says the copy failed and left the file empty, which
        :func:`_take_late` then skips too. xdist sends the
        output also when the hand-off never ran: a session-finish wrapper
        of a conftest, which pytest registers in the worker before xdist's
        own and which encloses the guard's, raised or called ``pytest.exit``
        before its ``yield``. The copy is the only one then. A worker that
        held nothing at the hand-off wrote nothing to the file before it.
        Only xdist defines the hook, so it is optional: without xdist pytest
        neither calls it nor rejects it.
        """
        output = getattr(node, "workeroutput", None)
        config = getattr(node, "config", None)
        if not isinstance(output, dict) or not isinstance(config, pytest.Config):
            return
        handed = output.pop(_TO_THE_CONTROLLER, None)
        if handed is None:
            return  # nothing handed over, or taken at a first call already
        worker = getattr(getattr(node, "gateway", None), "id", "?")
        config.stash.setdefault(_TAKEN, set()).add(str(worker))
        if output.pop(_COPY_LEFT_EMPTY, False):
            config.stash.setdefault(_LEFT_EMPTY, set()).add(str(worker))
        held = config.stash.setdefault(_HELD, [])
        for where, messages in handed:
            held.append((f"in xdist worker {worker}, {where}", tuple(messages)))

    @pytest.hookimpl(optionalhook=True)
    def pytest_configure_node(self, node: object) -> None:
        """Name a file that takes an xdist worker's refusals to the controller.

        xdist calls this in the controller for each worker it starts, one that
        replaces a crashed worker included, before it sends the worker
        ``node.workerinput``, which the worker reads as
        ``config.workerinput``. The guard names a file there, one per worker
        and written by that worker alone, in a folder the controller makes
        for the session (:func:`_late_folder`). A worker appends each refusal
        to it as it holds it (:func:`_write_ahead`): until it hands its
        refusals to the controller as a copy of what it hands over, which
        counts when the worker crashes or is stopped before that, and after
        it what it finds in its terminal summary, after another
        session-finish wrapper's ``yield`` or in its ``pytest_unconfigure``
        (see :func:`_sent_late`). The controller reads the files in
        :meth:`pytest_unconfigure`. Only xdist defines the hook, so it is
        optional, as :meth:`pytest_testnodedown` is.
        """
        config = getattr(node, "config", None)
        workerinput = getattr(node, "workerinput", None)
        if not isinstance(config, pytest.Config) or not isinstance(workerinput, dict):
            return
        folder = _late_folder(config)
        if folder is None:
            return
        worker = str(workerinput.get("workerid", "?"))
        path = str(Path(folder, f"{worker}.jsonl"))
        config.stash.setdefault(_LATE_FILES, {})[path] = worker
        workerinput[_LATE_TO_THE_CONTROLLER] = path


def _is_guard_failure(error: BaseException) -> bool:
    """Return whether *error* is the guard's failure, or a group that holds one.

    The guard's failure is an exception whose class carries the mark of
    ``RealHomeGuardFailure``, whichever copy of this module made the class.
    pytest can import this file as two modules when ``python -m pytest`` runs
    from ``tests/``, where pytest loads it as the conftest ``conftest``. A
    conftest under ``tests/`` that imports from ``tests.conftest`` then
    imports it again under that name; ``-p tests.conftest``, with the
    repository root on ``PYTHONPATH``, imports it as ``tests.conftest``
    before pytest loads it as the conftest. The guard is registered once, by
    name, from the copy imported first, so ``_report_real_home_refusals`` can
    come from the other copy and raise that copy's class, which an
    ``isinstance`` check against this copy's class would miss: the test would
    pass as XFAIL.

    pytest raises the errors of several finalizers that failed in one teardown
    together, as an exception group.
    """
    if getattr(type(error), "_apothem_real_home_guard_failure", False) is True:
        return True
    inner = getattr(error, "exceptions", None)
    return isinstance(inner, tuple) and any(
        isinstance(each, BaseException) and _is_guard_failure(each) for each in inner
    )


def _keep_failed(report: pytest.TestReport) -> None:
    """Mark *report* failed and drop the ``xfail`` note pytest's skipping added."""
    report.outcome = "failed"
    if hasattr(report, "wasxfail"):
        del report.wasxfail


def _fail_on_late_refusals(report: pytest.TestReport) -> None:
    """Fail a teardown report when Apothem logged a refusal nobody reported.

    ``_report_real_home_refusals`` reads the log in its own teardown, so a
    refusal made while a fixture torn down after it was torn down (an
    ``_isolate_*`` fixture, a module- or session-scoped one) is still in the
    log. pytest builds the teardown report after every finalizer of the
    teardown has run, so this check sees it, the session's last teardown
    included.
    """
    refused = home_write_guard.drain_refusals()
    if not refused or report.outcome == "failed":
        return
    _keep_failed(report)
    report.longrepr = (
        "Apothem refused a write into the account's real home while a fixture "
        "was torn down, and the refusal was not raised to the test:\n"
        + "\n".join(f"  - {error}" for error in refused)
    )


def _outside_any_test(refused: Iterable[object], where: str) -> str:
    """Return the report of refusals Apothem logged outside any test, *where*."""
    return (
        "Apothem refused a write into the account's real home outside any "
        f"test, {where}, and the refusal was not raised:\n"
        + "\n".join(f"  - {error}" for error in refused)
    )


#: Where Apothem logged a refusal outside any test, as its report names it.
_AT_SESSION_START = "at the session start, before collection"
_DURING_COLLECTION = "during collection"
_BEFORE_THE_FIRST_TEST = "after collection, before the first test"
_IN_A_LOOP_WITHOUT_TESTS = "after collection, in a test loop that ran no test"
_BETWEEN_TWO_TESTS = "between two tests"
_IN_THE_CONTROLLER_DURING_THE_RUN = "in the xdist controller, during the test run"
_AFTER_THE_LAST_TEST = "after the last test"
_AFTER_THE_SESSION = "after the session finished"
_WITHOUT_A_SESSION = "while pytest ran no test session"

#: The refusals the guard holds for the end of the run, as ``(where, messages)``.
_HELD = pytest.StashKey[list[tuple[str, tuple[str, ...]]]]()
#: The session whose exit status ``pytest_unconfigure`` sets: for a refusal
#: found there, and again after ``pytest.exit`` reset it.
_HELD_SESSION = pytest.StashKey[pytest.Session]()
#: Set once the first test's setup has started.
_A_TEST_STARTED = pytest.StashKey[bool]()
#: The ``config.workeroutput`` key an xdist worker sends its held refusals under.
_TO_THE_CONTROLLER = "apothem-real-home-refusals"
#: The ``config.workeroutput`` key an xdist worker sets when the copy of its
#: refusals it wrote beside the hand-off failed and left its file empty.
_COPY_LEFT_EMPTY = "apothem-real-home-copy-left-empty"
#: The ``workerinput`` key that names the file an xdist worker appends each
#: refusal it holds to: a copy of what it hands over, and then what it finds
#: after that hand-off.
_LATE_TO_THE_CONTROLLER = "apothem-real-home-late-refusals"
#: In an xdist controller: the folder of those files, ``None`` once it is
#: removed or when it could not be made, and each worker's file, mapped to the
#: worker's name.
_LATE_FOLDER = pytest.StashKey[str | None]()
_LATE_FILES = pytest.StashKey[dict[str, str]]()
#: How the controller names what a worker wrote to that file once it had
#: handed its refusals over.
_AFTER_THE_HAND_OFF = "after it handed its refusals to the controller"
#: Set in an xdist worker once its ``trylast`` session-finish wrapper has
#: handed what it held to the controller; a worker whose session stopped
#: before its session finish never sets it.
_HANDED_OFF = pytest.StashKey[bool]()
#: In an xdist worker: how many of the refusals the guard holds (``_HELD``)
#: the worker has written to its file already (see :func:`_write_ahead`).
_IN_THE_FILE = pytest.StashKey[int]()
#: In an xdist controller: the workers whose hand-off ``pytest_testnodedown``
#: took from their ``config.workeroutput``.
_TAKEN = pytest.StashKey[set[str]]()
#: In an xdist controller: the workers of ``_TAKEN`` whose output said that
#: the copy beside the hand-off left their file empty (``_COPY_LEFT_EMPTY``).
_LEFT_EMPTY = pytest.StashKey[set[str]]()
#: Set once the guard has reported a refusal and failed the run.
_REPORTED = pytest.StashKey[bool]()
#: The exit statuses a held refusal turns into "tests failed".
_PASSED_OR_EMPTY = (pytest.ExitCode.OK, pytest.ExitCode.NO_TESTS_COLLECTED)


def _is_controller(config: pytest.Config) -> bool:
    """Return whether *config* is an xdist controller's, which runs no test."""
    return config.pluginmanager.get_plugin("dsession") is not None


def _is_worker(config: pytest.Config) -> bool:
    """Return whether *config* is an xdist worker's, which sends an output."""
    return isinstance(getattr(config, "workeroutput", None), dict)


def _hold(config: pytest.Config, where: str) -> None:
    """Move what the refusal log holds into what the guard holds, *where*.

    An xdist worker also writes it to its file at once (see
    :func:`_write_ahead`).
    """
    refused = home_write_guard.drain_refusals()
    if refused:
        held = config.stash.setdefault(_HELD, [])
        held.append((where, tuple(str(error) for error in refused)))
        if _is_worker(config):
            _write_ahead(config, held)


def _write_ahead(
    config: pytest.Config, held: Sequence[tuple[str, tuple[str, ...]]]
) -> None:
    """Append to this xdist worker's file what it holds and has not written.

    The worker hands what it holds to the controller only at its session finish
    (:meth:`RealHomeGuard.pytest_sessionfinish`). Until then a refusal it held
    at the session start, during collection, between two tests or after its
    last test is in this process alone, and a worker that crashed or was
    stopped before that hand-off would lose it: xdist reports such a worker
    down, and fails a test for it only when one was running on it. So would a
    worker whose session finish a wrapper stopped before the hand-off. Written
    to the file as it is held, the refusal reaches the controller, which reads
    the file once the worker has ended (:func:`_take_late`). A line written
    before the hand-off is a copy of what the hand-off sends, and the
    controller skips it when ``pytest_testnodedown`` took that hand-off from
    the worker's output, so nothing is reported twice. After the hand-off the
    file is the only way to the controller. A write that fails is tried again
    with the next refusal and when the worker reports what it holds
    (:func:`_report_held`).
    """
    written = config.stash.get(_IN_THE_FILE, 0)
    if _sent_late(config, held[written:]) is None:
        config.stash[_IN_THE_FILE] = len(held)


def _hold_before_the_test(item: pytest.Item) -> None:
    """Hold what was logged since the test before *item*, or since collection.

    It runs when *item*'s setup starts, before any of its fixtures is set up
    and before pytest sets ``PYTEST_CURRENT_TEST`` for it, so the refusal log
    then holds only refusals made outside any test: after the teardown report
    of the test before, in a ``pytest_runtest_logreport`` or
    ``pytest_runtest_logfinish`` hook or a ``pytest_runtest_protocol`` wrapper,
    or before this test's setup, in a ``pytest_runtest_logstart`` hook. For
    the first test of a session that is one since the test loop wrapper held
    the log (:meth:`RealHomeGuard.pytest_runtestloop`), such as one from a
    plain ``pytest_runtestloop`` implementation, which runs before pytest's
    own. ``_report_real_home_refusals`` would otherwise fail *item* for it, as
    made during the test.
    """
    config = item.config
    first = not config.stash.get(_A_TEST_STARTED, False)
    config.stash[_A_TEST_STARTED] = True
    where = (
        _BEFORE_THE_FIRST_TEST
        if first
        else f"{_BETWEEN_TWO_TESTS}, before {item.nodeid}"
    )
    _hold(config, where)


def _report_held(
    config: pytest.Config,
    session: pytest.Session | None,
    *,
    to_the_controller: bool = False,
) -> None:
    """Report every refusal the guard holds, and fail the run.

    The report goes to the terminal, on a line of its own (xdist leaves the
    progress line open), or to ``stderr`` when there is no terminal reporter.
    An xdist worker's terminal output is discarded and the controller does not
    use its exit code, so a worker sends the refusals to the controller
    instead: with *to_the_controller* in ``config.workeroutput``, which xdist
    sends, with a copy in the file the controller gave it, and after that in
    that file alone (:func:`_sent_late`). The worker writes each refusal to
    the file when it holds it (:func:`_write_ahead`), so here it writes only
    what did not reach the file then. A worker that has no such file, or
    cannot write to it, writes the refusals it held for that file alone to
    ``stderr``, with why it could not send them; one whose copy beside the
    hand-off fails writes why to ``stderr``. No try follows that write,
    so what part of it reached the file stays there, and the controller
    fails the run on it, as it does on a file the write left empty; a
    later write starts on a line of its own after it. The exit status of
    *session* becomes "tests failed" when it was "OK" or "no tests
    collected", which some jobs accept as a pass.
    """
    held = config.stash.get(_HELD, [])
    if not held:
        return
    reports = [*held]
    held.clear()
    # How many of them the worker wrote to its file as it held them.
    written = config.stash.get(_IN_THE_FILE, 0)
    config.stash[_IN_THE_FILE] = 0
    output = getattr(config, "workeroutput", None)
    worker = isinstance(output, dict)  # an xdist worker
    if worker and to_the_controller:
        output.setdefault(_TO_THE_CONTROLLER, []).extend(reports)
        # The file holds a copy, for a controller whose test loop ends before
        # it takes the output or a worker that ends before xdist sends it;
        # the controller skips the copy otherwise (see _take_late).
        unsent = _sent_late(config, reports[written:])
        if unsent is not None and _is_empty(config):
            # Opening the file to append created it, or an earlier write
            # did, and no byte reached it: the controller skips it only
            # when it takes this output, which brings every refusal.
            output[_COPY_LEFT_EMPTY] = True
        if unsent is not None:
            name = getattr(config, "workerinput", {}).get("workerid", "?")
            sys.stderr.write(
                f"In xdist worker {name}, the guard handed its refusals to the "
                f"controller, but could not write their copy: {unsent}. The "
                "controller gets them only when the worker sends its output.\n"
            )
        return
    if worker:
        reports = reports[written:]
    unsent = _sent_late(config, reports, last_try=True) if worker else None
    if worker and unsent is None:
        return
    name = getattr(config, "workerinput", {}).get("workerid", "?")
    prefix = f"in xdist worker {name}, " if worker else ""
    message = "\n".join(
        _outside_any_test(each, prefix + where) for where, each in reports
    )
    reporter = config.pluginmanager.get_plugin("terminalreporter")
    if worker:
        when = (
            "after it handed its refusals to the controller, once every plain "
            "session-finish hook had run"
            if config.stash.get(_HANDED_OFF, False)
            else "before it handed its refusals to the controller, which it "
            "does at its session finish"
        )
        named = getattr(config, "workerinput", {}).get(_LATE_TO_THE_CONTROLLER)
        if not named:
            outcome = "The run does not fail on it."
        elif output.get(_COPY_LEFT_EMPTY, False):
            outcome = (
                "The run fails on it when part of it reached that file. The "
                "copy beside the hand-off left the file empty, and a "
                "controller that takes the worker's output skips the file "
                "while it stays empty."
            )
        else:
            outcome = (
                "The run fails on it only when part of it reached that file, "
                "or when the file is left empty."
            )
        sys.stderr.write(
            f"{message}\nThe worker found it {when}, and could not send it to "
            f"the controller: {unsent}. {outcome}\n"
        )
    elif reporter is not None:
        reporter.write_line(f"\n{message}", red=True)
    else:
        sys.stderr.write(message + "\n")
    if not worker:
        config.stash[_REPORTED] = True
    _fail_the_run(session)


def _fail_the_run(session: pytest.Session | None) -> None:
    """Turn the exit status "OK" or "no tests collected" into "tests failed".

    Some jobs accept either as a pass. So is a status the system cuts to one
    of them (see :func:`_a_passing_code`): ``pytest.exit(returncode=256)``
    ends a POSIX process with 0. Any other status is kept.
    """
    if session is not None and _a_passing_code(session.exitstatus):
        session.exitstatus = pytest.ExitCode.TESTS_FAILED


@contextlib.contextmanager
def _a_passing_exit_fails(config: pytest.Config) -> Iterator[None]:
    """Raise ``SystemExit(1)`` in place of a passing one once the run failed.

    pytest catches no ``SystemExit`` around ``pytest_sessionfinish`` or
    ``pytest_unconfigure``, so a hook that calls ``sys.exit(0)`` there, or
    raises ``SystemExit`` with the code ``None``, ends the process with 0
    whatever the session's exit status says. Once the guard has reported a
    refusal in the session, such an exit becomes ``SystemExit(1)``, as the
    status becomes "tests failed" again after ``pytest.exit(returncode=0)``
    (see :meth:`RealHomeGuard.pytest_unconfigure`); so does
    ``sys.exit(5)``, as ``pytest.exit(returncode=5)`` does (see
    :func:`_a_passing_code`). Any other code is the hook's own, and stays.
    """
    try:
        yield
    except SystemExit as error:
        if _a_passing_code(error.code) and config.stash.get(_REPORTED, False):
            raise SystemExit(pytest.ExitCode.TESTS_FAILED) from error
        raise


def _a_passing_code(code: object) -> bool:
    """Return whether a ``SystemExit`` with *code* ends the run as a pass.

    ``None`` exits 0, and so do 0 and ``False``; 5 is "no tests collected",
    which some jobs accept as a pass (see :func:`_fail_the_run`). A POSIX
    system keeps only the low 8 bits of an exit code, so 256 or -256 exits
    0 there and 261 exits 5: an int code counts by its remainder modulo
    256, on Windows too, where such a code fails the run either way. Any
    other code, a message included (which exits 1), is not a pass.
    """
    if code is None:
        return True
    return isinstance(code, int) and code % 256 in _PASSED_OR_EMPTY


def _late_folder(config: pytest.Config) -> str | None:
    """Return the folder an xdist controller reads its workers' files from.

    The controller makes it once per session, in the temporary folder, with
    ``tempfile.mkdtemp``, which never takes a name that exists: a folder an
    earlier run left behind (one stopped before it removed its own) is never
    read, also when that run used the same ``--basetemp``. ``None`` when it
    cannot be made, when Python finds no usable temporary folder (``tempfile``
    raises ``FileNotFoundError`` then), or when Apothem would refuse a write
    into the temporary folder (``home_write_guard.would_refuse``): the guard
    never writes into a protected folder of a real home. The workers then
    write what they find after the hand-off to ``stderr`` (see
    :func:`_report_held`).

    It is not made in pytest's own folder for the session (its basetemp),
    whose retention would remove a folder that a killed controller left.
    Without ``--basetemp``, pytest's own ``pytest_sessionfinish`` removes
    the basetemp when ``tmp_path_retention_policy`` is ``none``, or
    ``failed`` and the run passed, and under ``all`` removes its lock, after
    which another pytest run's cleanup may remove it. The controller reads
    the files later, in ``pytest_unconfigure``, so the refusals in them
    would be lost. Only a basetemp given with ``--basetemp`` stays until the
    next run that names it, and a run need not name one: the suite's
    top-level runs (the ``addopts`` in ``pyproject.toml``) name none, though
    the pytester sessions of its own tests do.
    """
    if _LATE_FOLDER not in config.stash:
        folder = None
        with contextlib.suppress(OSError):
            parent = tempfile.gettempdir()
            if not home_write_guard.would_refuse(parent):
                folder = tempfile.mkdtemp(prefix="apothem-late-refusals-", dir=parent)
        config.stash[_LATE_FOLDER] = folder
    return config.stash[_LATE_FOLDER]


def _sent_late(
    config: pytest.Config,
    reports: Sequence[tuple[str, tuple[str, ...]]],
    *,
    last_try: bool = False,
) -> str | None:
    """Append *reports* to the file the xdist controller gave this worker.

    The file is the one :meth:`RealHomeGuard.pytest_configure_node` named in
    ``config.workerinput``. Each report is one JSON line, all of them written
    in one call, and no other process writes to the file. Each line says
    whether the worker had handed its refusals to the controller by then
    (``handed_off``): a worker whose session stopped before its session
    finish never did. Returns ``None`` once they are written, or why they
    were not: the controller named no file (see :func:`_late_folder`), or
    the file could not be written (the controller's folder is gone, say),
    with the system's reason. What part of a failed write reached the file
    is cut off again, so the next try writes each report once; when that
    cut fails too, the controller may read a report twice: the part cut off
    as a refusal of its own, with no place named, and the next try's line,
    which starts on a line of its own, as the full report. With *last_try*
    no try follows, so that part stays: the controller holds a line cut
    off part way as a refusal of its own, and fails the run on it, as it
    does on a file the write created and left empty. A later write starts
    on a new line after such a line. With no report it opens
    no file: the worker creates its file only to write a refusal.

    Opening the file to append creates it, so a write that fails before any
    byte lands (a full disk, say) leaves it empty. That file stays: the
    controller holds it as a refusal of its own, which is the only sign of
    the refusal when the worker crashes before it sends its output. Only
    for the copy written beside the hand-off does the worker say so in that
    output (see :func:`_report_held`), and the controller skips the empty
    file when it takes the output, which brings every refusal it was
    opened for.
    """
    if not reports:
        return None
    workerinput = getattr(config, "workerinput", None)
    path = (
        workerinput.get(_LATE_TO_THE_CONTROLLER)
        if isinstance(workerinput, dict)
        else None
    )
    if not isinstance(path, str) or not path:
        return (
            "the controller named no file for it (it could not make a folder "
            "for the files, or Apothem would refuse a write there)"
        )
    handed_off = config.stash.get(_HANDED_OFF, False)
    lines = "".join(
        _dumps({"where": where, "messages": list(messages), "handed_off": handed_off})
        + "\n"
        for where, messages in reports
    )
    data = lines.encode("utf-8")
    start: int | None = None
    try:
        with Path(path).open("a+b") as stream:
            start = stream.seek(0, os.SEEK_END)
            # A line an earlier last try cut off part way ends with no
            # newline; the new lines start on a line of their own.
            if start:
                stream.seek(start - 1)
                if stream.read(1) != b"\n":
                    data = b"\n" + data
            stream.write(data)
    except OSError as error:
        # Part of the text may have reached the file (a full disk, say). When
        # the caller writes the same reports again later, cut the file back
        # to where it ended: a worker that crashes before it hands them over
        # would otherwise have each one read twice, plus a cut-off line. On
        # the last try that part is the only record the controller gets.
        if start is not None and not last_try:
            with contextlib.suppress(OSError):
                os.truncate(path, start)
        return f"writing {path} failed: {error.strerror or error}"
    return None


def _is_empty(config: pytest.Config) -> bool:
    """Return whether this worker's file exists and holds no byte.

    ``False`` when the controller named no file, or on any error.
    """
    workerinput = getattr(config, "workerinput", None)
    path = (
        workerinput.get(_LATE_TO_THE_CONTROLLER)
        if isinstance(workerinput, dict)
        else None
    )
    if not isinstance(path, str) or not path:
        return False
    try:
        return Path(path).stat().st_size == 0
    except OSError:
        return False


def _take_late(config: pytest.Config) -> None:
    """Hold what each xdist worker wrote to its file, and remove the folder.

    It first waits for every worker to end (:func:`_end_the_workers`), so no
    worker writes to its file after it was read. Each refusal is named for its
    worker, for whether the worker had handed its refusals to the controller by
    then, and for where the worker found it (``in xdist worker gw0, after it
    handed its refusals to the controller, after the session finished``; see
    :func:`_late_report`). A line the worker wrote before that hand-off is a
    copy of what it handed over: it is skipped when ``pytest_testnodedown``
    took that hand-off from the worker's output, and held when it did not (the
    worker crashed or was stopped first, or a session-finish wrapper stopped
    its session finish before the hand-off, say). A worker that found nothing
    wrote no file. A file that cannot be read, or that holds no line, is held
    as a refusal of its own, so the run fails: the worker creates its file only
    to write a refusal it found, and one stopped after it created the file and
    before the text reached it leaves the file empty. An empty file is
    skipped only when ``pytest_testnodedown`` took the worker's output and
    that output says the copy written beside the hand-off failed and left
    the file empty: the output holds every refusal the file was opened for.
    Nothing happens outside an xdist controller, which alone names files.
    """
    files = config.stash.get(_LATE_FILES, {})
    if files:
        _end_the_workers(config)
    held = config.stash.setdefault(_HELD, [])
    taken = config.stash.get(_TAKEN, set())
    left_empty = config.stash.get(_LEFT_EMPTY, set())
    for path, worker in files.items():
        named = f"in xdist worker {worker}"
        try:
            text = Path(path).read_text(encoding="utf-8")
        except FileNotFoundError:
            continue
        except (OSError, ValueError) as error:
            held.append((named, (f"the guard could not read {path}: {error}",)))
            continue
        lines = [line for line in text.splitlines() if line.strip()]
        if not lines and worker in left_empty:
            continue  # the output it sent holds what the file was opened for
        if not lines:
            empty = (
                f"{path} is empty: the worker creates it only to write a "
                "refusal it found, so it was stopped while it wrote, say"
            )
            held.append((named, (empty,)))
        for line in lines:
            report, handed_off = _late_report(line, named)
            # A line written before the hand-off, of a worker whose output
            # pytest_testnodedown took, is a copy of what that output held.
            if handed_off is False and worker in taken:
                continue
            held.append(report)
    files.clear()
    folder = config.stash.get(_LATE_FOLDER, None)
    if folder is not None:
        _rmtree(folder, ignore_errors=True)
        config.stash[_LATE_FOLDER] = None


def _end_the_workers(config: pytest.Config) -> None:
    """Tell every xdist worker still running to exit, and wait for it to end.

    xdist's own ``pytest_sessionfinish`` in the controller does this, but it
    is a plain implementation, and pluggy calls none after one that raises:
    a plain ``pytest_sessionfinish`` hook that pluggy calls before it (a
    ``tryfirst`` one, or one registered after xdist's) and ends the run with
    ``pytest.exit`` leaves the workers running. ``teardown_nodes`` waits for
    each worker process to end, as xdist's hook does, and returns at once
    when they all have. An error here is dropped, and the files are read
    all the same.
    """
    session = config.pluginmanager.get_plugin("dsession")
    nodes = getattr(session, "nodemanager", None)
    if nodes is not None:
        with contextlib.suppress(Exception):
            nodes.teardown_nodes()


def _late_report(
    line: str, named: str
) -> tuple[tuple[str, tuple[str, ...]], bool | None]:
    """Return ``(where, messages)`` for one line a worker wrote, and its flag.

    *named* is the worker (``in xdist worker gw0``). The place adds ``after
    it handed its refusals to the controller`` only when the line says the
    worker had (``handed_off``; see :func:`_sent_late`), then where the
    worker found the refusal. The flag is that ``handed_off`` value. A line
    that cannot be read as one (a worker stopped while it wrote it) is
    returned whole as the message, under *named* alone, with no flag.
    """
    try:
        found = _loads(line)
        where = str(found["where"])
        messages = tuple(str(message) for message in found["messages"])
        handed_off = found.get("handed_off") is True
    except (ValueError, KeyError, TypeError, AttributeError):
        return (named, (line,)), None
    parts = [named, *([_AFTER_THE_HAND_OFF] if handed_off else []), where]
    return (", ".join(part for part in parts if part), messages), handed_off


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
