# SPDX-License-Identifier: MIT

"""The real-home guard in ``tests/conftest.py`` stops a test before it can write.

Importing ``tests/conftest.py`` registers ``real_home_guard`` with the pytest
session doing the import. Its setup hook fails a test, before any of its fixtures
is set up, when the isolation fixtures of ``tests/conftest.py`` do not apply to
it. Its call hook fails a test, before its body runs, when its environment points
Apothem at the home the pytest process started with or at a real folder in it.
Its report hook keeps such a failure failed when the test is marked ``xfail``.
``__all__`` makes a star import of ``tests/conftest.py`` carry the isolation
fixtures, which a star import used to skip because their names start with ``_``.

The ``test_*`` functions run in the suite, where ``tests/conftest.py`` is loaded
as a conftest. They check that the guard is registered once, with its hooks
ordered as intended, and that the call hook finds nothing for a suite test, and
they check the guard's comparison on text: a folder below a real home is
allowed, but not the home or a real folder in it.

Showing the guard stop a test takes a pytest session of its own, because the
call hook compares with the home its session started with.
``test_the_pytester_cases_pass`` starts ``python -m pytest -p pytester`` on a
copy of this file, and that session collects only the ``case_*`` functions, so
the ``pytester`` plugin stays out of the suite's own session. Each case points
``HOME``, ``USERPROFILE`` and ``LOCALAPPDATA`` at fresh folders, the fake real
ones, writes a probe folder with pytester and runs it in-process. The probe
session imports ``tests/conftest.py`` anew (one case imports it just before, in
a thread, with the fake real home already set), so the fake real home is its
real home, and the developer's own home is never named. The probe tests only read the
home; the first line of each writes a sentinel file into the probe folder, never
into a home, so a missing sentinel proves the body never started. The probe
fixtures that stand for a fixture writing during setup write their sentinels
there too. One probe test uses no fixture and the other uses ``tmp_path``.
"""

from __future__ import annotations

import importlib
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING

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
    # The conftest module itself holds no guard hook, only the registrar.
    for hook in ("pytest_runtest_setup", "pytest_runtest_call", "pytest_pyfunc_call"):
        caller = getattr(request.node.ihook, hook)
        assert [i for i in caller.get_hookimpls() if i.plugin is conftest] == []
    registrars = [
        impl
        for impl in request.config.hook.pytest_configure.get_hookimpls()
        if impl.plugin is conftest
    ]
    assert [impl.function.__name__ for impl in registrars] == [
        "pytest_register_real_home_guard"
    ]


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


def test_a_star_import_carries_the_isolation_and_the_guard(
    request: pytest.FixtureRequest,
) -> None:
    conftest = _suite_conftest(request.config)
    exported = set(conftest.__all__)
    assert exported >= {*_ISOLATION, "_isolate_hook_state", *_GUARD_NAMES}
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
    assert _written(pytester, _SENTINELS) == list(_SENTINELS)


def case_the_conftest_loaded_as_a_plugin_stops_a_fixture_that_undoes_it(
    pytester: pytest.Pytester, fake_real_home: Path
) -> None:
    pytester.makeconftest(_REAL_HOME_AGAIN)

    result = _run(pytester, "-p", "tests.conftest")

    _assert_stopped(result, pytester)
    assert _flagged(result) == _HOME_NAMES | _FOLDER_NAMES, result.stdout.str()
    assert f"{fake_real_home} is the real home" in result.stdout.str()
