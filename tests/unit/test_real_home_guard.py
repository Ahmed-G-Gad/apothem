# SPDX-License-Identifier: MIT

"""The real-home guard in ``tests/conftest.py`` stops a test before it can write.

Importing ``tests/conftest.py`` registers ``real_home_guard`` with the pytest
session doing the import. Its setup hook fails a test, before any of its
fixtures is set up, when the isolation fixtures of ``tests/conftest.py`` do not
apply to it. Its call hook fails a test, before its body runs, when its
environment points Apothem at the home the pytest process started with or at a
real folder in it. Its report hook keeps such a failure failed when the test is
marked ``xfail``. Its session hooks fail the run on a refusal of a write into a
protected home that a caller absorbed outside any test, named for where it
happened. ``__all__`` makes a star import of ``tests/conftest.py`` carry the
isolation fixtures and ``_report_real_home_refusals``, which a star import
would skip otherwise because their names start with ``_``.

The ``test_*`` functions run in the suite, where ``tests/conftest.py`` is
loaded as a conftest. They check that the guard is registered once, with its
hooks ordered as intended (the session hooks that read the refusal log
included), that ``tests/conftest.py`` holds none of the hooks the guard
object implements, and that the call hook finds nothing for a suite test,
and they check the guard's comparison on text: a folder below a real home
is allowed, but not the home or a real folder in it.

Showing the guard stop a test takes a pytest session of its own, because the
call hook compares with the home its session started with.
``test_the_pytester_cases_pass`` starts ``python -m pytest -p pytester`` on a
copy of this file, and that session collects only the ``case_*`` functions, so
the ``pytester`` plugin stays out of the suite's own session. Each case points
``HOME``, ``USERPROFILE`` and ``LOCALAPPDATA`` at fresh folders, the fake real
ones, writes a probe folder with pytester and runs it in-process, or, where
the probe session ends with a ``SystemExit``, in a child process that inherits
them. The probe session imports ``tests/conftest.py`` anew (one case imports
it just before, in a thread, with the fake real home already set), so the fake
real home is its real home, and the developer's own home is never named. The
probe tests only read the home; the first line of each writes a sentinel file
into the probe folder, never into a home, so a missing sentinel proves the body
never started. The probe fixtures that stand for a fixture writing during setup
write their sentinels there too. One probe test uses no fixture and the other
uses ``tmp_path``.

The other cases protect the fake real home with
``apothem.lib.home_write_guard.also_protect_home`` and absorb a refusal of a
write into it. Three absorb it in the test body or a fixture's teardown, with
and without an ``xfail`` mark, and with the mark when the probe conftest takes
the refusal fixture from a second copy of ``tests/conftest.py``, loaded under
another module name. Each test errors at teardown. The rest absorb it outside
any test: while a test module is imported, which fails that module's
collection, and in a probe conftest's hook, which leaves the tests to run and
pass and fails the run: at the session start (also in a run that collects no
test), in a ``pytest_collection`` or ``pytest_collection_modifyitems`` hook, in
a ``pytest_collection_finish`` hook while a path that does not exist stops the
collection, between two collect reports (a ``pytest_itemcollected`` hook, and
the ``pytest_collectreport`` hook of the session's own report), in a
``pytest_runtestloop`` wrapper before it yields and in a plain
``pytest_runtestloop`` hook (also with ``--co`` and with every test deselected,
when no test runs), between two tests (a ``pytest_runtest_logreport`` hook for
a teardown report), in a ``pytest_sessionfinish`` hook (also one that then
calls ``pytest.exit(returncode=0)``, as a ``pytest_configure`` hook does before
any session starts, and one that calls ``sys.exit(0)``, with and without xdist,
or ``sys.exit(5)``, as a ``pytest_terminal_summary`` hook does with a bare
``sys.exit()``, as a ``pytest_unconfigure`` hook does too, and so does a
``sys.exit(0)`` after the guard's other hooks: in a ``tryfirst`` session-finish
or unconfigure wrapper pytest registered after the guard, in a cleanup, and in
an xdist controller's session-finish hook before it read its workers' files,
also after a hook that ended the session finish with ``sys.exit`` or raised;
these probe sessions run in a child process) or after a session-finish wrapper
yields, in ``pytest_terminal_summary``, in ``pytest_unconfigure`` (with ``-p
no:xdist``), and under xdist (``-n 2``) at the session start and in a worker's
session finish (reported once, and also when a controller hook ended its test
loop with ``pytest.exit`` before it took the worker's output), also in a
``trylast`` hook of a conftest that pytest finds during collection, and after a
worker handed its refusals to the controller: in its
``pytest_terminal_summary``, in its ``pytest_unconfigure`` and after its own
``tryfirst`` session-finish wrapper yields, which the worker writes to a file
the controller reads and removes, also once a controller hook ended the run
with ``pytest.exit`` before xdist ended the workers (a later run with the same
``--basetemp`` and no refusal passes and reads none of the files an earlier run
left in its folder, and no such file is made in a protected folder), a worker
whose session ends at its start, which handed nothing over, is not named as if
it had, a worker that ends with ``os._exit(0)`` in its session finish, before
it hands anything over, still fails the run with what it absorbed between two
tests and after its last test (a worker that hands the same over has each
reported once), and so does one whose session-finish wrapper raises or calls
``pytest.exit`` before its ``yield``, which leaves the guard's hand-off out of
its output, and an empty file a worker left, a line it cut short and a file the
controller cannot read each fail the run; a worker that stops on Ctrl-C has its
refusal reported once, and one the controller absorbs while its workers run the
tests is named for the run. Each names where the refusal happened. A session
that absorbs nothing exits 0, with and without xdist. The guard refuses before
any write, so nothing lands in a home.
"""

from __future__ import annotations

import errno
import importlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import IO, TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from pluggy import HookImpl

#: Hands the repo root to the pytester session, which runs from a copy of this file.
_REPO_VARIABLE = "APOTHEM_REAL_HOME_GUARD_REPO"
_REPO_ROOT = Path(os.environ.get(_REPO_VARIABLE) or Path(__file__).resolve().parents[2])
_CONFTEST = _REPO_ROOT / "tests" / "conftest.py"
#: The guard's public names, which a star import carries.
_GUARD_NAMES = {
    "REAL_HOME_GUARD_PLUGIN",
    "RealHomeGuard",
    "RealHomeGuardFailure",
    "pytest_register_real_home_guard",
    "real_home_guard",
}
#: The public names a star import of ``tests/conftest.py`` carried before it
#: had an ``__all__``, less ``pytest_real_home_guard``, which became the plugin
#: object ``real_home_guard``.
_PUBLIC_BEFORE_ALL = {
    "Callable",
    "DEFAULT_PROFILE_PATH",
    "Generator",
    "Iterable",
    "Iterator",
    "Path",
    "annotations",
    "contextlib",
    "install_driver",
    "install_driver_types",
    "install_ledger",
    "os",
    "propagation",
    "pytest",
    "resolve_shared_data_home",
    "sys",
}
_ISOLATION = (
    "_isolate_session_home",
    "_isolate_user_home",
    "_isolate_install_ledger",
    "_isolate_backup_root",
)
#: Every name ``__all__`` lists that starts with ``_``, which a star import
#: carries only because it is listed: the five isolation fixtures and the
#: fixture that fails a test after which a refusal was absorbed.
_UNDERSCORE_EXPORTS = {
    *_ISOLATION,
    "_isolate_hook_state",
    "_report_real_home_refusals",
}
#: The functions the pytester session collects, and the suite does not.
_CASE_PREFIX = "case_"

# --- The probe folder the cases build ----------------------------------------

#: Puts the repo root on ``sys.path`` for the import that follows it.
_REPO_ON_PATH = f"""\
import os
import sys

sys.path.insert(0, os.environ[{_REPO_VARIABLE!r}])
"""

#: The import that used to skip every isolation fixture.
_STAR_IMPORT = (
    _REPO_ON_PATH
    + """
from tests.conftest import *  # noqa: E402, F403
"""
)

#: Two autouse fixtures that stand for a fixture writing while it is set up.
_SETUP_WRITERS = """
from pathlib import Path

import pytest

HERE = Path(__file__).parent


@pytest.fixture(scope="session", autouse=True)
def session_writer():
    (HERE / "fixture-ran-session").write_bytes(b"")


@pytest.fixture(autouse=True)
def function_writer():
    (HERE / "fixture-ran-function").write_bytes(b"")
"""
_FIXTURE_SENTINELS = ("fixture-ran-session", "fixture-ran-function")

#: Imports one plain name and no isolation fixture, then writes during setup.
_NO_ISOLATION = (
    _REPO_ON_PATH
    + """
from tests.conftest import install_ledger  # noqa: E402, F401
"""
    + _SETUP_WRITERS
)

#: Imports two isolation fixtures by name and not the other two, nor the guard.
_SOME_ISOLATION = (
    _REPO_ON_PATH
    + """
from tests.conftest import _isolate_install_ledger, _isolate_user_home  # noqa: E402, F401
"""
    + _SETUP_WRITERS
)
_NOT_IMPORTED = ("_isolate_session_home", "_isolate_backup_root")

#: Removes every name of the guard that the star import bound.
_GUARD_NAMES_DELETED = """

del REAL_HOME_GUARD_PLUGIN, RealHomeGuard, RealHomeGuardFailure
del pytest_register_real_home_guard, real_home_guard
"""

#: A call wrapper registered after the guard that puts the real home back.
_REAL_HOME_IN_A_LATER_WRAPPER = """

REAL_HOME = os.environ["HOME"]


@pytest.hookimpl(wrapper=True, trylast=True)
def pytest_runtest_call(item):
    saved = {name: os.environ[name] for name in ("HOME", "USERPROFILE")}
    os.environ.update(HOME=REAL_HOME, USERPROFILE=REAL_HOME)
    try:
        return (yield)
    finally:
        os.environ.update(saved)
"""

#: Puts back the two roots tests/conftest.py bound from the real home at import.
_REAL_ROOTS_AGAIN = """

STATE_ROOT = install_ledger.STATE_ROOT
BACKUP_ROOT = install_driver.BACKUP_ROOT


@pytest.fixture(autouse=True)
def real_roots_again(_isolate_install_ledger, _isolate_backup_root, monkeypatch):
    monkeypatch.setattr(install_ledger, "STATE_ROOT", STATE_ROOT)
    monkeypatch.setattr(install_driver, "BACKUP_ROOT", BACKUP_ROOT)
"""

#: A session-scoped autouse fixture whose name sorts before _isolate_session_home.
_EARLY_SESSION_WRITER = """


@pytest.fixture(scope="session", autouse=True)
def _install_writer():
    (Path(__file__).parent / "fixture-ran-session").write_bytes(b"")
"""

#: The same fixture, requesting the session home, which pytest then sets up first.
_EARLY_SESSION_WRITER_ISOLATED = _EARLY_SESSION_WRITER.replace(
    "def _install_writer():", "def _install_writer(_isolate_session_home):"
)

#: A fixture of the same name in place of the session home of tests/conftest.py.
_SESSION_HOME_REPLACED = """


@pytest.fixture(scope="session", autouse=True)
def _isolate_session_home():
    yield
"""

#: A ``pytest_pyfunc_call`` wrapper that puts the real home back around the call.
_REAL_HOME_IN_A_FUNCTION_WRAPPER = """

REAL_HOME = os.environ["HOME"]


@pytest.hookimpl(wrapper=True)
def pytest_pyfunc_call(pyfuncitem):
    saved = {name: os.environ[name] for name in ("HOME", "USERPROFILE")}
    os.environ.update(HOME=REAL_HOME, USERPROFILE=REAL_HOME)
    try:
        return (yield)
    finally:
        os.environ.update(saved)
"""

#: Hands the real home to the install manifest through its own seam.
_REAL_MANIFEST_HOME = """

REAL_HOME = os.environ["HOME"]


@pytest.fixture(autouse=True)
def manifest_home(monkeypatch):
    monkeypatch.setattr(propagation, "USER_HOME", Path(REAL_HOME))
"""

#: With tests/conftest.py loaded as a plugin, puts the real home back after it.
_REAL_HOME_AGAIN = """
import os

import pytest

REAL_HOME = os.environ["HOME"]


@pytest.fixture(autouse=True)
def real_home_again(_isolate_user_home, monkeypatch):
    for name in ("HOME", "USERPROFILE"):
        monkeypatch.setenv(name, REAL_HOME)
"""


def _variable_again(name: str, value: str, *, clear_override: bool = False) -> str:
    """Return a fixture that sets *name* to *value* after the isolation fixtures."""
    clear = (
        '    monkeypatch.delenv("APOTHEM_HOOK_STATE_DIR", raising=False)\n'
        if clear_override
        else ""
    )
    return f"""

@pytest.fixture(autouse=True)
def variable_again(
    _isolate_session_home, _isolate_user_home, _isolate_hook_state, monkeypatch
):
    monkeypatch.setenv({name!r}, {value!r})
{clear}"""


#: Two probe tests that only read the home, after a sentinel in the probe folder.
_PROBES = """
import os
from pathlib import Path

HERE = Path(__file__).parent


def test_fixture_free():
    (HERE / "body-ran-fixture-free").write_bytes(b"")
    assert Path.home()
    assert os.environ.get("HOME") or os.environ.get("USERPROFILE")


def test_with_tmp_path(tmp_path):
    (HERE / "body-ran-with-tmp-path").write_bytes(b"")
    assert tmp_path.is_dir()
    assert Path.home()
"""
_SENTINELS = ("body-ran-fixture-free", "body-ran-with-tmp-path")
_PROBE_TESTS = ("test_fixture_free", "test_with_tmp_path")

#: The same two probe tests, each marked ``xfail``, which absorbs any failure.
_XFAIL_PROBES = "import pytest\n" + _PROBES.replace(
    "\ndef test_", '\n@pytest.mark.xfail(reason="probe")\ndef test_'
)

#: Four probe tests that each absorb a refusal of a write into a protected home:
#: in the test body, in a function fixture's teardown, in a function fixture's
#: teardown beside another fixture whose teardown fails, and in a module
#: fixture's teardown. ``{home}`` is the protected home and ``{marker}`` a mark
#: line or nothing. Nothing is written: the guard refuses before any write.
_ABSORBING_PROBES = """
import contextlib

import pytest

from apothem.lib import home_write_guard

HOME = {home!r}
home_write_guard.also_protect_home(HOME)


def _absorb():
    with contextlib.suppress(OSError):
        home_write_guard.refuse_real_home_write(
            HOME + "/.apothem/probe.txt", operation="write"
        )


@pytest.fixture
def absorbs_at_teardown():
    yield
    _absorb()


@pytest.fixture(scope="module")
def absorbs_at_module_teardown():
    yield
    _absorb()


@pytest.fixture
def fails_at_teardown():
    yield
    raise ValueError("another fixture's teardown failed")

{marker}
def test_absorbs_in_its_body():
    _absorb()

{marker}
def test_absorbs_in_a_fixture_teardown(absorbs_at_teardown):
    pass

{marker}
def test_absorbs_beside_another_failing_teardown(
    absorbs_at_teardown, fails_at_teardown
):
    pass

{marker}
def test_absorbs_in_a_module_fixture_teardown(absorbs_at_module_teardown):
    pass
"""
#: The probe tests in the order they run. The module fixture's teardown runs
#: with the last test's, so its test stays last. The third test's teardown
#: fails twice at once, which pytest raises as an exception group.
_ABSORBING_TESTS = (
    "test_absorbs_in_its_body",
    "test_absorbs_in_a_fixture_teardown",
    "test_absorbs_beside_another_failing_teardown",
    "test_absorbs_in_a_module_fixture_teardown",
)

#: After the star import, takes ``_report_real_home_refusals`` from a second
#: copy of tests/conftest.py, loaded under another module name. A run of
#: ``python -m pytest`` from ``tests/`` loads the file as the conftest
#: ``conftest``, and makes such a copy when a conftest there imports from
#: ``tests.conftest``, which imports the file again under that name, or with
#: ``-p tests.conftest`` and the repository root on ``PYTHONPATH``, which
#: imports it as ``tests.conftest`` before pytest loads the conftest. The
#: copy registers no second guard, and its fixture raises its own
#: ``RealHomeGuardFailure``. The probe stops if that class is the first
#: copy's, and the session at its start if the guard pytest registered is
#: not the first copy's: with the guard and the fixture from one copy, the
#: case would pass without the guard meeting a second copy's failure.
_SECOND_COPYS_REFUSAL_FIXTURE = f"""

import importlib.util

_SPEC = importlib.util.spec_from_file_location(
    "a_second_copy_of_tests_conftest",
    os.path.join(os.environ[{_REPO_VARIABLE!r}], "tests", "conftest.py"),
)
_SECOND = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_SECOND)
assert _SECOND.RealHomeGuardFailure is not RealHomeGuardFailure
_report_real_home_refusals = _SECOND._report_real_home_refusals


def pytest_sessionstart(session):
    guard = session.config.pluginmanager.get_plugin(REAL_HOME_GUARD_PLUGIN)
    assert guard is real_home_guard, "the guard is not the first copy's"
"""

#: The names the call guard gives, as its findings spell them.
_HOME_NAMES = {"HOME", "USERPROFILE", "Path.home()", "propagation.user_home()"}
_FOLDER_NAMES = {
    "the data home",
    "the support folder ~/.config/apothem",
    "the default profile's folder",
}
_ROOT_NAMES = {
    "the install ledger root (install_ledger.STATE_ROOT)",
    "the backup root (install_driver.BACKUP_ROOT)",
}

# --- In the suite -------------------------------------------------------------


def _suite_conftest(config: pytest.Config) -> ModuleType:
    """Return ``tests/conftest.py`` as pytest registered it in this session."""
    for plugin in config.pluginmanager.get_plugins():
        location = getattr(plugin, "__file__", None)
        if location and Path(location).resolve() == _CONFTEST.resolve():
            return plugin
    raise AssertionError(f"pytest has not registered {_CONFTEST}")


def _call_order(request: pytest.FixtureRequest, hook: str) -> list[HookImpl]:
    """Return the implementations of *hook* in the order pytest calls them."""
    return list(reversed(getattr(request.node.ihook, hook).get_hookimpls()))


def _guard_impl(request: pytest.FixtureRequest, hook: str) -> HookImpl:
    guard = request.config.pluginmanager.get_plugin("apothem-real-home-guard")
    impls = [impl for impl in _call_order(request, hook) if impl.plugin is guard]
    assert len(impls) == 1, impls
    return impls[0]


def _implemented_hooks(manager: pytest.PytestPluginManager, plugin: object) -> set[str]:
    """Return every hook *plugin* implements, read from its attributes.

    pytest's own rule decides which attribute is a hook implementation (its
    name starts with ``pytest_`` and it is a function or a method), and each
    one counts under the hook its ``specname`` names, if it has one.
    """
    hooks: set[str] = set()
    for name in dir(plugin):
        opts = manager.parse_hookimpl_opts(plugin, name)
        if opts is not None:
            hooks.add(opts.get("specname") or name)
    return hooks


def _registered_hooks(manager: pytest.PytestPluginManager, plugin: object) -> set[str]:
    """Return every hook pytest registered *plugin* under."""
    return {caller.name for caller in manager.get_hookcallers(plugin) or ()}


def test_the_import_registers_one_guard_object(request: pytest.FixtureRequest) -> None:
    conftest = _suite_conftest(request.config)
    manager = request.config.pluginmanager
    guards = [
        plugin
        for plugin in manager.get_plugins()
        if type(plugin).__name__ == "RealHomeGuard"
    ]
    assert guards == [conftest.real_home_guard]
    assert manager.get_plugin(conftest.REAL_HOME_GUARD_PLUGIN) is guards[0]
    # The guard's hooks are read from the object, so one added to
    # RealHomeGuard is checked below with no list to update. They are the
    # hooks pytest registered the object under.
    hooks = _implemented_hooks(manager, guards[0])
    assert hooks, "the guard implements no hook"
    assert hooks == _registered_hooks(manager, guards[0])
    # The conftest module itself defines none of them at module level, and
    # pytest registered it under none of them (a function of another name
    # with that specname would count), so a star import of it registers
    # none of them a second time. The check goes by hook name only: a hook
    # of the conftest's own, such as the registrar (a pytest_configure
    # hook), fails it too once the guard implements a hook of that name.
    shared = {name for name in hooks if callable(vars(conftest).get(name))}
    shared |= _registered_hooks(manager, conftest) & hooks
    assert not shared, (
        f"tests/conftest.py implements the guard's hooks {sorted(shared)} at "
        "module level, so a star import registers them a second time; a hook "
        "of its own that shares a name with a guard hook needs an exception "
        "made here on purpose"
    )
    registrars = [
        impl
        for impl in request.config.hook.pytest_configure.get_hookimpls()
        if impl.plugin is conftest
    ]
    assert [impl.function.__name__ for impl in registrars] == [
        "pytest_register_real_home_guard"
    ]


def test_a_plain_script_that_imports_the_conftest_registers_nothing(
    tmp_path: Path,
) -> None:
    """Outside pytest the import finds no plugin manager and changes nothing.

    The import-time walk registers the guard only when a pytest session is on
    the stack (case ``a_conftest_that_imports_some_isolation_fixtures`` pins
    that it does then). A plain script gets ``None`` back, the import still
    succeeds, and nothing is written to the home it runs with.
    """
    home = tmp_path / "home"
    home.mkdir()
    script = (
        "import tests.conftest as conftest\n"
        "print(conftest._importing_plugin_manager() is None)\n"
    )
    env = {
        **os.environ,
        "HOME": str(home),
        "USERPROFILE": str(home),
        "PYTHONPATH": os.pathsep.join([str(_REPO_ROOT / "src"), str(_REPO_ROOT)]),
    }
    done = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=300,
        check=False,
    )

    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == "True", done.stdout + done.stderr
    assert list(home.iterdir()) == []


def test_the_setup_hook_runs_before_any_fixture_is_set_up(
    request: pytest.FixtureRequest,
) -> None:
    impl = _guard_impl(request, "pytest_runtest_setup")
    assert impl.tryfirst, "the guard has to run before the fixtures are set up"
    assert not impl.wrapper, "a tryfirst wrapper leaves pytest's own unentered"
    runner = request.config.pluginmanager.get_plugin("runner")
    order = [i.plugin for i in _call_order(request, "pytest_runtest_setup")]
    assert order.index(impl.plugin) < order.index(runner)


def _is_conftest(plugin: object) -> bool:
    return Path(getattr(plugin, "__file__", None) or "-").name == "conftest.py"


def test_the_call_hook_runs_after_every_wrapper_and_before_the_item_runs(
    request: pytest.FixtureRequest,
) -> None:
    impl = _guard_impl(request, "pytest_runtest_call")
    assert not impl.wrapper, "a wrapper registered later would nest inside it"
    assert not impl.hookwrapper
    assert not impl.tryfirst
    assert not impl.trylast, "a trylast plain hook runs after the test"
    order = _call_order(request, "pytest_runtest_call")
    runner = request.config.pluginmanager.get_plugin("runner")
    at = order.index(impl)
    assert [i.plugin for i in order[at + 1 :]].count(runner) == 1
    # A plain hook registered before the guard runs after it; a conftest's never
    # is. Another plugin's plain hook (pytest-cov's, say) may come either side.
    assert [i for i in order[at + 1 :] if _is_conftest(i.plugin)] == []


def test_the_function_hook_runs_right_before_the_function_is_called(
    request: pytest.FixtureRequest,
) -> None:
    """``Function.runtest`` calls ``pytest_pyfunc_call`` after every call hook."""
    impl = _guard_impl(request, "pytest_pyfunc_call")
    assert not impl.wrapper
    assert not impl.hookwrapper
    assert not impl.tryfirst
    assert not impl.trylast
    order = _call_order(request, "pytest_pyfunc_call")
    python = request.config.pluginmanager.get_plugin("python")
    after = order[order.index(impl) + 1 :]
    assert [i for i in after if i.plugin is python and i.trylast] != []
    assert [i for i in after if _is_conftest(i.plugin)] == []
    assert type(request.node).runtest is pytest.Function.runtest


def test_the_report_hook_wraps_every_other_report_hook(
    request: pytest.FixtureRequest,
) -> None:
    impl = _guard_impl(request, "pytest_runtest_makereport")
    assert impl.wrapper
    assert impl.tryfirst, "it has to finish after skipping changed the report"
    skipping = request.config.pluginmanager.get_plugin("skipping")
    order = [i.plugin for i in _call_order(request, "pytest_runtest_makereport")]
    assert order.index(impl.plugin) < order.index(skipping)


def test_the_session_hooks_read_the_log_after_what_they_follow(
    request: pytest.FixtureRequest,
) -> None:
    """Each hook that reads the refusal log outside a test finishes late enough."""
    guard = request.config.pluginmanager.get_plugin("apothem-real-home-guard")

    def guard_impls(hook: str) -> list[HookImpl]:
        return [i for i in _call_order(request, hook) if i.plugin is guard]

    for hook in (
        "pytest_sessionstart",
        "pytest_collection_finish",
        "pytest_unconfigure",
    ):
        (impl,) = guard_impls(hook)
        assert impl.wrapper, hook
        assert impl.tryfirst, f"{hook}: it has to finish after every other one"
    # On the object, like the others: at module level a star import would
    # register it twice, and a conftest that imports single names not at all.
    (collect,) = guard_impls("pytest_make_collect_report")
    assert collect.wrapper, "it reads the log before and after each report"
    (loop,) = guard_impls("pytest_runtestloop")
    assert loop.wrapper
    assert loop.trylast, "it has to start after every other wrapper"
    wrappers = [
        i
        for i in _call_order(request, "pytest_runtestloop")
        if i.wrapper or i.hookwrapper
    ]
    assert wrappers[-1] is loop
    after_the_summary, at_the_end = guard_impls("pytest_sessionfinish")
    assert after_the_summary.wrapper
    assert after_the_summary.tryfirst
    assert at_the_end.wrapper
    assert at_the_end.trylast, "it has to go on after every plain one"
    reporter = request.config.pluginmanager.get_plugin("terminalreporter")
    calls = _call_order(request, "pytest_sessionfinish")
    finish_wrappers = [i for i in calls if i.wrapper or i.hookwrapper]
    assert finish_wrappers[-1] is at_the_end
    (summary,) = [i for i in calls if i.plugin is reporter]
    assert summary.wrapper, "the summary is written after its yield"
    assert calls.index(after_the_summary) < calls.index(summary)
    (main,) = guard_impls("pytest_cmdline_main")
    assert main.wrapper
    assert main.tryfirst, "it has to see an exit after the guard's other wrappers"
    (worker_down,) = guard_impls("pytest_testnodedown")
    assert worker_down.optionalhook, "only xdist defines the hook"
    (worker_up,) = guard_impls("pytest_configure_node")
    assert worker_up.optionalhook, "only xdist defines the hook"
    assert not worker_up.wrapper


def test_a_star_import_carries_the_isolation_and_the_guard(
    request: pytest.FixtureRequest,
) -> None:
    conftest = _suite_conftest(request.config)
    exported = set(conftest.__all__)
    assert exported >= _GUARD_NAMES
    underscored = {name for name in exported if name.startswith("_")}
    # The texts on __all__ in tests/conftest.py and tests/README.md name these.
    assert underscored == _UNDERSCORE_EXPORTS
    # Assertion rewriting adds names such as "@py_builtins"; no import binds them.
    public = {
        name
        for name in vars(conftest)
        if name.isidentifier() and not name.startswith("_")
    }
    assert public <= exported, "a public name of the module is not exported"
    assert exported >= _PUBLIC_BEFORE_ALL, "a name a star import carried is gone"
    assert "pytest_real_home_guard" not in exported, "dropped on purpose"
    assert [name for name in exported if not hasattr(conftest, name)] == []


def test_a_suite_test_meets_both_guards(request: pytest.FixtureRequest) -> None:
    conftest = _suite_conftest(request.config)
    assert conftest._REAL_HOMES, "the guard captured no real home"
    assert conftest._real_home_findings(conftest._current_locations()) == []
    assert set(_ISOLATION) <= set(request.node.fixturenames)


def test_only_a_real_home_and_its_real_folders_count(
    request: pytest.FixtureRequest,
) -> None:
    """Compare text only: nothing here reads or writes the real home."""
    conftest = _suite_conftest(request.config)
    home = next(iter(conftest._REAL_HOMES))

    def real(*parts: str) -> str | None:
        path = str(Path(home, *parts))  # text only: no Path.resolve, no disk access
        return conftest._real_location(path, path)

    assert real() is not None
    assert real(".apothem") is not None
    assert real(".apothem", "state", "cursor", "ledger.jsonl") is not None
    assert real(".config", "apothem", "rules") is not None
    assert real(".local", "state", "apothem", "session-end-gate") is not None
    assert real(".codex") is not None
    assert real(".codex", "agents") is not None
    assert real(".claude") is not None
    assert real(".config") is not None
    assert real(".config", "opencode") is not None
    # The Windows temporary folder sits below the home; so does any other folder.
    assert real("AppData", "Local", "Temp", "pytest-of-x", "user-home0") is None
    assert real("work", "repo") is None
    assert real(".apothem-other") is None
    assert real(".codex-other") is None
    assert real(".local", "state") is None


@pytest.mark.skipif(sys.platform != "win32", reason="LOCALAPPDATA is a Windows folder")
def test_only_the_apothem_folder_of_the_real_localappdata_counts(
    request: pytest.FixtureRequest,
) -> None:
    """The isolation leaves ``LOCALAPPDATA`` as the process started with it."""
    conftest = _suite_conftest(request.config)
    local = os.path.normcase(os.environ["LOCALAPPDATA"])

    def real(*parts: str) -> str | None:
        path = str(Path(local, *parts))
        return conftest._real_location(path, path)

    assert real() is None
    assert real("Temp", "pytest-of-x", "hook-state0") is None
    assert real("apothem") is not None
    assert real("apothem", "state") is not None


def test_a_captured_folder_that_holds_a_home_or_the_temporary_folder_is_left_out(
    request: pytest.FixtureRequest,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Such a folder would make every test's temporary folder count as real."""
    conftest = _suite_conftest(request.config)
    home = tmp_path / "home"
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))  # holds the home
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", tempfile.gettempdir())
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))

    folders = {shown for _, _, shown, _ in conftest._startup_folders([str(home)])}

    assert str(tmp_path) not in folders
    assert tempfile.gettempdir() not in folders
    assert str(tmp_path / "config") in folders
    assert str(home / ".codex") in folders


def _link_folder(link: Path, target: Path) -> None:
    """Make *link* a folder link to *target*: a junction on Windows."""
    if sys.platform == "win32":
        import _winapi

        _winapi.CreateJunction(str(target), str(link))
    else:
        link.symlink_to(target, target_is_directory=True)


def test_a_temporary_folder_spelled_another_way_is_left_out_too(
    request: pytest.FixtureRequest,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``TEMP`` can be spelled other than it resolves: with an 8.3 short name
    (``RUNNER~1``) on GitHub's Windows runners, under ``/var`` on macOS. A
    link stands in for that here. The variable names the temporary folder
    through the link, and the temporary folder is spelled through the link too
    (as on a runner, where both are short) or as it resolves.
    """
    conftest = _suite_conftest(request.config)
    temp = tmp_path / "temp"
    temp.mkdir()
    spelled = tmp_path / "temp-link"
    try:
        _link_folder(spelled, temp)
    except OSError as error:
        pytest.skip(f"cannot make a folder link here: {error}")
    found = {}
    try:
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(spelled))
        monkeypatch.setenv("XDG_CONFIG_HOME", str(temp / "config"))
        for tempdir in (spelled, temp):
            monkeypatch.setattr(tempfile, "tempdir", str(tempdir))
            found[tempdir] = conftest._startup_folders([str(tmp_path / "home")])
    finally:
        # Removes the link only, never the folder it leads to.
        if sys.platform == "win32":
            os.rmdir(spelled)  # noqa: PTH106
        else:
            spelled.unlink()

    for tempdir, folders in found.items():
        shown = {entry[2] for entry in folders}
        keys = {entry[0] for entry in folders}
        assert str(spelled) not in shown, tempdir
        assert os.path.normcase(os.path.realpath(temp)) not in keys, tempdir
        linked = os.path.normcase(str(spelled))
        assert [key for key in keys if key.startswith(linked)] == [], tempdir


def test_a_folder_below_a_resolved_one_resolves_as_realpath_does(
    request: pytest.FixtureRequest, tmp_path: Path
) -> None:
    """The shortcut for missing folders below the home matches a full realpath."""
    conftest = _suite_conftest(request.config)
    home = tmp_path / "home"
    (home / ".config").mkdir(parents=True)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    paths = [
        home,
        home / ".apothem",  # missing
        home / ".apothem" / "state",  # missing below missing
        home / ".config",  # present
        home / ".config" / "apothem",  # missing below present
    ]
    try:
        (home / "linked").symlink_to(elsewhere, target_is_directory=True)
    except OSError:  # no symlink privilege on this Windows host
        pass
    else:
        paths += [home / "linked", home / "linked" / "apothem"]
    known: dict[str, str] = {}
    for path in paths:
        expected = os.path.normcase(os.path.realpath(path))
        assert conftest._resolved(str(path), known) == expected, path
        assert conftest._resolved(str(path)) == expected, path


def test_a_controller_with_no_usable_temporary_folder_names_no_file(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no usable temporary folder, the xdist controller names no file.

    Python raises ``FileNotFoundError`` when no candidate temporary folder
    can be written (a full disk, say). The controller then names no file for
    its workers, which write what they find after the hand-off to
    ``stderr``, instead of the error stopping the session.
    """
    conftest = _suite_conftest(request.config)

    def no_folder() -> str:
        raise FileNotFoundError(2, "No usable temporary directory found")

    monkeypatch.setattr(tempfile, "gettempdir", no_folder)
    config = SimpleNamespace(stash=pytest.Stash())

    assert conftest._late_folder(config) is None


def test_a_worker_that_cannot_send_a_refusal_says_why(
    request: pytest.FixtureRequest,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A worker's ``stderr`` note names why the refusal did not reach the file.

    It held a refusal after its session finished, with no file named by the
    controller in one run and a file in a folder that is gone in the other.
    """
    conftest = _suite_conftest(request.config)
    gone = tmp_path / "gone" / "gw0.jsonl"
    reasons = {
        "the controller named no file for it": {},
        f"writing {gone} failed: ": {conftest._LATE_TO_THE_CONTROLLER: str(gone)},
    }
    for reason, named in reasons.items():
        config = SimpleNamespace(
            stash=pytest.Stash(),
            workeroutput={},
            workerinput={"workerid": "gw0", **named},
            pluginmanager=SimpleNamespace(get_plugin=lambda name: None),
        )
        refusal = ("after the session finished", ("a refusal",))
        config.stash[conftest._HELD] = [refusal]

        conftest._report_held(config, None)

        note = " ".join(capsys.readouterr().err.split())
        assert "in xdist worker gw0, after the session finished" in note
        assert f"could not send it to the controller: {reason}" in note, note
        assert "The run does not fail on it." in note
        assert not gone.exists()


class _HalfWrites:
    """A file stream whose write puts half its data in the file, then fails."""

    def __init__(self, stream: IO[Any]) -> None:
        self._stream = stream

    def __enter__(self) -> _HalfWrites:
        return self

    def __exit__(self, *exc: object) -> None:
        self._stream.close()

    def __getattr__(self, name: str) -> object:
        return getattr(self._stream, name)

    def write(self, data: bytes | str) -> int:
        self._stream.write(data[: len(data) // 2])
        self._stream.flush()
        raise OSError(errno.ENOSPC, "No space left on device")


def test_a_write_that_fails_part_way_leaves_the_workers_file_as_it_was(
    request: pytest.FixtureRequest, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A worker's failed append is cut back, so the next try writes it once.

    The worker writes the same reports again with its next refusal and when
    it reports what it holds. Half a line left by a failed write, and the
    whole line written after it, would have the controller read the report
    twice.
    """
    conftest = _suite_conftest(request.config)
    late = tmp_path / "gw0.jsonl"
    before = b'{"where": "before", "messages": [], "handed_off": false}\n'
    late.write_bytes(before)
    config = SimpleNamespace(
        stash=pytest.Stash(),
        workerinput={"workerid": "gw0", conftest._LATE_TO_THE_CONTROLLER: str(late)},
    )
    report = ("after the session finished", ("a refusal",))
    opened = Path.open

    def half_open(path: Path, *args: str, **kwargs: str) -> _HalfWrites:
        return _HalfWrites(opened(path, *args, **kwargs))

    with monkeypatch.context() as patch:
        patch.setattr(Path, "open", half_open)
        reason = conftest._sent_late(config, [report])

    assert reason is not None
    assert "No space left on device" in reason
    assert late.read_bytes() == before
    assert conftest._sent_late(config, [report]) is None
    lines = late.read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["where"] for line in lines] == [
        "before",
        "after the session finished",
    ]


def test_a_passing_exit_fails_once_a_refusal_was_reported(
    request: pytest.FixtureRequest,
) -> None:
    """The guard's session-finish and unconfigure wrappers fail a passing exit.

    Its ``pytest_cmdline_main`` wrapper converts the same exits at the end
    of the run, so the pytester cases pass without the conversion in the
    other two wrappers; this checks that conversion on its own. A
    ``SystemExit`` with the code ``None``, 0 or 5, or one that a POSIX
    system cuts to 0 or 5 (256, -256, 261), becomes one with the code 1
    once the guard has reported a refusal; any other code, and any code
    before such a report, stays.
    """
    conftest = _suite_conftest(request.config)
    config = SimpleNamespace(stash=pytest.Stash())

    def ended(code: object, reported: bool) -> object:
        config.stash[conftest._REPORTED] = reported
        with (
            pytest.raises(SystemExit) as raised,
            conftest._a_passing_exit_fails(config),
        ):
            raise SystemExit(code)
        return raised.value.code

    codes = (None, 0, 5, 256, -256, 261, 3, 257, "a message")
    found = {
        (code, reported): ended(code, reported)
        for code in codes
        for reported in (False, True)
    }

    passing = {None, 0, 5, 256, -256, 261}
    assert found == {
        (code, reported): 1 if reported and code in passing else code
        for code in codes
        for reported in (False, True)
    }


def test_the_pytester_cases_pass(tmp_path: Path) -> None:
    """Run the ``case_*`` functions below in a pytester session of their own."""
    session = tmp_path / "session"
    session.mkdir()
    module = session / Path(__file__).name
    shutil.copyfile(__file__, module)
    # An empty ini roots the session here, away from the repo's pytest settings.
    (session / "pytest.ini").write_bytes(b"[pytest]\n")
    env = {
        name: value
        for name, value in os.environ.items()
        if not name.startswith("PYTEST_")
    }
    env[_REPO_VARIABLE] = str(_REPO_ROOT)
    # Keeps the session from writing bytecode next to tests/conftest.py.
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    done = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "pytester",
            "-p",
            "no:cacheprovider",
            "-o",
            f"python_functions={_CASE_PREFIX}*",
            "-q",
            "--basetemp",
            str(tmp_path / "basetemp"),
            module.name,
        ],
        cwd=session,
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=900,
        check=False,
    )
    report = f"{done.stdout}\n{done.stderr}"
    cases = [name for name in globals() if name.startswith(_CASE_PREFIX)]
    assert done.returncode == 0, report
    assert f"{len(cases)} passed" in done.stdout, report


# --- In the pytester session --------------------------------------------------


@pytest.fixture
def fake_real_home(
    pytester: pytest.Pytester,
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    """Point the home at a fresh folder the probe session takes as the real one.

    pytester points ``HOME`` and ``USERPROFILE`` at its own folder; this moves
    them to a sibling of it, so the sentinels the probe tests write into the
    pytester folder never land in a home. ``LOCALAPPDATA`` moves into that home,
    as on Windows, and the variables the call guard compares are cleared, so
    the probe session captures only folders in the fake home. The repo root
    goes on ``sys.path`` for ``-p tests.conftest``.
    """
    home = tmp_path_factory.mktemp("fake-real-home")
    for name in ("HOME", "USERPROFILE"):
        monkeypatch.setenv(name, str(home))
    for name in (
        "HOMEDRIVE",
        "HOMEPATH",
        "CODEX_HOME",
        "CLAUDE_CONFIG_DIR",
        "CLAUDE_PLUGIN_DATA",
        "XDG_CONFIG_HOME",
        "XDG_STATE_HOME",
    ):
        monkeypatch.delenv(name, raising=False)
    local = home / "AppData" / "Local"
    local.mkdir(parents=True)
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    monkeypatch.syspath_prepend(os.environ[_REPO_VARIABLE])
    pytester.makeini("[pytest]\n")
    pytester.makepyfile(test_probe=_PROBES)
    return home


def _run(pytester: pytest.Pytester, *args: str) -> pytest.RunResult:
    return pytester.runpytest("-p", "no:cacheprovider", *args)


def _written(pytester: pytest.Pytester, names: tuple[str, ...]) -> list[str]:
    return [name for name in names if (pytester.path / name).exists()]


def _flagged(result: pytest.RunResult) -> set[str]:
    """Return every name the call guard's findings gave, over all failed tests."""
    names: set[str] = set()
    for line in result.outlines:
        if line.startswith("  - "):
            listed, _, _ = line[len("  - ") :].partition(": ")
            names.update(listed.split(", "))
    return names


def _assert_each_failure_says(result: pytest.RunResult, when: str, *lines: str) -> None:
    """Match *lines* in each probe test's own failure section.

    The short summary repeats the message whole or cut to the terminal width,
    which differs between hosts, so the sections are matched in order, not
    counted.
    """
    expected: list[str] = []
    for test in _PROBE_TESTS:
        expected += [f"*_ {when}{test} _*", *lines]
    result.stdout.fnmatch_lines(expected)


def _assert_stopped(result: pytest.RunResult, pytester: pytest.Pytester) -> None:
    result.assert_outcomes(failed=2)
    assert _written(pytester, _SENTINELS) == []
    _assert_each_failure_says(
        result, "", "real-home guard: stopped before the test body ran*"
    )


def _assert_stopped_at_setup(
    result: pytest.RunResult,
    pytester: pytest.Pytester,
    missing: tuple[str, ...] = _ISOLATION,
) -> None:
    _assert_stopped_at_setup_by(
        result, pytester, f"missing isolation fixtures: {', '.join(missing)}"
    )


def _assert_stopped_at_setup_by(
    result: pytest.RunResult, pytester: pytest.Pytester, line: str
) -> None:
    result.assert_outcomes(errors=2)
    assert _written(pytester, _FIXTURE_SENTINELS) == []
    assert _written(pytester, _SENTINELS) == []
    _assert_each_failure_says(
        result,
        "ERROR at setup of ",
        "real-home guard: stopped before any fixture was set up*",
        line,
    )


def case_a_star_import_isolates_and_runs(
    pytester: pytest.Pytester, fake_real_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``__all__`` carries the isolation fixtures through a star import.

    A developer's own ``CODEX_HOME``, ``CLAUDE_CONFIG_DIR`` and
    ``XDG_CONFIG_HOME`` are cleared by them, and the inherited ``LOCALAPPDATA``
    is left alone without stopping the test. The temporary folders sit inside
    the real home, as on Windows: allowed.
    """
    monkeypatch.setenv("CODEX_HOME", str(fake_real_home / "codex-home"))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(fake_real_home / "claude-config"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(fake_real_home / "xdg-config"))
    pytester.makeconftest(_STAR_IMPORT)

    result = _run(pytester, f"--basetemp={fake_real_home / 'temp'}")

    result.assert_outcomes(passed=2)
    assert result.ret == pytest.ExitCode.OK
    assert _written(pytester, _SENTINELS) == list(_SENTINELS)


def case_a_conftest_without_the_isolation_stops_before_its_fixtures(
    pytester: pytest.Pytester, fake_real_home: Path
) -> None:
    """Importing any name registers the guard; none of the fixtures came along."""
    pytester.makeconftest(_NO_ISOLATION)

    result = _run(pytester)

    _assert_stopped_at_setup(result, pytester)


def case_a_conftest_without_the_isolation_stops_under_setup_only(
    pytester: pytest.Pytester, fake_real_home: Path
) -> None:
    pytester.makeconftest(_NO_ISOLATION)

    result = _run(pytester, "--setup-only")

    _assert_stopped_at_setup(result, pytester)


def case_a_conftest_that_imports_some_isolation_fixtures_stops_for_the_rest(
    pytester: pytest.Pytester, fake_real_home: Path
) -> None:
    """The import of two fixtures by name brings no guard name, but registers it."""
    pytester.makeconftest(_SOME_ISOLATION)

    result = _run(pytester)

    _assert_stopped_at_setup(result, pytester, _NOT_IMPORTED)


def case_an_xfail_test_without_the_isolation_still_errors(
    pytester: pytest.Pytester, fake_real_home: Path
) -> None:
    pytester.makepyfile(test_probe=_XFAIL_PROBES)
    pytester.makeconftest(_NO_ISOLATION)

    result = _run(pytester)

    _assert_stopped_at_setup(result, pytester)


def case_deleting_the_guard_names_leaves_the_guard(
    pytester: pytest.Pytester, fake_real_home: Path
) -> None:
    """The import registered the guard object; the names only point at it."""
    pytester.makeconftest(_STAR_IMPORT + _GUARD_NAMES_DELETED + _REAL_ROOTS_AGAIN)

    result = _run(pytester)

    _assert_stopped(result, pytester)
    assert _flagged(result) == _ROOT_NAMES, result.stdout.str()


def case_a_later_call_wrapper_that_puts_the_real_home_back_is_stopped(
    pytester: pytest.Pytester, fake_real_home: Path
) -> None:
    """pytest starts every wrapper before the guard's plain call hook."""
    pytester.makeconftest(_STAR_IMPORT + _REAL_HOME_IN_A_LATER_WRAPPER)

    result = _run(pytester)

    _assert_stopped(result, pytester)
    assert _flagged(result) == _HOME_NAMES | _FOLDER_NAMES, result.stdout.str()


def case_an_xfail_test_the_call_hook_stops_is_failed_not_xfailed(
    pytester: pytest.Pytester, fake_real_home: Path
) -> None:
    pytester.makepyfile(test_probe=_XFAIL_PROBES)
    pytester.makeconftest(_STAR_IMPORT + _REAL_ROOTS_AGAIN)

    result = _run(pytester)

    _assert_stopped(result, pytester)
    assert _flagged(result) == _ROOT_NAMES, result.stdout.str()


def case_a_session_started_after_the_import_gets_the_guard_from_the_hook(
    pytester: pytest.Pytester, fake_real_home: Path
) -> None:
    """``pytest_register_real_home_guard`` registers it when the import cannot.

    The module is imported first in a thread, whose stack holds no pytest
    session, so the import registers nothing; the probe's star import then finds
    the module already imported. The modules that import added are removed
    again afterwards.
    """
    before = set(sys.modules)
    try:
        worker = threading.Thread(
            target=importlib.import_module, args=["tests.conftest"]
        )
        worker.start()
        worker.join()
        assert "tests.conftest" in sys.modules
        pytester.makeconftest(_STAR_IMPORT + _REAL_ROOTS_AGAIN)

        result = _run(pytester)
    finally:
        for name in set(sys.modules) - before:
            del sys.modules[name]

    _assert_stopped(result, pytester)
    assert _flagged(result) == _ROOT_NAMES, result.stdout.str()


def case_a_session_fixture_set_up_before_the_session_home_is_stopped(
    pytester: pytest.Pytester, fake_real_home: Path
) -> None:
    """``_install_writer`` sorts before ``_isolate_session_home`` in the conftest.

    pytest would set it up first, against the real home, so the setup hook stops
    the test before either is set up.
    """
    pytester.makeconftest(_STAR_IMPORT + _EARLY_SESSION_WRITER)

    result = _run(pytester)

    _assert_stopped_at_setup_by(
        result,
        pytester,
        "  - _install_writer (*) is session-scoped and set up before"
        " _isolate_session_home",
    )


def case_a_session_fixture_that_requests_the_session_home_runs(
    pytester: pytest.Pytester, fake_real_home: Path
) -> None:
    pytester.makeconftest(_STAR_IMPORT + _EARLY_SESSION_WRITER_ISOLATED)

    result = _run(pytester, f"--basetemp={fake_real_home / 'temp'}")

    result.assert_outcomes(passed=2)
    assert _written(pytester, _SENTINELS) == list(_SENTINELS)
    assert _written(pytester, ("fixture-ran-session",)) == ["fixture-ran-session"]


def case_a_fixture_in_place_of_the_session_home_is_stopped(
    pytester: pytest.Pytester, fake_real_home: Path
) -> None:
    """The name alone is not enough: it has to be the fixture of tests/conftest.py."""
    pytester.makeconftest(_STAR_IMPORT + _SESSION_HOME_REPLACED + _SETUP_WRITERS)

    result = _run(pytester)

    _assert_stopped_at_setup_by(
        result,
        pytester,
        "  - _isolate_session_home is not the fixture of tests/conftest.py*",
    )


def case_a_function_call_wrapper_that_puts_the_real_home_back_is_stopped(
    pytester: pytest.Pytester, fake_real_home: Path
) -> None:
    """``Function.runtest`` calls ``pytest_pyfunc_call`` after every call hook."""
    pytester.makeconftest(_STAR_IMPORT + _REAL_HOME_IN_A_FUNCTION_WRAPPER)

    result = _run(pytester)

    _assert_stopped(result, pytester)
    assert _flagged(result) == _HOME_NAMES | _FOLDER_NAMES, result.stdout.str()


def case_a_fixture_that_puts_the_two_roots_back_is_stopped(
    pytester: pytest.Pytester, fake_real_home: Path
) -> None:
    """tests/conftest.py bound the ledger and backup roots from the real home."""
    pytester.makeconftest(_STAR_IMPORT + _REAL_ROOTS_AGAIN)

    result = _run(pytester)

    _assert_stopped(result, pytester)
    assert _flagged(result) == _ROOT_NAMES, result.stdout.str()
    assert str(fake_real_home / ".apothem") in result.stdout.str()


def case_a_fixture_that_hands_the_manifest_the_real_home_is_stopped(
    pytester: pytest.Pytester, fake_real_home: Path
) -> None:
    pytester.makeconftest(_STAR_IMPORT + _REAL_MANIFEST_HOME)

    result = _run(pytester)

    _assert_stopped(result, pytester)
    assert _flagged(result) == {
        "propagation.user_home()",
        "the support folder ~/.config/apothem",
    }, result.stdout.str()


def case_codex_home_on_the_real_codex_home_is_stopped(
    pytester: pytest.Pytester, fake_real_home: Path
) -> None:
    real = fake_real_home / ".codex"
    pytester.makeconftest(_STAR_IMPORT + _variable_again("CODEX_HOME", str(real)))

    result = _run(pytester)

    _assert_stopped(result, pytester)
    assert _flagged(result) == {"CODEX_HOME"}, result.stdout.str()
    assert f"{real} is the real Codex home" in result.stdout.str()


def case_a_developers_own_codex_home_put_back_is_stopped(
    pytester: pytest.Pytester, fake_real_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The folder ``CODEX_HOME`` named at import counts, and what is inside it."""
    own = fake_real_home / "codex-home"
    monkeypatch.setenv("CODEX_HOME", str(own))
    inside = str(own / "profiles")
    pytester.makeconftest(_STAR_IMPORT + _variable_again("CODEX_HOME", inside))

    result = _run(pytester)

    _assert_stopped(result, pytester)
    assert _flagged(result) == {"CODEX_HOME"}, result.stdout.str()
    # The folder is shown resolved, which on macOS adds /private to /var.
    assert f"{inside} is inside the real Codex home" in result.stdout.str()


def case_claude_config_dir_on_the_real_claude_folder_is_stopped(
    pytester: pytest.Pytester, fake_real_home: Path
) -> None:
    real = str(fake_real_home / ".claude")
    pytester.makeconftest(_STAR_IMPORT + _variable_again("CLAUDE_CONFIG_DIR", real))

    result = _run(pytester)

    _assert_stopped(result, pytester)
    assert _flagged(result) == {"CLAUDE_CONFIG_DIR"}, result.stdout.str()


def case_xdg_config_home_on_the_real_config_folder_is_stopped(
    pytester: pytest.Pytester, fake_real_home: Path
) -> None:
    real = str(fake_real_home / ".config")
    pytester.makeconftest(_STAR_IMPORT + _variable_again("XDG_CONFIG_HOME", real))

    result = _run(pytester)

    _assert_stopped(result, pytester)
    assert _flagged(result) == {"XDG_CONFIG_HOME"}, result.stdout.str()


def case_localappdata_counts_once_the_hook_state_falls_back_to_it(
    pytester: pytest.Pytester, fake_real_home: Path
) -> None:
    """Clearing the hook state override sends the hook state to LOCALAPPDATA.

    Only on Windows: elsewhere Apothem never reads ``LOCALAPPDATA``, the hook
    state falls back to the temporary home, and the probes run.
    """
    local = os.environ["LOCALAPPDATA"]
    pytester.makeconftest(
        _STAR_IMPORT + _variable_again("LOCALAPPDATA", local, clear_override=True)
    )

    result = _run(pytester)

    if sys.platform != "win32":
        result.assert_outcomes(passed=2)
        assert _written(pytester, _SENTINELS) == list(_SENTINELS)
        return
    _assert_stopped(result, pytester)
    assert _flagged(result) == {"the hook state folder (from LOCALAPPDATA)"}, (
        result.stdout.str()
    )
    assert str(Path(local, "apothem")) in result.stdout.str()


def case_xdg_state_home_on_the_real_state_folder_is_stopped(
    pytester: pytest.Pytester, fake_real_home: Path
) -> None:
    """With the override cleared, the hook state folder is ``<it>/apothem``.

    That is the real ``~/.local/state/apothem``, on every platform.
    """
    real = str(fake_real_home / ".local" / "state")
    pytester.makeconftest(
        _STAR_IMPORT + _variable_again("XDG_STATE_HOME", real, clear_override=True)
    )

    result = _run(pytester)

    _assert_stopped(result, pytester)
    assert _flagged(result) == {"the hook state folder (from XDG_STATE_HOME)"}, (
        result.stdout.str()
    )


def case_claude_plugin_data_on_the_real_home_is_stopped(
    pytester: pytest.Pytester, fake_real_home: Path
) -> None:
    """The hook state folder ``<home>/state`` is no real folder; the base is."""
    real = str(fake_real_home)
    pytester.makeconftest(
        _STAR_IMPORT + _variable_again("CLAUDE_PLUGIN_DATA", real, clear_override=True)
    )

    result = _run(pytester)

    _assert_stopped(result, pytester)
    assert _flagged(result) == {"CLAUDE_PLUGIN_DATA"}, result.stdout.str()


def case_the_conftest_loaded_as_a_plugin_isolates_and_runs(
    pytester: pytest.Pytester, fake_real_home: Path
) -> None:
    """The temporary folders sit inside the real home, as on Windows: allowed."""
    result = _run(
        pytester, "-p", "tests.conftest", f"--basetemp={fake_real_home / 'temp'}"
    )

    result.assert_outcomes(passed=2)
    assert result.ret == pytest.ExitCode.OK
    assert _written(pytester, _SENTINELS) == list(_SENTINELS)


def case_the_conftest_loaded_as_a_plugin_stops_a_fixture_that_undoes_it(
    pytester: pytest.Pytester, fake_real_home: Path
) -> None:
    pytester.makeconftest(_REAL_HOME_AGAIN)

    result = _run(pytester, "-p", "tests.conftest")

    _assert_stopped(result, pytester)
    assert _flagged(result) == _HOME_NAMES | _FOLDER_NAMES, result.stdout.str()
    assert f"{fake_real_home} is the real home" in result.stdout.str()


def _assert_each_absorbed_refusal_errors(
    result: pytest.RunResult,
    home: Path,
    tests: tuple[str, ...] = _ABSORBING_TESTS,
    **outcomes: int,
) -> None:
    """Each test in *tests* errors at teardown, and nothing reached *home*."""
    result.assert_outcomes(errors=len(tests), **outcomes)
    expected: list[str] = []
    for test in tests:
        expected += [
            f"*_ ERROR at teardown of {test} _*",
            "*Apothem refused a write into the account's real home*",
        ]
    result.stdout.fnmatch_lines(expected)
    assert "XFAIL" not in result.stdout.str()
    assert not (home / ".apothem").exists()


def case_an_xfail_test_that_absorbs_a_refusal_still_errors(
    pytester: pytest.Pytester, fake_real_home: Path
) -> None:
    """pytest's ``skipping`` would turn the teardown error into XFAIL."""
    pytester.makepyfile(
        test_probe=_ABSORBING_PROBES.format(
            home=str(fake_real_home), marker="@pytest.mark.xfail"
        )
    )
    pytester.makeconftest(_STAR_IMPORT)

    result = _run(pytester)

    _assert_each_absorbed_refusal_errors(
        result, fake_real_home, xpassed=len(_ABSORBING_TESTS)
    )


def case_an_xfail_test_errors_when_a_second_copy_reports_the_refusal(
    pytester: pytest.Pytester, fake_real_home: Path
) -> None:
    """A failure from a second copy of tests/conftest.py is the guard's too.

    The probe conftest's ``_report_real_home_refusals`` raises the class of a
    second copy, while the guard, registered once from the first copy, checks.
    The probe conftest checks both before any test runs (see
    ``_SECOND_COPYS_REFUSAL_FIXTURE``). Were the class not recognised,
    ``skipping`` would turn each teardown error into XFAIL and the run would
    exit 0. The test with the module fixture is left out: its refusal is
    logged after the fixture's teardown, and the guard then fails the teardown
    report itself, so that test would fail the run even if the class were not
    recognised.
    """
    tests = _ABSORBING_TESTS[:-1]
    pytester.makepyfile(
        test_probe=_ABSORBING_PROBES.format(
            home=str(fake_real_home), marker="@pytest.mark.xfail"
        )
    )
    pytester.makeconftest(_STAR_IMPORT + _SECOND_COPYS_REFUSAL_FIXTURE)

    result = _run(pytester, "-k", "not module_fixture")

    assert result.ret == pytest.ExitCode.TESTS_FAILED, result.stdout.str()
    _assert_each_absorbed_refusal_errors(
        result, fake_real_home, tests, xpassed=len(tests)
    )


def case_a_test_that_absorbs_a_refusal_errors(
    pytester: pytest.Pytester, fake_real_home: Path
) -> None:
    pytester.makepyfile(
        test_probe=_ABSORBING_PROBES.format(home=str(fake_real_home), marker="")
    )
    pytester.makeconftest(_STAR_IMPORT)

    result = _run(pytester)

    _assert_each_absorbed_refusal_errors(
        result, fake_real_home, passed=len(_ABSORBING_TESTS)
    )


#: A helper that absorbs one refusal of a write into the protected home
#: ``{home}``, for a probe to call outside any test.
_ABSORB_ONE = """
import contextlib

from apothem.lib import home_write_guard


def _absorb():
    home_write_guard.also_protect_home({home!r})
    with contextlib.suppress(OSError):
        home_write_guard.refuse_real_home_write(
            {home!r} + "/.apothem/probe.txt", operation="write"
        )
"""

#: A probe module that absorbs the refusal while it is imported.
_ABSORBED_AT_IMPORT = """
_absorb()


def test_after_the_import():
    pass
"""

#: A conftest hook that absorbs the refusal after the last test.
_ABSORBED_AT_SESSION_FINISH = """

def pytest_sessionfinish(session):
    _absorb()
"""


def case_a_refusal_absorbed_at_import_fails_the_collection(
    pytester: pytest.Pytester, fake_real_home: Path
) -> None:
    """Not the first test that runs after it: the module that absorbed it."""
    pytester.makepyfile(
        test_probe=_ABSORB_ONE.format(home=str(fake_real_home)) + _ABSORBED_AT_IMPORT
    )
    pytester.makeconftest(_STAR_IMPORT)

    result = _run(pytester)

    result.assert_outcomes(errors=1)
    result.stdout.fnmatch_lines(
        [
            "*ERROR collecting test_probe.py*",
            "*outside any test, while pytest collected test_probe.py*",
        ]
    )
    assert "during this test" not in result.stdout.str()
    assert not (fake_real_home / ".apothem").exists()


#: A conftest hook that absorbs the refusal once, after pytest collected
#: ``test_probe.py`` and before it collects ``test_second.py``.
_ABSORBED_WHEN_AN_ITEM_IS_COLLECTED = """

def pytest_itemcollected(item):
    if item.name == "test_fixture_free":
        _absorb()
"""

#: A conftest hook that absorbs the refusal at the session's own collect report.
_ABSORBED_AT_THE_SESSIONS_COLLECT_REPORT = """

def pytest_collectreport(report):
    if report.nodeid == "":
        _absorb()
"""


def case_a_refusal_absorbed_between_two_collect_reports_fails_the_run(
    pytester: pytest.Pytester, fake_real_home: Path
) -> None:
    """Not the collection of the module pytest collects next, which ran no test."""
    pytester.makepyfile(test_second="def test_second():\n    pass\n")
    pytester.makeconftest(
        _STAR_IMPORT
        + _ABSORB_ONE.format(home=str(fake_real_home))
        + _ABSORBED_WHEN_AN_ITEM_IS_COLLECTED
    )

    result = _run(pytester)

    result.assert_outcomes(passed=len(_PROBE_TESTS) + 1)
    assert result.ret == pytest.ExitCode.TESTS_FAILED
    result.stdout.fnmatch_lines(
        [
            "*outside any test, during collection, before pytest collected "
            "test_second.py, and the refusal*"
        ]
    )
    assert "ERROR collecting" not in result.stdout.str()
    assert "during this test" not in result.stdout.str()
    assert not (fake_real_home / ".apothem").exists()


def case_a_refusal_absorbed_at_the_sessions_collect_report_fails_the_run(
    pytester: pytest.Pytester, fake_real_home: Path
) -> None:
    """Not the collection of the root folder, which would drop every test."""
    result = _run_absorbing(
        pytester, fake_real_home, _ABSORBED_AT_THE_SESSIONS_COLLECT_REPORT
    )

    _assert_the_run_failed_on_it(
        result, fake_real_home, "during collection, before pytest collected ."
    )
    assert "ERROR collecting" not in result.stdout.str()


def case_a_refusal_absorbed_after_the_last_test_fails_the_run(
    pytester: pytest.Pytester, fake_real_home: Path
) -> None:
    pytester.makepyfile(test_probe="def test_passes():\n    pass\n")
    pytester.makeconftest(
        _STAR_IMPORT
        + _ABSORB_ONE.format(home=str(fake_real_home))
        + _ABSORBED_AT_SESSION_FINISH
    )

    result = _run(pytester)

    result.assert_outcomes(passed=1)
    assert result.ret == pytest.ExitCode.TESTS_FAILED
    result.stdout.fnmatch_lines(["*outside any test, after the last test*"])
    assert not (fake_real_home / ".apothem").exists()


#: A conftest hook that absorbs the refusal in the terminal summary. pytest's
#: terminal reporter writes the summary after every plain session-finish hook.
_ABSORBED_IN_THE_TERMINAL_SUMMARY = """

def pytest_terminal_summary(terminalreporter):
    _absorb()
"""

#: A session-finish wrapper that absorbs the refusal after it yields, which is
#: after every plain session-finish hook.
_ABSORBED_AFTER_A_SESSION_FINISH_WRAPPER = """

@pytest.hookimpl(wrapper=True)
def pytest_sessionfinish(session):
    try:
        return (yield)
    finally:
        _absorb()
"""

#: A conftest hook that absorbs the refusal when pytest unconfigures.
_ABSORBED_AT_UNCONFIGURE = """

def pytest_unconfigure(config):
    _absorb()
"""

#: A session-finish hook that absorbs the refusal in an xdist worker only.
_ABSORBED_AT_A_WORKERS_SESSION_FINISH = """

def pytest_sessionfinish(session):
    if hasattr(session.config, "workerinput"):
        _absorb()
"""


def _run_absorbing(
    pytester: pytest.Pytester, home: Path, hook: str, *args: str
) -> pytest.RunResult:
    """Run the two probe tests under a conftest whose *hook* absorbs a refusal."""
    pytester.makeconftest(_STAR_IMPORT + _ABSORB_ONE.format(home=str(home)) + hook)
    return _run(pytester, *args)


def _assert_the_run_failed_on_it(
    result: pytest.RunResult, home: Path, where: str
) -> None:
    """Both probe tests pass, and the run fails on the refusal, named *where*."""
    result.assert_outcomes(passed=len(_PROBE_TESTS))
    assert result.ret == pytest.ExitCode.TESTS_FAILED
    result.stdout.fnmatch_lines([f"*outside any test, {where}, and the refusal*"])
    assert "during this test" not in result.stdout.str()
    assert not (home / ".apothem").exists()


def case_a_refusal_absorbed_in_the_terminal_summary_fails_the_run(
    pytester: pytest.Pytester, fake_real_home: Path
) -> None:
    result = _run_absorbing(pytester, fake_real_home, _ABSORBED_IN_THE_TERMINAL_SUMMARY)

    _assert_the_run_failed_on_it(result, fake_real_home, "after the last test")


def case_a_refusal_absorbed_after_a_session_finish_wrapper_yields_fails_the_run(
    pytester: pytest.Pytester, fake_real_home: Path
) -> None:
    result = _run_absorbing(
        pytester, fake_real_home, _ABSORBED_AFTER_A_SESSION_FINISH_WRAPPER
    )

    _assert_the_run_failed_on_it(result, fake_real_home, "after the last test")


def case_a_refusal_absorbed_at_unconfigure_fails_the_run(
    pytester: pytest.Pytester, fake_real_home: Path
) -> None:
    """Without xdist too, whose two hooks the guard implements as optional."""
    result = _run_absorbing(
        pytester, fake_real_home, _ABSORBED_AT_UNCONFIGURE, "-p", "no:xdist"
    )

    _assert_the_run_failed_on_it(result, fake_real_home, "after the session finished")


#: A session-finish hook that absorbs the refusal and then ends the run with
#: ``pytest.exit`` and the exit code ``{code}``.
_ABSORBED_BEFORE_PYTEST_EXIT = """

def pytest_sessionfinish(session):
    _absorb()
    pytest.exit("probe", returncode={code})
"""


def case_pytest_exit_with_code_0_after_a_refusal_still_fails_the_run(
    pytester: pytest.Pytester, fake_real_home: Path
) -> None:
    """pytest sets the code ``pytest.exit`` gives after every session-finish wrapper.

    The guard sets "tests failed" again in ``pytest_unconfigure``, also for
    261, which a POSIX system cuts to 5. Any other code is the hook's own,
    and stays.
    """
    exit_0 = _ABSORBED_BEFORE_PYTEST_EXIT.format(code=0)

    result = _run_absorbing(pytester, fake_real_home, exit_0)

    assert result.ret == pytest.ExitCode.TESTS_FAILED
    result.stdout.fnmatch_lines(
        ["*outside any test, after the last test, and the refusal*"]
    )
    assert not (fake_real_home / ".apothem").exists()
    exit_261 = _ABSORBED_BEFORE_PYTEST_EXIT.format(code=261)
    assert _run_absorbing(pytester, fake_real_home, exit_261).ret == 1
    exit_4 = _ABSORBED_BEFORE_PYTEST_EXIT.format(code=4)
    assert _run_absorbing(pytester, fake_real_home, exit_4).ret == 4


#: A configure hook that absorbs the refusal and then ends the run with
#: ``pytest.exit`` and the exit code 0, before any session starts.
_ABSORBED_BEFORE_PYTEST_EXIT_AT_CONFIGURE = """

def pytest_configure(config):
    _absorb()
    pytest.exit("probe", returncode=0)
"""


def case_pytest_exit_with_code_0_while_pytest_configures_still_fails_the_run(
    pytester: pytest.Pytester, fake_real_home: Path
) -> None:
    """No session starts, so the refusal is named for a run that ran none.

    pytest returns the exit status of the session it made before it
    configured, whose start it never called, after ``pytest_unconfigure``.
    """
    result = _run_absorbing(
        pytester,
        fake_real_home,
        _ABSORBED_BEFORE_PYTEST_EXIT_AT_CONFIGURE,
        "-p",
        "no:xdist",
    )

    assert result.ret == pytest.ExitCode.TESTS_FAILED
    output = " ".join(f"{result.stdout.str()}\n{result.stderr.str()}".split())
    named = "outside any test, while pytest ran no test session, and the refusal"
    assert named in output, output
    assert "after the session finished" not in output
    assert not (fake_real_home / ".apothem").exists()


#: A session-finish hook, a terminal-summary hook and an unconfigure hook,
#: each of which absorbs the refusal and then ends the run with ``sys.exit``
#: and the exit code ``{code}`` (none for a bare ``sys.exit()``).
_ABSORBED_BEFORE_SYS_EXIT = """

def pytest_sessionfinish(session):
    _absorb()
    sys.exit({code})
"""
_ABSORBED_BEFORE_SYS_EXIT_IN_THE_TERMINAL_SUMMARY = """

def pytest_terminal_summary(terminalreporter):
    _absorb()
    sys.exit({code})
"""
_ABSORBED_BEFORE_SYS_EXIT_AT_UNCONFIGURE = """

def pytest_unconfigure(config):
    _absorb()
    sys.exit({code})
"""


def _run_absorbing_in_a_child(
    pytester: pytest.Pytester, home: Path, hook: str, *args: str
) -> pytest.RunResult:
    """Run what :func:`_run_absorbing` runs, in a child process.

    pytester's in-process run cannot report a ``SystemExit`` that leaves
    ``pytest.main``: pytest 9.1 fails there with a ``NameError`` of its own.
    The child inherits the fake real home from the environment.
    """
    pytester.makeconftest(_STAR_IMPORT + _ABSORB_ONE.format(home=str(home)) + hook)
    return pytester.runpytest_subprocess("-p", "no:cacheprovider", *args, timeout=300)


def case_sys_exit_with_code_0_after_a_refusal_still_fails_the_run(
    pytester: pytest.Pytester, fake_real_home: Path
) -> None:
    """pytest catches no ``SystemExit`` around either hook.

    ``sys.exit(0)`` would end the run with 0 after the guard reported the
    refusal, so the guard raises ``SystemExit`` with the code 1 in its
    place, also in an xdist controller, whose workers run the hook too. So
    does a bare ``sys.exit()``, here in a terminal-summary hook, which runs
    within the session finish, ``sys.exit(5)``, as "no tests collected"
    counts as a pass for some jobs, and ``sys.exit(256)``, which a POSIX
    system cuts to 0. Any other code is the hook's own, and stays.
    """
    for hook, code, where, args in (
        (_ABSORBED_BEFORE_SYS_EXIT, "0", "after the last test", ()),
        (_ABSORBED_BEFORE_SYS_EXIT, "0", "after the last test", ("-n", "2")),
        (_ABSORBED_BEFORE_SYS_EXIT, "5", "after the last test", ()),
        (_ABSORBED_BEFORE_SYS_EXIT, "256", "after the last test", ()),
        (
            _ABSORBED_BEFORE_SYS_EXIT_IN_THE_TERMINAL_SUMMARY,
            "",
            "after the last test",
            (),
        ),
        (
            _ABSORBED_BEFORE_SYS_EXIT_AT_UNCONFIGURE,
            "0",
            "after the session finished",
            (),
        ),
    ):
        result = _run_absorbing_in_a_child(
            pytester, fake_real_home, hook.format(code=code), *args
        )

        assert result.ret == pytest.ExitCode.TESTS_FAILED, (code, result.stdout.str())
        result.stdout.fnmatch_lines([f"*outside any test, {where}, and the refusal*"])
    for hook in (_ABSORBED_BEFORE_SYS_EXIT, _ABSORBED_BEFORE_SYS_EXIT_AT_UNCONFIGURE):
        kept = _run_absorbing_in_a_child(pytester, fake_real_home, hook.format(code=3))
        assert kept.ret == 3, kept.stdout.str()
    assert not (fake_real_home / ".apothem").exists()


#: A plain session-finish hook that absorbs the refusal, and a ``tryfirst``
#: session-finish wrapper that pytest registers after the guard, so that it
#: finishes after the guard's own wrappers: it ends the run with
#: ``sys.exit`` and the code ``{code}`` after its ``yield``.
_EXITS_AFTER_THE_GUARDS_SESSION_FINISH_WRAPPERS = """

@pytest.hookimpl(specname="pytest_sessionfinish")
def pytest_sessionfinish_absorbs(session):
    _absorb()


@pytest.hookimpl(wrapper=True, tryfirst=True)
def pytest_sessionfinish(session):
    try:
        return (yield)
    finally:
        sys.exit({code})
"""

#: A ``tryfirst`` unconfigure wrapper that pytest registers after the guard,
#: so that it finishes after the guard's own: after its ``yield`` it absorbs
#: the refusal and ends the run with ``sys.exit`` and the code ``{code}``.
_EXITS_AFTER_THE_GUARDS_UNCONFIGURE_WRAPPER = """

@pytest.hookimpl(wrapper=True, tryfirst=True)
def pytest_unconfigure(config):
    try:
        return (yield)
    finally:
        _absorb()
        sys.exit({code})
"""

#: A cleanup registered with ``config.add_cleanup``, which pytest runs after
#: every ``pytest_unconfigure`` hook: it absorbs the refusal and ends the run
#: with ``sys.exit`` and the code ``{code}``.
_EXITS_IN_A_CLEANUP = """

def _absorb_and_exit():
    _absorb()
    sys.exit({code})


def pytest_configure(config):
    config.add_cleanup(_absorb_and_exit)
"""

#: In the xdist controller only, a plain session-finish hook that ends the
#: run with ``sys.exit(0)`` before the controller has read the files its
#: workers wrote.
_THE_CONTROLLER_EXITS_AT_ITS_SESSION_FINISH = """

def pytest_sessionfinish(session):
    if not hasattr(session.config, "workerinput"):
        sys.exit(0)
"""


def case_sys_exit_after_the_guards_other_hooks_still_fails_the_run(
    pytester: pytest.Pytester, fake_real_home: Path
) -> None:
    """The guard's ``pytest_cmdline_main`` wrapper sees the exit last.

    pytest runs the session-finish and unconfigure hooks, and the cleanups,
    inside ``pytest_cmdline_main``. A ``tryfirst`` wrapper of either hook
    that pytest registers after the guard finishes after the guard's own,
    and a cleanup runs after every unconfigure hook, so a ``sys.exit(0)``
    there passed the run; so did one in an xdist controller's plain
    session-finish hook, before it read what its workers found after they
    handed their refusals over. Any other code stays.
    """
    late = f"{_AFTER_THE_HAND_OFF}, after the last test"
    after = "outside any test, after the session finished, and the refusal"
    found = {}
    for label, hook, args, named in (
        (
            "a later tryfirst session-finish wrapper",
            _EXITS_AFTER_THE_GUARDS_SESSION_FINISH_WRAPPERS.format(code=0),
            (),
            ("outside any test, after the last test, and the refusal",),
        ),
        (
            "a later tryfirst unconfigure wrapper",
            _EXITS_AFTER_THE_GUARDS_UNCONFIGURE_WRAPPER.format(code=0),
            (),
            (after,),
        ),
        ("a cleanup", _EXITS_IN_A_CLEANUP.format(code=0), (), (after,)),
        (
            "the xdist controller",
            _ABSORBED_IN_A_WORKERS_TERMINAL_SUMMARY
            + _THE_CONTROLLER_EXITS_AT_ITS_SESSION_FINISH,
            ("-n", "2"),
            (f"in xdist worker gw0, {late}", f"in xdist worker gw1, {late}"),
        ),
    ):
        result = _run_absorbing_in_a_child(pytester, fake_real_home, hook, *args)

        output = " ".join(result.stdout.str().split())
        found[label] = (result.ret, [output.count(each) for each in named])
    failed = pytest.ExitCode.TESTS_FAILED
    assert {label: (failed, [1] * len(seen)) for label, (_, seen) in found.items()} == (
        found
    )
    kept = _run_absorbing_in_a_child(
        pytester, fake_real_home, _EXITS_IN_A_CLEANUP.format(code=3)
    )
    assert kept.ret == 3, kept.stdout.str()
    assert not (fake_real_home / ".apothem").exists()


#: A plain session-finish hook that ends the run with ``sys.exit`` and the
#: code ``{code}``, after it absorbed the refusal when ``{absorb}`` is true.
_EXITS_AT_THE_SESSION_FINISH = """

def pytest_sessionfinish(session):
    if {absorb}:
        _absorb()
    sys.exit({code})
"""

#: A plain session-finish hook that absorbs the refusal and then raises an
#: exception other than ``SystemExit``.
_RAISES_AT_THE_SESSION_FINISH = """

def pytest_sessionfinish(session):
    _absorb()
    raise RuntimeError("probe")
"""

#: A plain unconfigure hook that absorbs the refusal.
_ABSORBED_AT_UNCONFIGURE_ALONE = """

def pytest_unconfigure(config):
    _absorb()
"""


def case_a_passing_exit_after_one_that_left_the_session_finish_fails_the_run(
    pytester: pytest.Pytester, fake_real_home: Path
) -> None:
    """An exception that leaves the session finish does not hide a later exit.

    pytest skips ``pytest_unconfigure`` and the cleanups then, and calls
    them after ``pytest_cmdline_main``, so the guard's wrapper of that hook
    calls them itself first. A ``sys.exit(0)`` in a cleanup, or in a
    ``tryfirst`` unconfigure wrapper that pytest registered after the guard,
    after a session-finish hook absorbed the refusal and ended the run with
    ``sys.exit`` (0 or 3) or raised another exception, exits 1; so does a
    session-finish ``sys.exit(0)`` when the only refusal comes in a plain
    unconfigure hook after it. A code other than 0 or 5 from the later exit
    stays.
    """
    found = {}
    for label, hook, named in (
        (
            "sys.exit(0) at the session finish, then in a cleanup",
            _EXITS_AT_THE_SESSION_FINISH.format(absorb=True, code=0)
            + _EXITS_IN_A_CLEANUP.format(code=0),
            "outside any test, after the last test, and the refusal",
        ),
        (
            "sys.exit(3) at the session finish, then in a later wrapper",
            _EXITS_AT_THE_SESSION_FINISH.format(absorb=True, code=3)
            + _EXITS_AFTER_THE_GUARDS_UNCONFIGURE_WRAPPER.format(code=0),
            "outside any test, after the last test, and the refusal",
        ),
        (
            "RuntimeError at the session finish, then sys.exit(0) in a cleanup",
            _RAISES_AT_THE_SESSION_FINISH + _EXITS_IN_A_CLEANUP.format(code=0),
            "outside any test, after the last test, and the refusal",
        ),
        (
            "sys.exit(0) at the session finish, the refusal at unconfigure",
            _EXITS_AT_THE_SESSION_FINISH.format(absorb=False, code=0)
            + _ABSORBED_AT_UNCONFIGURE_ALONE,
            "outside any test, after the session finished, and the refusal",
        ),
    ):
        result = _run_absorbing_in_a_child(pytester, fake_real_home, hook)

        output = " ".join(result.stdout.str().split())
        found[label] = (result.ret, named in output)
    failed = pytest.ExitCode.TESTS_FAILED
    assert dict.fromkeys(found, (failed, True)) == found
    kept = _run_absorbing_in_a_child(
        pytester,
        fake_real_home,
        _EXITS_AT_THE_SESSION_FINISH.format(absorb=True, code=3)
        + _EXITS_IN_A_CLEANUP.format(code=4),
    )
    assert kept.ret == 4, kept.stdout.str()
    assert not (fake_real_home / ".apothem").exists()


def case_an_xdist_workers_refusal_after_its_last_test_fails_the_run(
    pytester: pytest.Pytester, fake_real_home: Path
) -> None:
    """The worker hands it to the controller, which ignores the worker's exit code.

    The worker also writes a copy to its file, which the controller skips:
    each refusal is reported once.
    """
    result = _run_absorbing(
        pytester, fake_real_home, _ABSORBED_AT_A_WORKERS_SESSION_FINISH, "-n", "2"
    )

    _assert_the_run_failed_on_it(
        result, fake_real_home, "in xdist worker gw?, after the last test"
    )
    output = result.stdout.str()
    for worker in ("gw0", "gw1"):
        named = f"in xdist worker {worker}, after the last test, and the refusal"
        assert output.count(named) == 1, output


#: A report hook that ends the xdist controller's test loop with
#: ``pytest.exit`` and the exit code 0 at the first test call a worker
#: reports, so the controller never takes what the worker hands over at its
#: session finish. The controller is told apart by its config, as below.
_ENDS_THE_CONTROLLERS_TEST_LOOP = """

CONFIGS = []


def pytest_configure(config):
    CONFIGS.append(config)


def pytest_runtest_logreport(report):
    if not hasattr(CONFIGS[-1], "workerinput") and report.when == "call":
        pytest.exit("probe", returncode=0)
"""


def case_a_workers_refusal_fails_the_run_after_the_controllers_loop_ended(
    pytester: pytest.Pytester, fake_real_home: Path
) -> None:
    """The worker also writes what it hands over to its file.

    The controller's loop ended before it took the worker's output, so it
    reports the refusal from the file, named as the output would name it.
    """
    result = _run_absorbing(
        pytester,
        fake_real_home,
        _ENDS_THE_CONTROLLERS_TEST_LOOP + _ABSORBED_AT_A_WORKERS_SESSION_FINISH,
        "-n",
        "1",
    )

    assert result.ret == pytest.ExitCode.TESTS_FAILED
    output = result.stdout.str()
    named = "in xdist worker gw0, after the last test, and the refusal"
    assert output.count(named) == 1, output
    assert _AFTER_THE_HAND_OFF not in output
    assert not (fake_real_home / ".apothem").exists()


#: How the controller names a refusal an xdist worker found after it handed
#: what it held to the controller.
_AFTER_THE_HAND_OFF = "after it handed its refusals to the controller"

#: A terminal-summary hook that absorbs the refusal in an xdist worker only,
#: after the worker handed its refusals to the controller.
_ABSORBED_IN_A_WORKERS_TERMINAL_SUMMARY = """

def pytest_terminal_summary(terminalreporter, config):
    if hasattr(config, "workerinput"):
        _absorb()
"""

#: An unconfigure hook that absorbs the refusal in an xdist worker only.
_ABSORBED_AT_A_WORKERS_UNCONFIGURE = """

def pytest_unconfigure(config):
    if hasattr(config, "workerinput"):
        _absorb()
"""

#: A ``tryfirst`` session-finish wrapper, registered after the guard and so
#: finishing after the guard's own, that absorbs the refusal after its
#: ``yield`` in an xdist worker only.
_ABSORBED_AFTER_A_WORKERS_FIRST_SESSION_FINISH_WRAPPER = """

@pytest.hookimpl(wrapper=True, tryfirst=True)
def pytest_sessionfinish(session):
    try:
        return (yield)
    finally:
        if hasattr(session.config, "workerinput"):
            _absorb()
"""


def _assert_each_worker_sent_it_late(
    result: pytest.RunResult, home: Path, where: str
) -> None:
    """Both workers found the refusal after the hand-off; the run failed on it."""
    _assert_the_run_failed_on_it(
        result, home, f"in xdist worker gw?, {_AFTER_THE_HAND_OFF}, {where}"
    )
    output = result.stdout.str()
    for worker in ("gw0", "gw1"):
        named = f"in xdist worker {worker}, {_AFTER_THE_HAND_OFF}, {where}"
        assert output.count(named) == 1, output


def case_an_xdist_workers_refusal_in_its_terminal_summary_fails_the_run(
    pytester: pytest.Pytester,
    fake_real_home: Path,
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The worker writes it to a file the controller reads once it is down.

    The controller makes that file's folder in its temporary folder and
    removes it when it has read it.
    """
    temp = tmp_path_factory.mktemp("controller-temp")
    monkeypatch.setattr(tempfile, "tempdir", str(temp))

    result = _run_absorbing(
        pytester, fake_real_home, _ABSORBED_IN_A_WORKERS_TERMINAL_SUMMARY, "-n", "2"
    )

    _assert_each_worker_sent_it_late(result, fake_real_home, "after the last test")
    assert list(temp.iterdir()) == []


#: Keeps the folder of late-refusal files the xdist controller made, as a run
#: stopped before it removed its folder would: the guard's removal does
#: nothing in this session.
_THE_LATE_FOLDER_KEPT = """

import tests.conftest as _guard_module

_guard_module._rmtree = lambda *args, **kwargs: None
"""


def case_a_folder_an_earlier_run_left_is_never_read(
    pytester: pytest.Pytester,
    fake_real_home: Path,
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A later run makes a folder of its own and never reads the earlier one.

    The first run keeps its folder, with each worker's file in it. A second
    run with the same ``--basetemp`` and no refusal passes and names none of
    the first run's refusals, and the first run's files are still there.
    """
    temp = tmp_path_factory.mktemp("controller-temp")
    monkeypatch.setattr(tempfile, "tempdir", str(temp))
    basetemp = f"--basetemp={fake_real_home / 'temp'}"
    kept_and_absorbed = _THE_LATE_FOLDER_KEPT + _ABSORBED_IN_A_WORKERS_TERMINAL_SUMMARY

    first = _run_absorbing(
        pytester, fake_real_home, kept_and_absorbed, "-n", "2", basetemp
    )

    _assert_each_worker_sent_it_late(first, fake_real_home, "after the last test")
    (kept,) = temp.iterdir()
    files = sorted(path.name for path in kept.iterdir())
    assert files == ["gw0.jsonl", "gw1.jsonl"]
    pytester.makeconftest(_STAR_IMPORT)
    again = _run(pytester, "-n", "2", basetemp)
    again.assert_outcomes(passed=len(_PROBE_TESTS))
    assert again.ret == pytest.ExitCode.OK
    assert "refused" not in again.stdout.str()
    assert list(temp.iterdir()) == [kept]
    assert sorted(path.name for path in kept.iterdir()) == files


def case_an_xdist_workers_refusal_at_its_unconfigure_fails_the_run(
    pytester: pytest.Pytester, fake_real_home: Path
) -> None:
    result = _run_absorbing(
        pytester, fake_real_home, _ABSORBED_AT_A_WORKERS_UNCONFIGURE, "-n", "2"
    )

    _assert_each_worker_sent_it_late(
        result, fake_real_home, "after the session finished"
    )


def case_an_xdist_workers_refusal_after_its_first_session_finish_wrapper_fails(
    pytester: pytest.Pytester, fake_real_home: Path
) -> None:
    """The wrapper finishes after the guard's, so the worker's unconfigure sees it."""
    result = _run_absorbing(
        pytester,
        fake_real_home,
        _ABSORBED_AFTER_A_WORKERS_FIRST_SESSION_FINISH_WRAPPER,
        "-n",
        "2",
    )

    _assert_each_worker_sent_it_late(
        result, fake_real_home, "after the session finished"
    )


#: A ``tryfirst`` session-finish hook that ends the run with ``pytest.exit``
#: and the code 0 in the xdist controller. pluggy calls no plain hook after
#: one that raises, so xdist's own, which tells the workers to exit and waits
#: for them, does not run.
_EXITS_BEFORE_XDIST_ENDS_THE_WORKERS = """

@pytest.hookimpl(tryfirst=True)
def pytest_sessionfinish(session):
    if not hasattr(session.config, "workerinput"):
        pytest.exit("probe", returncode=0)
"""

#: An unconfigure hook that absorbs the refusal in an xdist worker after a
#: pause, so the worker is still running when the controller unconfigures.
_ABSORBED_LATE_AT_A_WORKERS_UNCONFIGURE = """

def pytest_unconfigure(config):
    if hasattr(config, "workerinput"):
        import time

        time.sleep(1)
        _absorb()
"""


def case_the_controller_waits_for_its_workers_before_it_reads_their_files(
    pytester: pytest.Pytester, fake_real_home: Path
) -> None:
    """A hook that ends the run before xdist's own leaves the workers running.

    The guard tells them to exit and waits for them before it reads their
    files, so what they find in their ``pytest_unconfigure`` still fails the
    run, which ``pytest.exit`` set to 0. pytest writes no summary then.
    """
    result = _run_absorbing(
        pytester,
        fake_real_home,
        _EXITS_BEFORE_XDIST_ENDS_THE_WORKERS + _ABSORBED_LATE_AT_A_WORKERS_UNCONFIGURE,
        "-n",
        "2",
    )

    assert result.ret == pytest.ExitCode.TESTS_FAILED
    output = result.stdout.str()
    for worker in ("gw0", "gw1"):
        named = f"in xdist worker {worker}, {_AFTER_THE_HAND_OFF}, after the session"
        assert output.count(named) == 1, output
    assert not (fake_real_home / ".apothem").exists()


#: A session-start hook that absorbs the refusal in an xdist worker and ends
#: the worker's session there, so the worker never reaches its session
#: finish and hands nothing to the controller.
_ABSORBED_WHERE_A_WORKERS_SESSION_ENDS_AT_ITS_START = """

def pytest_sessionstart(session):
    if hasattr(session.config, "workerinput"):
        _absorb()
        pytest.exit("probe", returncode=0)
"""


def case_a_worker_that_handed_nothing_over_is_not_named_as_if_it_had(
    pytester: pytest.Pytester, fake_real_home: Path
) -> None:
    """A worker whose session ends at its start sends its refusal in the file.

    It never reached its session finish, where it hands its refusals to the
    controller, so the controller names the refusal for where it happened,
    not as found after that hand-off.
    """
    result = _run_absorbing(
        pytester,
        fake_real_home,
        _ABSORBED_WHERE_A_WORKERS_SESSION_ENDS_AT_ITS_START,
        "-n",
        "1",
        "--max-worker-restart",
        "0",
    )

    assert result.ret == pytest.ExitCode.TESTS_FAILED
    output = result.stdout.str()
    named = f"in xdist worker gw0, {_AT_SESSION_START}, and the refusal"
    assert output.count(named) == 1, output
    assert _AFTER_THE_HAND_OFF not in output
    assert not (fake_real_home / ".apothem").exists()


#: In an xdist worker only: a report hook that absorbs the refusal at the
#: first probe test's teardown report, which the second test's setup holds
#: as made between two tests; a finish hook that absorbs it again when the
#: last test is done; and a plain session-finish hook that then ends that
#: worker's process with ``os._exit(0)``, as a crash or a kill while it is
#: idle would, before it hands anything to the controller. The worker is
#: told apart by its config, as below.
_ABSORBED_IN_A_WORKER_THAT_THEN_ENDS = """

CONFIGS = []
ABSORBED = []


def pytest_configure(config):
    CONFIGS.append(config)


def _in_a_worker():
    return hasattr(CONFIGS[-1], "workerinput")


def pytest_runtest_logreport(report):
    if (
        _in_a_worker()
        and report.when == "teardown"
        and report.nodeid.endswith("test_fixture_free")
    ):
        _absorb()
        ABSORBED.append(report.nodeid)


def pytest_runtest_logfinish(nodeid, location):
    if _in_a_worker() and nodeid.endswith("test_with_tmp_path"):
        _absorb()


def pytest_sessionfinish(session):
    if _in_a_worker() and ABSORBED:
        os._exit(0)
"""

#: The same hooks, in a worker that goes on to hand its refusals over.
_ABSORBED_IN_A_WORKER_THAT_HANDS_THEM_OVER = (
    _ABSORBED_IN_A_WORKER_THAT_THEN_ENDS.replace("os._exit(0)", "pass")
)

#: Where the worker of those hooks found each refusal.
_HELD_BY_A_WORKER = (
    "between two tests, before test_probe.py::test_with_tmp_path",
    "after the last test",
)


def case_a_worker_that_ends_before_it_hands_its_refusals_over_fails_the_run(
    pytester: pytest.Pytester, fake_real_home: Path
) -> None:
    """The worker writes each refusal to its file as it holds it.

    ``--dist loadfile`` runs both probe tests in one worker. It ends in its
    session finish, before it hands what it holds to the controller, so
    xdist reports it down but fails no test, since none was running on it.
    The controller reads its file and fails the run on both refusals: the
    one held between the two tests, and the one logged after the last test,
    which the worker holds when its session finish starts. A worker that
    hands the same refusals over has each reported once, not again from
    its file.
    """
    args = ("-n", "2", "--dist", "loadfile", "--max-worker-restart", "0")
    result = _run_absorbing(
        pytester, fake_real_home, _ABSORBED_IN_A_WORKER_THAT_THEN_ENDS, *args
    )

    result.assert_outcomes(passed=len(_PROBE_TESTS))
    assert result.ret == pytest.ExitCode.TESTS_FAILED, result.stdout.str()
    output = " ".join(result.stdout.str().split())
    crashed = re.search(r"worker (gw\d) crashed", output)
    assert crashed is not None, output
    for where in _HELD_BY_A_WORKER:
        named = f"outside any test, in xdist worker {crashed[1]}, {where}, and"
        assert output.count(named) == 1, output
    assert _AFTER_THE_HAND_OFF not in output
    handed = _run_absorbing(
        pytester, fake_real_home, _ABSORBED_IN_A_WORKER_THAT_HANDS_THEM_OVER, *args
    )
    handed.assert_outcomes(passed=len(_PROBE_TESTS))
    assert handed.ret == pytest.ExitCode.TESTS_FAILED, handed.stdout.str()
    output = " ".join(handed.stdout.str().split())
    assert "crashed" not in output, output
    for where in _HELD_BY_A_WORKER:
        named = rf"in xdist worker gw\d, {re.escape(where)}, and"
        assert len(re.findall(named, output)) == 1, output
    assert not (fake_real_home / ".apothem").exists()


#: The same hooks, with a session-finish wrapper in place of the hook that
#: ends the worker: in a worker that absorbed a refusal, it runs ``STOP``
#: before its ``yield``, so no implementation it encloses runs.
_ABSORBED_IN_A_WORKER_WHOSE_WRAPPER_STOPS = (
    _ABSORBED_IN_A_WORKER_THAT_THEN_ENDS.replace(
        """
def pytest_sessionfinish(session):
    if _in_a_worker() and ABSORBED:
        os._exit(0)
""",
        """
@pytest.hookimpl(wrapper=True)
def pytest_sessionfinish(session):
    if _in_a_worker() and ABSORBED:
        STOP
    return (yield)
""",
    )
)


def case_a_worker_whose_wrapper_stops_its_session_finish_still_fails_the_run(
    pytester: pytest.Pytester, fake_real_home: Path
) -> None:
    """The worker's output reaches the controller without the hand-off in it.

    pytest registers a probe conftest in the worker before xdist's worker
    plugin, so xdist's session-finish wrapper encloses the conftest's and
    still sends the worker's output, and the conftest's wrapper encloses the
    guard's ``trylast`` one, which never starts when the conftest's raises
    or calls ``pytest.exit`` before its ``yield``. The controller then
    reports what the worker wrote to its file, each refusal once.
    """
    args = ("-n", "2", "--dist", "loadfile", "--max-worker-restart", "0")
    for stop in ('raise RuntimeError("probe")', 'pytest.exit("probe", returncode=0)'):
        hooks = _ABSORBED_IN_A_WORKER_WHOSE_WRAPPER_STOPS.replace("STOP", stop)

        result = _run_absorbing(pytester, fake_real_home, hooks, *args)

        assert result.ret == pytest.ExitCode.TESTS_FAILED, result.stdout.str()
        output = " ".join(result.stdout.str().split())
        for where in _HELD_BY_A_WORKER:
            named = rf"in xdist worker gw\d, {re.escape(where)}, and"
            assert len(re.findall(named, output)) == 1, output
        assert _AFTER_THE_HAND_OFF not in output
    assert not (fake_real_home / ".apothem").exists()


#: Where the probe hooks below find the file an xdist worker writes its late
#: refusals to, in ``config.workerinput``.
_LATE_FILE_KEY = "apothem-real-home-late-refusals"

#: An unconfigure hook that leaves the file an xdist worker writes its late
#: refusals to empty, as a worker stopped after it created the file would.
_AN_EMPTY_LATE_FILE = f"""

def pytest_unconfigure(config):
    if hasattr(config, "workerinput"):
        open(config.workerinput[{_LATE_FILE_KEY!r}], "a").close()
"""


def case_an_empty_late_file_a_worker_left_fails_the_run(
    pytester: pytest.Pytester, fake_real_home: Path
) -> None:
    """A worker creates the file only to write a refusal it found.

    An empty one means it was stopped while it wrote, so the run fails, and
    the report names the worker and the file.
    """
    pytester.makeconftest(_STAR_IMPORT + _AN_EMPTY_LATE_FILE)

    result = _run(pytester, "-n", "1")

    result.assert_outcomes(passed=len(_PROBE_TESTS))
    assert result.ret == pytest.ExitCode.TESTS_FAILED
    output = " ".join(result.stdout.str().split())
    assert "outside any test, in xdist worker gw0, and the refusal" in output
    assert "gw0.jsonl is empty: the worker creates it only to write" in output
    assert not (fake_real_home / ".apothem").exists()


#: An unconfigure hook that leaves the start of a line in the file an xdist
#: worker writes its late refusals to, as a worker stopped while it wrote
#: the line would.
_A_CUT_LATE_LINE = f"""

def pytest_unconfigure(config):
    if hasattr(config, "workerinput"):
        with open(config.workerinput[{_LATE_FILE_KEY!r}], "a") as stream:
            stream.write('{{"where": "probe", "messa')
"""

#: An unconfigure hook that puts a folder where an xdist worker writes its
#: late refusals, so the controller cannot read that file.
_A_FOLDER_IN_PLACE_OF_THE_LATE_FILE = f"""

def pytest_unconfigure(config):
    if hasattr(config, "workerinput"):
        import os

        os.mkdir(config.workerinput[{_LATE_FILE_KEY!r}])
"""


def case_a_cut_line_in_a_workers_late_file_fails_the_run(
    pytester: pytest.Pytester, fake_real_home: Path
) -> None:
    """A line the controller cannot read is reported whole, for the worker."""
    pytester.makeconftest(_STAR_IMPORT + _A_CUT_LATE_LINE)

    result = _run(pytester, "-n", "1")

    result.assert_outcomes(passed=len(_PROBE_TESTS))
    assert result.ret == pytest.ExitCode.TESTS_FAILED
    output = " ".join(result.stdout.str().split())
    named = "outside any test, in xdist worker gw0, and the refusal was not raised:"
    assert f'{named} - {{"where": "probe", "messa' in output, output


def case_a_workers_late_file_the_controller_cannot_read_fails_the_run(
    pytester: pytest.Pytester, fake_real_home: Path
) -> None:
    """The worker made it only to write a refusal, so the run fails on it."""
    pytester.makeconftest(_STAR_IMPORT + _A_FOLDER_IN_PLACE_OF_THE_LATE_FILE)

    result = _run(pytester, "-n", "1")

    result.assert_outcomes(passed=len(_PROBE_TESTS))
    assert result.ret == pytest.ExitCode.TESTS_FAILED
    output = " ".join(result.stdout.str().split())
    named = "outside any test, in xdist worker gw0, and the refusal was not raised:"
    assert f"{named} - the guard could not read " in output, output
    assert "gw0.jsonl" in output


#: Protects the fake real home when the probe conftest is imported, before the
#: xdist controller starts its workers.
_PROTECTED_AT_IMPORT = """

home_write_guard.also_protect_home({home!r})
"""


def case_an_xdist_controller_makes_no_folder_in_a_protected_temporary_folder(
    pytester: pytest.Pytester, fake_real_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Apothem would refuse a write into it, so the guard writes nothing there.

    The workers then have no file for what they find after the hand-off and
    write it to ``stderr`` instead, and the run passes, as it did before the
    file.
    """
    temp = fake_real_home / ".apothem" / "temp"
    temp.mkdir(parents=True)
    monkeypatch.setattr(tempfile, "tempdir", str(temp))

    result = _run_absorbing(
        pytester,
        fake_real_home,
        _PROTECTED_AT_IMPORT.format(home=str(fake_real_home))
        + _ABSORBED_AT_A_WORKERS_UNCONFIGURE,
        "-n",
        "2",
    )

    result.assert_outcomes(passed=len(_PROBE_TESTS))
    assert result.ret == pytest.ExitCode.OK
    assert "refused" not in result.stdout.str()
    assert list(temp.iterdir()) == []


#: A session-finish hook that pytest calls after the guard's own, in a
#: conftest that pytest registers during collection, after the guard. It
#: absorbs the refusal in an xdist worker only.
_ABSORBED_LAST_AT_A_WORKERS_SESSION_FINISH = """

@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session):
    if hasattr(session.config, "workerinput"):
        _absorb()
"""


def case_a_later_conftests_refusal_at_a_workers_session_finish_fails_the_run(
    pytester: pytest.Pytester, fake_real_home: Path
) -> None:
    """A ``trylast`` hook of a conftest found during collection runs last.

    The worker hands what it holds to the controller after it all the same.
    """
    pytester.makeconftest(_STAR_IMPORT)
    sub = pytester.mkdir("sub")
    (sub / "conftest.py").write_text(
        "import pytest\n"
        + _ABSORB_ONE.format(home=str(fake_real_home))
        + _ABSORBED_LAST_AT_A_WORKERS_SESSION_FINISH,
        encoding="utf-8",
    )

    result = _run(pytester, "-n", "2")

    _assert_the_run_failed_on_it(
        result, fake_real_home, "in xdist worker gw?, after the last test"
    )


def case_an_interrupted_xdist_workers_refusal_is_reported_once(
    pytester: pytest.Pytester, fake_real_home: Path
) -> None:
    """xdist reports a worker that stopped on Ctrl-C down twice."""
    pytester.makepyfile(test_probe="def test_stops():\n    raise KeyboardInterrupt\n")

    result = _run_absorbing(
        pytester,
        fake_real_home,
        _ABSORBED_AT_SESSION_START,
        "-n",
        "1",
        "--max-worker-restart",
        "0",
    )

    assert result.ret == pytest.ExitCode.INTERRUPTED
    output = result.stdout.str()
    assert output.count(f"in xdist worker gw0, {_AT_SESSION_START}") == 1, output
    assert not (fake_real_home / ".apothem").exists()


#: A conftest hook that absorbs the refusal in the xdist controller only,
#: for each test a worker reports. The controller is told apart by its config,
#: which has no ``workerinput``, not by ``PYTEST_XDIST_WORKER``: the pytester
#: session runs in the process of the case, which has that variable when the
#: cases themselves run in an xdist worker.
_ABSORBED_IN_THE_CONTROLLER_DURING_THE_RUN = """

CONFIGS = []


def pytest_configure(config):
    CONFIGS.append(config)


def pytest_runtest_logreport(report):
    if not hasattr(CONFIGS[-1], "workerinput") and report.when == "call":
        _absorb()
"""


def case_an_xdist_controllers_refusal_during_the_run_is_named_for_it(
    pytester: pytest.Pytester, fake_real_home: Path
) -> None:
    """The controller runs no test, so not after the last test."""
    result = _run_absorbing(
        pytester, fake_real_home, _ABSORBED_IN_THE_CONTROLLER_DURING_THE_RUN, "-n", "2"
    )

    _assert_the_run_failed_on_it(
        result, fake_real_home, "in the xdist controller, during the test run"
    )
    assert "after the last test" not in result.stdout.str()


def case_a_passing_session_under_xdist_exits_zero(
    pytester: pytest.Pytester, fake_real_home: Path
) -> None:
    pytester.makeconftest(_STAR_IMPORT)

    result = _run(pytester, "-n", "2")

    result.assert_outcomes(passed=len(_PROBE_TESTS))
    assert result.ret == pytest.ExitCode.OK
    assert "refused" not in result.stdout.str()


#: A conftest hook that absorbs the refusal when the session starts.
_ABSORBED_AT_SESSION_START = """

def pytest_sessionstart(session):
    _absorb()
"""

#: A conftest collection hook that absorbs the refusal before pytest's own
#: collects anything.
_ABSORBED_BEFORE_COLLECTION = """

def pytest_collection(session):
    _absorb()
"""

#: A conftest hook that absorbs the refusal after the last collect report.
_ABSORBED_AFTER_COLLECTION = """

def pytest_collection_modifyitems(session, config, items):
    _absorb()
"""

#: A test-loop wrapper that absorbs the refusal before the first test.
_ABSORBED_BEFORE_THE_TEST_LOOP = """

@pytest.hookimpl(wrapper=True)
def pytest_runtestloop(session):
    _absorb()
    return (yield)
"""

_AT_SESSION_START = "at the session start, before collection"
_BEFORE_THE_FIRST_TEST = "after collection, before the first test"


def _assert_nothing_collected_failed(result: pytest.RunResult) -> None:
    output = result.stdout.str()
    assert "ERROR collecting" not in output
    assert "found no collectors" not in output
    assert "while pytest collected" not in output


def case_a_refusal_absorbed_at_session_start_fails_the_run_after_the_tests(
    pytester: pytest.Pytester, fake_real_home: Path
) -> None:
    """Failing the session's collection would drop every test it collected."""
    result = _run_absorbing(pytester, fake_real_home, _ABSORBED_AT_SESSION_START)

    _assert_the_run_failed_on_it(result, fake_real_home, _AT_SESSION_START)
    _assert_nothing_collected_failed(result)


def case_a_refusal_absorbed_before_collection_fails_the_run_after_the_tests(
    pytester: pytest.Pytester, fake_real_home: Path
) -> None:
    result = _run_absorbing(pytester, fake_real_home, _ABSORBED_BEFORE_COLLECTION)

    _assert_the_run_failed_on_it(result, fake_real_home, _AT_SESSION_START)
    _assert_nothing_collected_failed(result)


def case_a_refusal_absorbed_after_collection_fails_the_run_not_the_first_test(
    pytester: pytest.Pytester, fake_real_home: Path
) -> None:
    result = _run_absorbing(pytester, fake_real_home, _ABSORBED_AFTER_COLLECTION)

    _assert_the_run_failed_on_it(result, fake_real_home, _BEFORE_THE_FIRST_TEST)


#: A collection-finish hook that absorbs the refusal. pytest calls it also
#: when the collection stops on an error.
_ABSORBED_AT_COLLECTION_FINISH = """

def pytest_collection_finish(session):
    _absorb()
"""


def case_a_refusal_absorbed_at_collection_finish_is_named_when_no_test_runs(
    pytester: pytest.Pytester, fake_real_home: Path
) -> None:
    """A path that does not exist stops the collection: no test loop starts."""
    result = _run_absorbing(
        pytester, fake_real_home, _ABSORBED_AT_COLLECTION_FINISH, "does_not_exist.py"
    )

    assert result.ret == pytest.ExitCode.USAGE_ERROR
    result.stdout.fnmatch_lines(
        [f"*outside any test, {_BEFORE_THE_FIRST_TEST}, and the refusal*"]
    )
    assert "after the last test" not in result.stdout.str()
    assert not (fake_real_home / ".apothem").exists()


def case_a_refusal_absorbed_before_the_test_loop_fails_the_run_not_the_first_test(
    pytester: pytest.Pytester, fake_real_home: Path
) -> None:
    result = _run_absorbing(pytester, fake_real_home, _ABSORBED_BEFORE_THE_TEST_LOOP)

    _assert_the_run_failed_on_it(result, fake_real_home, _BEFORE_THE_FIRST_TEST)


#: A conftest hook that absorbs the refusal once, at the first test's teardown
#: report, after which that test is done.
_ABSORBED_AT_A_TEARDOWN_REPORT = """

def pytest_runtest_logreport(report):
    if report.when == "teardown" and report.nodeid.endswith("test_fixture_free"):
        _absorb()
"""

#: A plain test-loop hook, which pytest calls before its own, that absorbs the
#: refusal and lets pytest's own run the tests.
_ABSORBED_IN_A_PLAIN_TEST_LOOP = """

def pytest_runtestloop(session):
    _absorb()
"""


def case_a_refusal_absorbed_between_two_tests_fails_the_run_not_the_next_test(
    pytester: pytest.Pytester, fake_real_home: Path
) -> None:
    result = _run_absorbing(pytester, fake_real_home, _ABSORBED_AT_A_TEARDOWN_REPORT)

    _assert_the_run_failed_on_it(
        result,
        fake_real_home,
        "between two tests, before test_probe.py::test_with_tmp_path",
    )


def case_a_refusal_absorbed_in_a_plain_test_loop_fails_the_run_not_the_first_test(
    pytester: pytest.Pytester, fake_real_home: Path
) -> None:
    result = _run_absorbing(pytester, fake_real_home, _ABSORBED_IN_A_PLAIN_TEST_LOOP)

    _assert_the_run_failed_on_it(result, fake_real_home, _BEFORE_THE_FIRST_TEST)


#: How a refusal from the test loop is named when the loop ran no test.
_IN_A_LOOP_WITHOUT_TESTS = "after collection, in a test loop that ran no test"


def case_a_refusal_absorbed_in_a_plain_test_loop_is_named_when_no_test_runs(
    pytester: pytest.Pytester, fake_real_home: Path
) -> None:
    """``--co`` runs no test, and neither does a run that deselects every test.

    No test's setup takes the refusal, so the loop names it when it ends,
    not as made after the last test.
    """
    for args in (["--co"], ["-k", "no_such_test"]):
        result = _run_absorbing(
            pytester, fake_real_home, _ABSORBED_IN_A_PLAIN_TEST_LOOP, *args
        )

        assert result.ret == pytest.ExitCode.TESTS_FAILED, args
        result.stdout.fnmatch_lines(
            [f"*outside any test, {_IN_A_LOOP_WITHOUT_TESTS}, and the refusal*"]
        )
        assert "after the last test" not in result.stdout.str(), args
        assert not (fake_real_home / ".apothem").exists()


def case_a_session_start_refusal_fails_a_run_that_collects_no_test(
    pytester: pytest.Pytester, fake_real_home: Path
) -> None:
    """The exit code says tests failed, not that none was collected."""
    pytester.makepyfile(test_probe="")

    result = _run_absorbing(pytester, fake_real_home, _ABSORBED_AT_SESSION_START)

    assert result.ret == pytest.ExitCode.TESTS_FAILED
    result.stdout.fnmatch_lines(["*collected 0 items*"])
    result.stdout.fnmatch_lines([f"*outside any test, {_AT_SESSION_START}, and*"])
    assert not (fake_real_home / ".apothem").exists()


def case_a_session_start_refusal_under_xdist_is_named_where_it_happened(
    pytester: pytest.Pytester, fake_real_home: Path
) -> None:
    """The controller collects nothing; each worker sends its own refusal."""
    result = _run_absorbing(
        pytester, fake_real_home, _ABSORBED_AT_SESSION_START, "-n", "2"
    )

    _assert_the_run_failed_on_it(result, fake_real_home, _AT_SESSION_START)
    _assert_nothing_collected_failed(result)
    output = result.stdout.str()
    assert output.count(f", {_AT_SESSION_START}, and the refusal") == 3, output
    assert output.count(f"in xdist worker gw0, {_AT_SESSION_START}") == 1, output
    assert output.count(f"in xdist worker gw1, {_AT_SESSION_START}") == 1, output
    assert "after the last test" not in output
