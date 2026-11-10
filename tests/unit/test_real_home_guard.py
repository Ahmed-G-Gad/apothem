# SPDX-License-Identifier: MIT

"""The real-home guard in ``tests/conftest.py`` stops a test before its body runs.

The guard fails a test whose environment points Apothem at the home the pytest
process started with. It matters most where the isolation fixtures never ran: a
conftest outside ``tests/`` that star-imports ``tests/conftest.py`` gets none of
them, because a star import skips names that start with ``_``.

The ``test_*`` functions run in the suite, where ``tests/conftest.py`` is loaded
as a conftest. The guard wraps their call and finds nothing, its comparison
allows a folder below a real home but not the home or an Apothem folder in it,
and its shortcut for missing folders resolves a path as ``os.path.realpath``
does.

Showing the guard stop a test takes a pytest session of its own, because the
guard compares with the home its session started with.
``test_the_pytester_cases_pass`` starts ``python -m pytest -p pytester`` on a
copy of this file, and that session collects only the ``case_*`` functions, so
the ``pytester`` plugin stays out of the suite's own session. Each case points
``HOME`` and ``USERPROFILE`` at a fresh folder, the fake real home, writes a
probe folder with pytester and runs it in-process. The probe session imports
``tests/conftest.py`` anew, so the fake real home is its real home, and the
developer's own home is never named. The probe tests only read the home; the
first line of each writes a sentinel file into the probe folder, never into a
home, so a missing sentinel proves the body never started. One probe test uses
no fixture and the other uses ``tmp_path``.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

#: Hands the repo root to the pytester session, which runs from a copy of this file.
_REPO_VARIABLE = "APOTHEM_REAL_HOME_GUARD_REPO"
_REPO_ROOT = Path(os.environ.get(_REPO_VARIABLE) or Path(__file__).resolve().parents[2])
_CONFTEST = _REPO_ROOT / "tests" / "conftest.py"
_GUARD = "pytest_real_home_guard"
#: The functions the pytester session collects, and the suite does not.
_CASE_PREFIX = "case_"

# --- The probe folder the cases build ----------------------------------------

#: The import the guard has to survive: it carries no name that starts with "_".
_STAR_IMPORT = f"""\
import os
import sys

sys.path.insert(0, os.environ[{_REPO_VARIABLE!r}])

from tests.conftest import *  # noqa: E402, F403
"""

#: Gives each probe test a home of its own.
_OWN_HOME = """
import pytest


@pytest.fixture(autouse=True)
def probe_home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    for name in ("HOME", "USERPROFILE"):
        monkeypatch.setenv(name, str(home))
"""

#: Re-points the two roots tests/conftest.py bound from the real home at import.
_OWN_ROOTS = """

@pytest.fixture(autouse=True)
def probe_roots(tmp_path, monkeypatch):
    monkeypatch.setattr(install_ledger, "STATE_ROOT", tmp_path / "state")
    monkeypatch.setattr(install_driver, "BACKUP_ROOT", tmp_path / "backups")
"""

#: Hands the real home to the install manifest through its own seam.
_REAL_MANIFEST_HOME = """
from pathlib import Path

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

#: The names the guard gives, as its findings spell them.
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


def test_the_guard_wraps_the_call_of_a_suite_test(
    request: pytest.FixtureRequest,
) -> None:
    conftest = _suite_conftest(request.config)
    guards = [
        hookimpl
        for hookimpl in request.node.ihook.pytest_runtest_call.get_hookimpls()
        if hookimpl.plugin is conftest and hookimpl.function.__name__ == _GUARD
    ]
    assert len(guards) == 1, guards
    assert guards[0].wrapper, "the guard has to run around the call, before the body"
    assert guards[0].trylast, "the guard has to be the last wrapper to start"


def test_a_suite_test_meets_the_guard(request: pytest.FixtureRequest) -> None:
    conftest = _suite_conftest(request.config)
    assert conftest._REAL_HOMES, "the guard captured no real home"
    assert conftest._real_home_findings(conftest._current_locations()) == []


def test_only_a_real_home_and_its_apothem_folders_count(
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
    # The Windows temporary folder sits below the home; so does any other folder.
    assert real("AppData", "Local", "Temp", "pytest-of-x", "user-home0") is None
    assert real("work", "repo") is None
    assert real(".config") is None
    assert real(".apothem-other") is None


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
        timeout=600,
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
    pytester folder never land in a home. The repo root goes on ``sys.path`` for
    ``-p tests.conftest``.
    """
    home = tmp_path_factory.mktemp("fake-real-home")
    for name in ("HOME", "USERPROFILE"):
        monkeypatch.setenv(name, str(home))
    for name in ("HOMEDRIVE", "HOMEPATH"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.syspath_prepend(os.environ[_REPO_VARIABLE])
    pytester.makeini("[pytest]\n")
    pytester.makepyfile(test_probe=_PROBES)
    return home


def _run(pytester: pytest.Pytester, *args: str) -> pytest.RunResult:
    return pytester.runpytest("-p", "no:cacheprovider", *args)


def _bodies_that_ran(pytester: pytest.Pytester) -> list[str]:
    return [name for name in _SENTINELS if (pytester.path / name).exists()]


def _flagged(result: pytest.RunResult) -> set[str]:
    """Return every name the guard's findings gave, over all failed tests."""
    names: set[str] = set()
    for line in result.outlines:
        if line.startswith("  - "):
            listed, _, _ = line[len("  - ") :].partition(": ")
            names.update(listed.split(", "))
    return names


def case_a_star_import_without_isolation_stops_both_bodies(
    pytester: pytest.Pytester, fake_real_home: Path
) -> None:
    pytester.makeconftest(_STAR_IMPORT)

    result = _run(pytester)

    result.assert_outcomes(failed=2)
    assert _bodies_that_ran(pytester) == []
    output = result.stdout.str()
    assert output.count("real-home guard: stopped before the test body ran") == 2
    assert _flagged(result) == _HOME_NAMES | _FOLDER_NAMES | _ROOT_NAMES, output
    assert f"{fake_real_home} is the real home" in output, output


def case_a_star_import_with_its_own_home_is_stopped_for_the_two_roots(
    pytester: pytest.Pytester, fake_real_home: Path
) -> None:
    """tests/conftest.py bound the ledger and backup roots from the real home."""
    pytester.makeconftest(_STAR_IMPORT + _OWN_HOME)

    result = _run(pytester)

    result.assert_outcomes(failed=2)
    assert _bodies_that_ran(pytester) == []
    assert _flagged(result) == _ROOT_NAMES, result.stdout.str()
    assert str(fake_real_home / ".apothem") in result.stdout.str()


def case_a_star_import_that_hands_the_manifest_the_real_home_is_stopped(
    pytester: pytest.Pytester, fake_real_home: Path
) -> None:
    pytester.makeconftest(_STAR_IMPORT + _OWN_HOME + _OWN_ROOTS + _REAL_MANIFEST_HOME)

    result = _run(pytester)

    result.assert_outcomes(failed=2)
    assert _bodies_that_ran(pytester) == []
    assert _flagged(result) == {
        "propagation.user_home()",
        "the support folder ~/.config/apothem",
    }, result.stdout.str()


def case_a_star_import_with_its_own_home_and_roots_runs(
    pytester: pytest.Pytester, fake_real_home: Path
) -> None:
    """The temporary folders sit inside the real home, as on Windows: allowed."""
    pytester.makeconftest(_STAR_IMPORT + _OWN_HOME + _OWN_ROOTS)

    result = _run(pytester, f"--basetemp={fake_real_home / 'temp'}")

    result.assert_outcomes(passed=2)
    assert _bodies_that_ran(pytester) == list(_SENTINELS)


def case_the_conftest_loaded_as_a_plugin_isolates_and_runs(
    pytester: pytest.Pytester, fake_real_home: Path
) -> None:
    """The temporary folders sit inside the real home, as on Windows: allowed."""
    result = _run(
        pytester, "-p", "tests.conftest", f"--basetemp={fake_real_home / 'temp'}"
    )

    result.assert_outcomes(passed=2)
    assert _bodies_that_ran(pytester) == list(_SENTINELS)


def case_the_conftest_loaded_as_a_plugin_stops_a_fixture_that_undoes_it(
    pytester: pytest.Pytester, fake_real_home: Path
) -> None:
    pytester.makeconftest(_REAL_HOME_AGAIN)

    result = _run(pytester, "-p", "tests.conftest")

    result.assert_outcomes(failed=2)
    assert _bodies_that_ran(pytester) == []
    assert _flagged(result) == _HOME_NAMES | _FOLDER_NAMES, result.stdout.str()
    assert f"{fake_real_home} is the real home" in result.stdout.str()
