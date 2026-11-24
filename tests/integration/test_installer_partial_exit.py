# SPDX-License-Identifier: MIT

"""The installers and updaters finish a partial engine run and end with code 2.

``apothem install`` and ``apothem update`` exit with code 2 (``status``
``partial``) when they leave a file Apothem keeps its block in as it is
because of its marker lines, after writing the rest of the install, or when
they stop after they have written something (a harness fails after an
earlier one in an ``APOTHEM_HARNESS=all`` batch wrote its files). The
one-shot scripts (``install.sh``, ``install.ps1``, ``update.sh`` and
``update.ps1``) read that code as partial: each prints one warning line, goes
on as on success (verify, the ``apothem`` shim and the next-step banner for
the installers, the closing line for the updaters) and ends with code 2. A
piped PowerShell run (``irm ... | iex``) has no script file, and ``exit``
there would close the session it runs in, so it leaves ``$LASTEXITCODE`` at 2
and the session open. Any other non-zero code stops the script as before.

Each test runs the real script against a stand-in engine: a checkout named by
``APOTHEM_SOURCE`` whose ``apothem/__main__.py`` records its arguments and,
for ``install`` and ``update``, exits with the code in
``APOTHEM_TEST_ENGINE_EXIT``; ``verify`` exits 0. The sh scripts run under
``sh`` on POSIX hosts and under Git for Windows' bash on Windows. An
``install.ps1`` run that places its ``.cmd`` shim runs on Windows only.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tests._shared.bash_resolver import find_test_bash
from tests._shared.python_shim import write_python_shim

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLER = REPO_ROOT / "scripts" / "installer"
HARNESS = "claude-code"
TIMEOUT_SECONDS = 300

#: The one line each script prints when the engine ends as partial.
PARTIAL_WARNING = (
    "The engine ended as partial (exit code 2): its messages above say which "
    "files it left as they are, or which harness stopped. Fix what they name, "
    f"then run 'apothem update --harness {HARNESS}' again."
)

#: The stand-in engine. ``print`` ends each record with a newline.
STAND_IN_ENGINE = """\
# SPDX-License-Identifier: MIT
import json
import os
import sys

with open(os.environ["APOTHEM_TEST_RECORD"], "a", encoding="utf-8") as record:
    print(json.dumps(sys.argv[1:]), file=record)
if sys.argv[1:2] in (["install"], ["update"]):
    sys.exit(int(os.environ["APOTHEM_TEST_ENGINE_EXIT"]))
"""

#: Exit codes the engine uses for a failed run: an expected error and a
#: usage error. The scripts stop on each, as they always have.
FAILED_RUN_CODES = [pytest.param(1, id="exit-1"), pytest.param(64, id="exit-64")]


def _shell() -> str | None:
    """``sh`` on POSIX hosts; Git for Windows' bash on Windows."""
    if sys.platform == "win32":
        return find_test_bash()
    return shutil.which("sh")


SHELL = _shell()
PWSH = shutil.which("pwsh") or shutil.which("powershell")

requires_sh = pytest.mark.skipif(SHELL is None, reason="no sh (or Git Bash) here")
requires_pwsh = pytest.mark.skipif(PWSH is None, reason="no PowerShell on this host")
requires_windows = pytest.mark.skipif(
    sys.platform != "win32", reason="the installer writes a .cmd shim on Windows"
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _stand_in_checkout(root: Path) -> Path:
    """A source tree whose engine is the stand-in, for ``APOTHEM_SOURCE``."""
    _write(root / "pyproject.toml", '[project]\nname = "stand-in"\n')
    _write(root / "src" / "apothem" / "__init__.py", "")
    _write(root / "src" / "apothem" / "__main__.py", STAND_IN_ENGINE)
    return root


def _profile(tmp_path: Path) -> Path:
    profile = tmp_path / "profile.yaml"
    _write(profile, "identity: {}\n")
    return profile


def _test_env(tmp_path: Path, engine_exit: int) -> dict[str, str]:
    """The host environment without Apothem or Python settings, plus the
    stand-in engine's record file and exit code."""
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith(("APOTHEM_", "PYTHON", "PIP_"))
    }
    env.update(
        {
            "NO_COLOR": "1",
            "PIP_NO_INDEX": "1",
            "PIP_CONFIG_FILE": os.devnull,
            "APOTHEM_TEST_RECORD": str(tmp_path / "engine-runs.jsonl"),
            "APOTHEM_TEST_ENGINE_EXIT": str(engine_exit),
        }
    )
    return env


def _engine_runs(tmp_path: Path) -> list[list[str]]:
    """The arguments of each engine run, in order."""
    record = tmp_path / "engine-runs.jsonl"
    if not record.is_file():
        return []
    return [
        json.loads(line) for line in record.read_text(encoding="utf-8").splitlines()
    ]


def _squashed(text: str) -> str:
    """TEXT without whitespace: Windows PowerShell 5.1 wraps long lines."""
    return re.sub(r"\s+", "", text)


def _output(result: subprocess.CompletedProcess[str]) -> str:
    return result.stdout + result.stderr


# --- install.sh and update.sh ----------------------------------------------


def _sh_path(path: Path) -> str:
    """PATH as the sh scripts read it: unchanged on POSIX, /c/... under Git Bash."""
    if sys.platform != "win32":
        return str(path)
    drive, rest = path.drive, path.as_posix()[len(path.drive) :]
    return f"/{drive[0].lower()}{rest}"


def _run_sh(
    tmp_path: Path, script: str, *args: str, engine_exit: int
) -> subprocess.CompletedProcess[str]:
    """Run SCRIPT from scripts/installer with ARGS against the stand-in engine.

    A driver program exports the script's folders (under TMP_PATH) in the
    form the shell reads, puts the test's Python first on PATH as
    ``python3``, and runs the script under ``sh``; its exit code is the
    script's.
    """
    assert SHELL is not None
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    python_dir = tmp_path / "python-shim"
    python_dir.mkdir(exist_ok=True)
    write_python_shim(python_dir / "python3")
    exports = {
        "HOME": home,
        "APOTHEM_HOME": tmp_path / "apothem-home",
        "APOTHEM_SOURCE": _stand_in_checkout(tmp_path / "checkout"),
        "APOTHEM_BIN_DIR": tmp_path / "bin",
        "APOTHEM_PROFILE": _profile(tmp_path),
    }
    lines = [
        f"export {name}={shlex.quote(_sh_path(value))}"
        for name, value in exports.items()
    ]
    lines.append(f'export PATH={shlex.quote(_sh_path(python_dir))}:"$PATH"')
    lines.append(shlex.join(["sh", _sh_path(INSTALLER / script), *args]))
    driver = tmp_path / "driver.sh"
    _write(driver, "\n".join(lines) + "\n")
    return subprocess.run(
        [SHELL, _sh_path(driver)],
        cwd=str(tmp_path),
        env=_test_env(tmp_path, engine_exit),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=TIMEOUT_SECONDS,
        check=False,
    )


@requires_sh
def test_install_sh_finishes_a_partial_install_and_exits_2(tmp_path: Path) -> None:
    """install.sh warns once, runs verify, places the shim, prints the banner
    and ends with code 2 when the engine install exits 2."""
    result = _run_sh(tmp_path, "install.sh", engine_exit=2)

    out = _output(result)
    assert result.returncode == 2, out
    assert _squashed(PARTIAL_WARNING) in _squashed(out), out
    assert out.count("exit code 2") == 1, out
    assert f"Harness {HARNESS} installed" not in out, out
    assert [run[0] for run in _engine_runs(tmp_path)] == ["install", "verify"], out
    assert "verify passed" in out, out
    assert (tmp_path / "bin" / "apothem").is_file(), out
    assert "Installation complete." in out, out


@requires_sh
def test_install_sh_dry_run_warns_and_exits_2(tmp_path: Path) -> None:
    """A dry run whose engine exits 2 warns, says the dry run is complete and
    ends with code 2; it runs no verify and places no shim."""
    result = _run_sh(tmp_path, "install.sh", "--dry-run", engine_exit=2)

    out = _output(result)
    assert result.returncode == 2, out
    assert _squashed(PARTIAL_WARNING) in _squashed(out), out
    assert "Dry-run complete" in out, out
    runs = _engine_runs(tmp_path)
    assert [run[0] for run in runs] == ["install"], out
    assert "--dry-run" in runs[0], runs
    assert not (tmp_path / "bin" / "apothem").exists(), out


@requires_sh
@pytest.mark.parametrize("code", FAILED_RUN_CODES)
def test_install_sh_still_stops_on_a_failed_engine_run(
    tmp_path: Path, code: int
) -> None:
    """Any other non-zero code ends install.sh with that code, before verify,
    the shim and the banner, and with no partial warning."""
    result = _run_sh(tmp_path, "install.sh", engine_exit=code)

    out = _output(result)
    assert result.returncode == code, out
    assert "exit code 2" not in out, out
    assert [run[0] for run in _engine_runs(tmp_path)] == ["install"], out
    assert not (tmp_path / "bin" / "apothem").exists(), out
    assert "Installation complete." not in out, out


@requires_sh
def test_update_sh_finishes_a_partial_update_and_exits_2(tmp_path: Path) -> None:
    """update.sh warns once, prints its closing line and ends with code 2
    when the engine update exits 2."""
    result = _run_sh(tmp_path, "update.sh", engine_exit=2)

    out = _output(result)
    assert result.returncode == 2, out
    assert _squashed(PARTIAL_WARNING) in _squashed(out), out
    assert out.count("exit code 2") == 1, out
    assert f"Harness {HARNESS} updated" not in out, out
    assert [run[0] for run in _engine_runs(tmp_path)] == ["update"], out
    assert "Update complete." in out, out


@requires_sh
@pytest.mark.parametrize("code", FAILED_RUN_CODES)
def test_update_sh_still_stops_on_a_failed_engine_run(
    tmp_path: Path, code: int
) -> None:
    result = _run_sh(tmp_path, "update.sh", engine_exit=code)

    out = _output(result)
    assert result.returncode == code, out
    assert "exit code 2" not in out, out
    assert "Update complete." not in out, out


# --- install.ps1 and update.ps1 --------------------------------------------


def _ps_env(tmp_path: Path, engine_exit: int) -> dict[str, str]:
    """The PowerShell scripts' environment: an isolated home and temp folder,
    the stand-in source, the shim folder and an existing profile."""
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    temp = tmp_path / "temp"
    temp.mkdir(exist_ok=True)
    env = _test_env(tmp_path, engine_exit)
    env.update(
        {
            "HOME": str(home),
            "USERPROFILE": str(home),
            "TMPDIR": str(temp),
            "TEMP": str(temp),
            "TMP": str(temp),
            "APOTHEM_HOME": str(tmp_path / "apothem-home"),
            "APOTHEM_SOURCE": str(_stand_in_checkout(tmp_path / "checkout")),
            "APOTHEM_BIN_DIR": str(tmp_path / "bin"),
            "APOTHEM_PROFILE": str(_profile(tmp_path)),
        }
    )
    return env


def _pwsh(
    args: list[str], tmp_path: Path, env: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    assert PWSH is not None
    return subprocess.run(
        [PWSH, "-NoProfile", "-ExecutionPolicy", "Bypass", *args],
        cwd=str(tmp_path),
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=TIMEOUT_SECONDS,
        check=False,
    )


def _run_ps1_by_path(
    tmp_path: Path, script: str, *flags: str, engine_exit: int
) -> subprocess.CompletedProcess[str]:
    env = _ps_env(tmp_path, engine_exit)
    return _pwsh(["-File", str(INSTALLER / script), *flags], tmp_path, env)


def _run_ps1_piped(
    tmp_path: Path, script: str, *flags: str, engine_exit: int
) -> subprocess.CompletedProcess[str]:
    """Run SCRIPT's text the way the one-liner does, with no script file:
    piped into Invoke-Expression, or, to pass FLAGS, as a script block made
    from the text. Then print $LASTEXITCODE, which shows that the run left
    the session open and what code it left."""
    env = {
        **_ps_env(tmp_path, engine_exit),
        "APOTHEM_TEST_SCRIPT": str(INSTALLER / script),
    }
    text = "Get-Content -Raw -LiteralPath $env:APOTHEM_TEST_SCRIPT"
    if flags:
        command = f"& ([scriptblock]::Create(({text}))) {' '.join(flags)}"
    else:
        command = f"{text} | Invoke-Expression"
    command += '; "SESSION-OPEN LASTEXITCODE=[$LASTEXITCODE]"'
    return _pwsh(["-Command", command], tmp_path, env)


def _run_ps1_in_strict_caller(
    tmp_path: Path, script: str, how: str, *, engine_exit: int
) -> subprocess.CompletedProcess[str]:
    """Run SCRIPT from a session that sets
    $PSNativeCommandUseErrorActionPreference to $true (PowerShell 7.4+), piped
    into Invoke-Expression or by path (HOW), then print $LASTEXITCODE and the
    session's preference."""
    env = {
        **_ps_env(tmp_path, engine_exit),
        "APOTHEM_TEST_SCRIPT": str(INSTALLER / script),
    }
    if how == "piped":
        run = (
            "Get-Content -Raw -LiteralPath $env:APOTHEM_TEST_SCRIPT | Invoke-Expression"
        )
    else:
        run = "& $env:APOTHEM_TEST_SCRIPT"
    command = (
        "$PSNativeCommandUseErrorActionPreference = $true; "
        f"{run}; "
        '"CALLER LASTEXITCODE=[$LASTEXITCODE] '
        'NATIVE=[$PSNativeCommandUseErrorActionPreference]"'
    )
    return _pwsh(["-Command", command], tmp_path, env)


@requires_pwsh
@pytest.mark.parametrize("how", ["piped", "by-path"])
@pytest.mark.parametrize(
    ("script", "closing"),
    [
        pytest.param(
            "install.ps1",
            "Installation complete.",
            marks=requires_windows,
            id="install.ps1",
        ),
        pytest.param("update.ps1", "Update complete.", id="update.ps1"),
    ],
)
def test_ps1_finishes_a_partial_run_when_the_caller_stops_on_native_errors(
    tmp_path: Path, script: str, closing: str, how: str
) -> None:
    """A caller that sets $PSNativeCommandUseErrorActionPreference = $true
    still gets the partial run finished with $LASTEXITCODE at 2, and keeps
    its preference as it was."""
    result = _run_ps1_in_strict_caller(tmp_path, script, how, engine_exit=2)

    out = _output(result)
    assert "CALLER LASTEXITCODE=[2] NATIVE=[True]" in out, out
    assert _squashed(PARTIAL_WARNING) in _squashed(out), out
    assert closing in out, out


@requires_pwsh
@requires_windows
def test_install_ps1_by_path_finishes_a_partial_install_and_exits_2(
    tmp_path: Path,
) -> None:
    """install.ps1 run by path warns once, runs verify, places the shim,
    prints the banner and exits with code 2 when the engine install exits 2."""
    result = _run_ps1_by_path(tmp_path, "install.ps1", engine_exit=2)

    out = _output(result)
    assert result.returncode == 2, out
    assert _squashed(PARTIAL_WARNING) in _squashed(out), out
    assert "materialization failed" not in out, out
    assert f"Harness {HARNESS} installed" not in out, out
    assert [run[0] for run in _engine_runs(tmp_path)] == ["install", "verify"], out
    assert "verify passed" in out, out
    assert (tmp_path / "bin" / "apothem.cmd").is_file(), out
    assert "Installation complete." in out, out


@requires_pwsh
@requires_windows
def test_install_ps1_piped_leaves_the_session_open_with_lastexitcode_2(
    tmp_path: Path,
) -> None:
    """A piped install.ps1 run finishes the partial install and leaves the
    session open, with $LASTEXITCODE at 2."""
    result = _run_ps1_piped(tmp_path, "install.ps1", engine_exit=2)

    out = _output(result)
    assert "SESSION-OPEN LASTEXITCODE=[2]" in out, out
    assert _squashed(PARTIAL_WARNING) in _squashed(out), out
    assert [run[0] for run in _engine_runs(tmp_path)] == ["install", "verify"], out
    assert (tmp_path / "bin" / "apothem.cmd").is_file(), out
    assert "Installation complete." in out, out


@requires_pwsh
def test_install_ps1_dry_run_warns_and_exits_2(tmp_path: Path) -> None:
    """A dry run by path whose engine exits 2 warns, says the dry run is
    complete and exits with code 2, with no verify run."""
    result = _run_ps1_by_path(tmp_path, "install.ps1", "-DryRun", "-Yes", engine_exit=2)

    out = _output(result)
    assert result.returncode == 2, out
    assert _squashed(PARTIAL_WARNING) in _squashed(out), out
    assert "Dry-run complete" in out, out
    assert [run[0] for run in _engine_runs(tmp_path)] == ["install"], out


@requires_pwsh
def test_install_ps1_piped_dry_run_leaves_lastexitcode_2(tmp_path: Path) -> None:
    result = _run_ps1_piped(tmp_path, "install.ps1", "-DryRun", "-Yes", engine_exit=2)

    out = _output(result)
    assert "SESSION-OPEN LASTEXITCODE=[2]" in out, out
    assert _squashed(PARTIAL_WARNING) in _squashed(out), out
    assert "Dry-run complete" in out, out


@requires_pwsh
@pytest.mark.parametrize("code", FAILED_RUN_CODES)
def test_install_ps1_still_stops_on_a_failed_engine_run(
    tmp_path: Path, code: int
) -> None:
    """Any other non-zero code still stops install.ps1 with its failure
    message, before verify, the shim and the banner."""
    result = _run_ps1_by_path(tmp_path, "install.ps1", engine_exit=code)

    out = _output(result)
    assert result.returncode == 1, out
    assert f"Harness materialization failed for {HARNESS}" in out, out
    assert "exit code 2" not in out, out
    assert [run[0] for run in _engine_runs(tmp_path)] == ["install"], out
    assert not (tmp_path / "bin" / "apothem.cmd").exists(), out
    assert "Installation complete." not in out, out


@requires_pwsh
def test_update_ps1_by_path_finishes_a_partial_update_and_exits_2(
    tmp_path: Path,
) -> None:
    result = _run_ps1_by_path(tmp_path, "update.ps1", engine_exit=2)

    out = _output(result)
    assert result.returncode == 2, out
    assert _squashed(PARTIAL_WARNING) in _squashed(out), out
    assert "re-materialization failed" not in out, out
    assert f"Harness {HARNESS} updated" not in out, out
    assert [run[0] for run in _engine_runs(tmp_path)] == ["update"], out
    assert "Update complete." in out, out


@requires_pwsh
def test_update_ps1_piped_leaves_the_session_open_with_lastexitcode_2(
    tmp_path: Path,
) -> None:
    result = _run_ps1_piped(tmp_path, "update.ps1", engine_exit=2)

    out = _output(result)
    assert "SESSION-OPEN LASTEXITCODE=[2]" in out, out
    assert _squashed(PARTIAL_WARNING) in _squashed(out), out
    assert "Update complete." in out, out


@requires_pwsh
@pytest.mark.parametrize("code", FAILED_RUN_CODES)
def test_update_ps1_still_stops_on_a_failed_engine_run(
    tmp_path: Path, code: int
) -> None:
    result = _run_ps1_by_path(tmp_path, "update.ps1", engine_exit=code)

    out = _output(result)
    assert result.returncode == 1, out
    assert f"Harness re-materialization failed for {HARNESS}" in out, out
    assert "exit code 2" not in out, out
    assert "Update complete." not in out, out
