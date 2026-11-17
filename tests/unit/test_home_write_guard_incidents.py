# SPDX-License-Identifier: MIT

"""A test run that skips ``tests/conftest.py`` still cannot write the real home.

Three ways of running a copied test file once sent installs into a developer's
real home: from a folder under ``.audit/`` with ``-c`` on the null device,
``-o addopts=`` and ``--rootdir`` there; from a scratch folder with its own
``pytest.ini``, where the test's fixture moved only ``HOME``; and as a single
file with ``--rootdir .``. None of them loads ``tests/conftest.py``, so the
install records, backup sets and tool folders bind to the home at import.
``apothem.lib.home_write_guard`` now refuses those writes in the product.

Each ``case_*`` function below rebuilds one of them with ``pytester`` and runs
it in a child pytest process. The real home is never named: the case points
``HOME`` and ``USERPROFILE`` at a fake account home under the pytester folder,
clears every variable that moves an Apothem root, and hands the child a plugin
(``fake_account_home``) that protects the fake home with ``also_protect_home``.
The probe test then runs the Codex and Claude Code installs, as the incident
tests did, and must fail with ``RealHomeWriteError`` while the fake home keeps
exactly the file the case put there. The control case runs the same probe
without the plugin and must write a ledger into the fake home and pass, which
shows the probe reaches the writers: a broken guard shows up as files in the
fake home, never in the real one.

``test_the_pytester_cases_pass`` runs the cases in a pytest session of their
own (``python -m pytest -p pytester`` on a copy of this file), so the
``pytester`` plugin stays out of the suite's session, and that session has a
fake home of its own too.

Every session started here has its own temporary folder (``TMP``, ``TEMP`` and
``TMPDIR``) and ``--basetemp`` under the folder that runs it, and each case
session gets ``--confcutdir`` on the pytester folder. Without that, ``-c`` on
the null device leaves pytest no folder to stop at (on Windows it reads the
null device as ``\\\\.\\nul``, which has no parent), so collection walks up
through every parent folder of the probe and lists the shared temporary folder,
where other processes create and remove folders while it reads.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

#: Hands the repo root to the session that runs the cases.
_REPO_VARIABLE = "APOTHEM_HOME_WRITE_GUARD_REPO"
_REPO_ROOT = Path(os.environ.get(_REPO_VARIABLE) or Path(__file__).resolve().parents[2])
#: The functions the case session collects, and the suite does not.
_CASE_PREFIX = "case_"
#: Variables that move an Apothem root away from the home; every child drops them.
_ROOT_VARIABLES = (
    "HOMEDRIVE",
    "HOMEPATH",
    "CODEX_HOME",
    "CLAUDE_CONFIG_DIR",
    "CLAUDE_PLUGIN_DATA",
    "XDG_CONFIG_HOME",
    "XDG_STATE_HOME",
    "XDG_DATA_HOME",
    "XDG_CACHE_HOME",
    "OPENCODE_CONFIG_DIR",
    "OPENCODE_CONFIG",
    "APOTHEM_HOOK_STATE_DIR",
)

#: The variables ``tempfile`` reads; every session gets a folder of its own.
_TEMPORARY_VARIABLES = ("TMP", "TEMP", "TMPDIR")

#: The file an incident overwrote, put in the fake home before the probe runs.
_RULES_FILE = (".config", "apothem", "rules", "harness-adapter-shape-schemas.md")
_RULES_BYTES = b"the operator's own copy\n"

#: The probe test: no conftest, Apothem imported at collection, as in the incidents.
_PROBE = """
from apothem.harnesses.claude_code import ClaudeCodeAdapter
from apothem.harnesses.codex import CodexAdapter


def test_install_into_the_home():
    CodexAdapter().install({})
    ClaudeCodeAdapter().install({})
"""

#: The second incident's fixture: it moves HOME only and leaves USERPROFILE.
_HOME_ONLY_FIXTURE = """
from pathlib import Path

import pytest

HERE = Path(__file__).parent


@pytest.fixture(autouse=True)
def _home_only(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    (HERE / "probe-home.txt").write_text(str(home), encoding="utf-8")
    monkeypatch.setenv("HOME", str(home))
"""


def test_the_pytester_cases_pass(tmp_path: Path) -> None:
    """Run the ``case_*`` functions below in a pytest session of their own."""
    session = tmp_path / "session"
    session.mkdir()
    module = session / Path(__file__).name
    shutil.copyfile(__file__, module)
    # An empty ini roots the session here, away from the repo's pytest settings.
    (session / "pytest.ini").write_bytes(b"[pytest]\n")
    home = tmp_path / "session-home"
    home.mkdir()
    temporary = tmp_path / "session-tmp"
    temporary.mkdir()
    env = {
        name: value
        for name, value in os.environ.items()
        if not name.startswith("PYTEST_") and name not in _ROOT_VARIABLES
    }
    env.update(
        {
            "HOME": str(home),
            "USERPROFILE": str(home),
            **dict.fromkeys(_TEMPORARY_VARIABLES, str(temporary)),
            _REPO_VARIABLE: str(_REPO_ROOT),
            "PYTHONPATH": os.pathsep.join((str(_REPO_ROOT / "src"), str(_REPO_ROOT))),
            # Keeps the sessions from writing bytecode into the checkout.
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    )
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


# --- In the case session --------------------------------------------------------


@pytest.fixture
def fake_home(pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the home at a fake account home that holds one operator file.

    The file is written here, by the case, before any Apothem code runs. The
    probe session also gets a temporary folder of its own.
    """
    temporary = pytester.path / "tmp"
    temporary.mkdir()
    for name in _TEMPORARY_VARIABLES:
        monkeypatch.setenv(name, str(temporary))
    home = pytester.path / "account-home"
    rules = home.joinpath(*_RULES_FILE)
    rules.parent.mkdir(parents=True)
    rules.write_bytes(_RULES_BYTES)
    for name in ("HOME", "USERPROFILE"):
        monkeypatch.setenv(name, str(home))
    for name in _ROOT_VARIABLES:
        monkeypatch.delenv(name, raising=False)
    return home


def _protect(folder: Path, home: Path) -> None:
    """Write the plugin that protects *home* into *folder*, the child's cwd."""
    (folder / "fake_account_home.py").write_text(
        "from apothem.lib import home_write_guard\n\n"
        f"home_write_guard.also_protect_home({str(home)!r})\n",
        encoding="utf-8",
    )


def _run(pytester: pytest.Pytester, *args: str) -> pytest.RunResult:
    """Run a probe session that looks for conftests and tests only in its folder.

    ``runpytest_subprocess`` adds a ``--basetemp`` under the pytester folder.
    """
    return pytester.runpytest_subprocess(
        "--confcutdir", str(pytester.path), *args, timeout=600
    )


def _snapshot(folder: Path) -> dict[str, bytes | None]:
    return {
        path.relative_to(folder).as_posix(): (
            path.read_bytes() if path.is_file() else None
        )
        for path in sorted(folder.rglob("*"))
    }


def _untouched() -> dict[str, bytes | None]:
    return {
        ".config": None,
        ".config/apothem": None,
        ".config/apothem/rules": None,
        "/".join(_RULES_FILE): _RULES_BYTES,
    }


def _assert_refused(result: pytest.RunResult, home: Path) -> None:
    # First: a guard that let the install through shows up as files here.
    written = sorted(set(_snapshot(home)) - set(_untouched()))
    assert written == [], f"the probe wrote into the fake home: {written[:5]}"
    assert _snapshot(home) == _untouched()
    output = "\n".join((*result.outlines, *result.errlines))
    assert "RealHomeWriteError" in output, output
    assert str(home) in output, output
    result.assert_outcomes(failed=1)


def case_incident_1_audit_folder_with_null_config(
    pytester: pytest.Pytester, fake_home: Path
) -> None:
    run = pytester.path / ".audit" / "run"
    run.mkdir(parents=True)
    probe = run / "test_probe.py"
    probe.write_text(_PROBE, encoding="utf-8")
    _protect(pytester.path, fake_home)
    result = _run(
        pytester,
        "-p",
        "fake_account_home",
        "-o",
        "addopts=",
        "--rootdir",
        str(run),
        "-c",
        os.devnull,
        str(probe),
    )
    _assert_refused(result, fake_home)


def case_incident_2_scratch_ini_and_a_fixture_that_moves_only_home(
    pytester: pytest.Pytester, fake_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scratch = pytester.path / "scratch"
    scratch.mkdir()
    (scratch / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    (scratch / "test_probe.py").write_text(
        _HOME_ONLY_FIXTURE + _PROBE, encoding="utf-8"
    )
    _protect(scratch, fake_home)
    monkeypatch.chdir(scratch)
    result = _run(
        pytester,
        "-p",
        "fake_account_home",
        "-c",
        "pytest.ini",
        "--rootdir",
        ".",
        "test_probe.py",
    )
    _assert_refused(result, fake_home)
    probe_home = Path((scratch / "probe-home.txt").read_text(encoding="utf-8"))
    assert not (probe_home / ".apothem").exists()


def case_incident_3_single_file_with_rootdir(
    pytester: pytest.Pytester, fake_home: Path
) -> None:
    probe = pytester.path / "test_probe.py"
    probe.write_text(_PROBE, encoding="utf-8")
    _protect(pytester.path, fake_home)
    result = _run(pytester, "-p", "fake_account_home", "--rootdir", ".", probe.name)
    _assert_refused(result, fake_home)


def case_control_without_the_plugin_the_probe_writes_the_fake_home(
    pytester: pytest.Pytester, fake_home: Path
) -> None:
    probe = pytester.path / "test_probe.py"
    probe.write_text(_PROBE, encoding="utf-8")
    result = _run(pytester, "--rootdir", ".", probe.name)
    result.assert_outcomes(passed=1)
    ledgers = sorted((fake_home / ".apothem" / "state").rglob("ledger.jsonl"))
    assert [ledger.parent.name for ledger in ledgers] == ["claude_code", "codex"]
    assert (fake_home / ".claude").is_dir()
