# SPDX-License-Identifier: MIT

"""Plain-script invocation regression for the conformity-gate hook.

Harness deployments invoke the gate by absolute file path
(``${PYTHON_BIN} ${HARNESS_ROOT}/.apothem/support/conformity/gate.py --hook``), not as
a package module — so ``sys.path`` starts without the directory containing the
``apothem`` package. Before the module-level bootstrap in ``gate.py``, every
matcher importing ``apothem.*`` raised ModuleNotFoundError into the fail-open
isolation boundary: 18 of the 22 per-Write matchers silently no-opped and the
deployed hook degraded to the stdlib-only subset. These tests reproduce the
deployed invocation shape (plain script path, no PYTHONPATH) and pin the
repaired behavior: every registered matcher loads, and an apothem-importing
matcher produces a real finding.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_GATE_SCRIPT = _REPO_ROOT / "src" / "apothem" / "conformity" / "gate.py"

# Content that trips matchers which import the apothem package
# (file_header_grep: missing SPDX header) alongside a stdlib-only matcher
# (bare_except_grep: the bare ``except:`` clause).
_TRIPWIRE_CONTENT = "try:\n    pass\nexcept:\n    pass\n"


def _run_gate_as_plain_script(tmp_path: Path) -> dict:
    """Invoke gate.py exactly as a deployed hook does and return the report."""
    scope = tmp_path / "scope"
    scope.mkdir()
    payload = {
        "tool_input": {
            "file_path": str(scope / "tripwire.py"),
            "content": _TRIPWIRE_CONTENT,
        }
    }
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    env["APOTHEM_CONFORMITY_SCOPE"] = str(scope)
    completed = subprocess.run(
        [sys.executable, str(_GATE_SCRIPT), "--hook"],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=False,
        encoding="utf-8",
        env=env,
    )
    assert completed.stdout, completed.stderr
    return json.loads(completed.stdout)


def test_plain_script_hook_loads_every_matcher(tmp_path: Path) -> None:
    """No matcher errors into the fail-open boundary under script invocation."""
    report = _run_gate_as_plain_script(tmp_path)
    errored = [i["grep"] for i in report["invocations"] if i.get("error")]
    assert errored == [], (
        "matchers failed to load under plain-script invocation "
        f"(the deployed hook shape): {errored}"
    )
    assert report["grep_count"] == len(report["invocations"]) > 0


def test_plain_script_hook_matches_package_invocation_findings(
    tmp_path: Path,
) -> None:
    """An apothem-importing matcher reports findings, same as package mode."""
    report = _run_gate_as_plain_script(tmp_path)
    finding_greps = {i["grep"] for i in report["invocations"] if i.get("findings")}
    # file_header_grep imports the apothem package; bare_except_grep is
    # stdlib-only. Both must fire on the tripwire content.
    assert "file_header_grep" in finding_greps
    assert "bare_except_grep" in finding_greps
    assert report["passed"] is False


def _run_standalone_from(
    tmp_path: Path, work: Path, pythonpath: str | None
) -> tuple[bool, str]:
    """Run the naming-grep validator through the gate from the folder *work*.

    The helper process starts in a clean folder and changes into *work* only
    after its own imports, so the planted modules reach the validator child
    alone.
    """
    code = (
        "import sys; sys.path[:1] = []; sys.path.insert(0, "
        + repr(str(_REPO_ROOT / "src"))
        + ")\n"
        "import json\n"
        "from pathlib import Path\n"
        "from apothem.conformity import gate\n"
        "print(json.dumps(gate._run_standalone('naming-grep', Path(sys.argv[1]))))\n"
    )
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    if pythonpath is not None:
        env["PYTHONPATH"] = pythonpath
    completed = subprocess.run(
        [sys.executable, "-c", code, str(tmp_path), str(work)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert completed.returncode == 0, completed.stderr
    passed, output = json.loads(completed.stdout.strip().splitlines()[-1])
    return passed, output


@pytest.mark.parametrize(
    "pythonpath",
    [None, os.pathsep + "/nonexistent", "/nonexistent" + os.pathsep, "."],
    ids=["unset", "leading-empty", "trailing-empty", "relative"],
)
def test_standalone_validators_ignore_modules_in_the_current_folder(
    tmp_path: Path, pythonpath: str | None
) -> None:
    """A planted ``json.py`` / ``runpy.py`` in the cwd never runs in the launcher.

    Guards GHSA-4rh9-7m5x-94j9: the standalone-validator subprocess starts with
    ``-c``, which puts the working directory first on ``sys.path``; an empty or
    relative entry in the user's ``PYTHONPATH`` does the same, so those are
    dropped from the child's environment. The validator must also really run.
    """
    marker = tmp_path / "marker"
    work = tmp_path / "work"
    work.mkdir()
    body = f"from pathlib import Path\nPath({str(marker)!r}).write_text('ran')\n"
    for name in ("json.py", "runpy.py", "sitecustomize.py"):
        (work / name).write_text(body, encoding="utf-8")
    passed, output = _run_standalone_from(tmp_path, work, pythonpath)
    assert not marker.exists(), "a module from the current folder ran"
    assert "Traceback" not in output, output
    assert "naming-grep" in output or "naming_grep" in output, output
    assert isinstance(passed, bool)


def _user_site(userbase: Path) -> Path | None:
    """Return the user site-packages folder under *userbase*, or ``None`` when off."""
    probe = subprocess.run(
        [
            sys.executable,
            "-c",
            "import site; print(site.ENABLE_USER_SITE); print(site.getusersitepackages())",
        ],
        env={**os.environ, "PYTHONUSERBASE": str(userbase)},
        capture_output=True,
        text=True,
        check=True,
    )
    enabled, folder = probe.stdout.strip().splitlines()[-2:]
    return Path(folder) if enabled == "True" else None


def test_standalone_validators_start_with_e_and_s(tmp_path: Path) -> None:
    """No ``PYTHONPATH`` entry and no user site-packages folder runs in a child.

    The gate runs by path with ``-E -s``, so the parent reads neither; a marker
    can only come from a validator child. A full-path ``PYTHONPATH`` entry
    holding ``sitecustomize.py`` and a user site holding ``usercustomize.py``
    must not run there, and the validator must still run.
    """
    marks = tmp_path / "marks"
    marks.mkdir()
    body = (
        "import os, pathlib\n"
        f"pathlib.Path({str(marks)!r}, __name__ + str(os.getpid())).write_text('ran')\n"
    )
    plant = tmp_path / "plant"
    plant.mkdir()
    (plant / "sitecustomize.py").write_text(body, encoding="utf-8")
    userbase = tmp_path / "userbase"
    user_site = _user_site(userbase)
    if user_site is not None:
        user_site.mkdir(parents=True)
        (user_site / "usercustomize.py").write_text(body, encoding="utf-8")
    project = tmp_path / "project"
    project.mkdir()
    env = {
        **os.environ,
        "PYTHONPATH": str(plant),
        "PYTHONUSERBASE": str(userbase),
    }
    env.pop("PYTHONSAFEPATH", None)
    completed = subprocess.run(
        [sys.executable, "-E", "-s", str(_GATE_SCRIPT), "--check", "naming-grep", "."],
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        encoding="utf-8",
        timeout=120,
    )
    assert sorted(path.name for path in marks.iterdir()) == []
    assert "Traceback" not in completed.stdout + completed.stderr, completed.stderr
    assert "naming" in completed.stdout, completed.stdout


def test_standalone_env_keeps_only_absolute_pythonpath_entries(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The child's PYTHONPATH holds the absolute entries only, or is absent."""
    from apothem.conformity import gate

    absolute = str(tmp_path)
    monkeypatch.setenv(
        "PYTHONPATH", os.pathsep.join(["", "rel", absolute, ".", "", absolute + "x"])
    )
    env = gate._standalone_env()
    assert env["PYTHONPATH"] == os.pathsep.join([absolute, absolute + "x"])
    assert env["PYTHONSAFEPATH"] == "1"
    monkeypatch.setenv("PYTHONPATH", os.pathsep + "rel")
    assert "PYTHONPATH" not in gate._standalone_env()


@pytest.mark.parametrize(
    ("entry", "windows", "kept"),
    [
        ("C:\\lib", True, True),
        ("c:/lib", True, True),
        ("\\\\server\\share\\lib", True, True),
        ("//server/share/lib", True, True),
        ("\\lib", True, False),
        ("/lib", True, False),
        ("C:rel", True, False),
        ("C:", True, False),
        ("rel", True, False),
        (".", True, False),
        ("/lib", False, True),
        ("rel", False, False),
        ("C:\\lib", False, False),
    ],
)
def test_full_path_entry_rule(entry: str, windows: bool, kept: bool) -> None:
    """One rule: a drive path or network path on Windows, a leading ``/`` elsewhere."""
    from apothem.conformity import gate

    assert gate._is_full_path_entry(entry, windows=windows) is kept
