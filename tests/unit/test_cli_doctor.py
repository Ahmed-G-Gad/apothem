# SPDX-License-Identifier: MIT

"""``doctor`` judges installed harnesses only, verifies them, and probes hooks.

doctor used to exit 1 unless all 17 harnesses were installed, and it only
checked presence. A user with one healthy harness
always got a failure, so doctor could not gate a setup step, while a broken
hook runtime passed unnoticed. Now an uninstalled harness is informational;
an installed one must verify, and every hook command it registered must start
with a no-op payload.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from click.testing import CliRunner

import apothem
from apothem.cli import _doctor_hooks, main
from apothem.harnesses._shared import install_driver, wrapper_factories
from apothem.lib import install_ledger

_PROFILE = (
    "schema_version: 1\nidentity:\n  name: Ada Lovelace\n"
    "  email: ada@analytical.engine\n  github: adalovelace\n"
)


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.delenv("CODEX_HOME", raising=False)
    monkeypatch.setenv("APOTHEM_HOME", str(tmp_path / "apothem-home"))
    monkeypatch.setattr(install_driver, "BACKUP_ROOT", tmp_path / "backups")
    monkeypatch.chdir(tmp_path)
    profile = home / ".config" / "apothem" / "profile.yaml"
    profile.parent.mkdir(parents=True)
    profile.write_text(_PROFILE, encoding="utf-8")
    return home


def _doctor(runner: CliRunner, *options: str) -> tuple[int, dict]:
    result = runner.invoke(main, ["doctor", "--json", *options])
    return result.exit_code, json.loads(result.stdout)


def _install(runner: CliRunner, harness: str, *options: str) -> None:
    result = runner.invoke(main, ["install", "--harness", harness, "--json", *options])
    assert result.exit_code == 0, result.output


def _row(payload: dict, name: str) -> dict:
    return next(row for row in payload["harnesses"] if row["name"] == name)


def _project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    project.mkdir()
    return project


def test_doctor_passes_with_nothing_installed(runner: CliRunner, home: Path) -> None:
    code, payload = _doctor(runner)
    assert code == 0, payload
    assert payload["all_ok"] is True
    statuses = {row["status"] for row in payload["harnesses"]}
    # Project-scope harnesses are only judged when --project names a root.
    assert statuses == {"not_installed", "needs_project"}


def test_doctor_passes_after_a_single_harness_install(
    runner: CliRunner, home: Path
) -> None:
    _install(runner, "codex")
    code, payload = _doctor(runner)
    assert code == 0, payload
    assert payload["all_ok"] is True
    codex = _row(payload, "codex")
    assert codex["status"] == "ok"
    assert codex["verified"] is True
    assert codex["hooks"]["probed"] >= 1
    assert codex["hooks"]["failed"] == []
    assert _row(payload, "opencode")["status"] == "not_installed"


def test_doctor_fails_when_a_registered_hook_cannot_start(
    runner: CliRunner, home: Path
) -> None:
    _install(runner, "codex")
    dispatcher = home / ".codex" / "hooks" / "dispatch.py"
    assert dispatcher.is_file()
    dispatcher.write_text("raise SystemExit(3)\n", encoding="utf-8")

    code, payload = _doctor(runner)

    assert code == 1, payload
    assert payload["all_ok"] is False
    failed = [check for check in payload["checks"] if check["status"] == "fail"]
    assert [check["code"] for check in failed] == ["hook.start_failed"]
    assert failed[0]["harness"] == "codex"
    assert "dispatch.py" in failed[0]["message"]
    assert failed[0]["fix"]


def test_doctor_starts_a_cursor_hook_written_for_powershell(
    runner: CliRunner, home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Cursor runs hook lines through PowerShell on Windows, so an install there
    # writes `& "<python>" "<dispatch.py>" ...`. Write that form on every host:
    # doctor must start the interpreter, not a program named "&".
    monkeypatch.setattr(wrapper_factories, "_on_windows", lambda: True)
    project = _project(tmp_path)
    _install(runner, "cursor", "--project", str(project))
    hook_file = project / ".cursor" / "hooks.json"
    [entry] = json.loads(hook_file.read_text(encoding="utf-8"))["hooks"]["sessionStart"]
    assert entry["command"].startswith('& "')

    code, payload = _doctor(runner, "--project", str(project))

    assert code == 0, payload
    cursor = _row(payload, "cursor")
    assert cursor["status"] == "ok"
    assert cursor["hooks"]["probed"] >= 1
    assert cursor["hooks"]["failed"] == []


def test_doctor_starts_github_copilot_hooks(
    runner: CliRunner, home: Path, tmp_path: Path
) -> None:
    # Copilot entries hold their command lines under "bash" and "powershell",
    # with no "command" key.
    project = _project(tmp_path)
    _install(runner, "github-copilot", "--project", str(project))

    code, payload = _doctor(runner, "--project", str(project))

    assert code == 0, payload
    copilot = _row(payload, "github-copilot")
    assert copilot["status"] == "ok"
    assert copilot["hooks"]["probed"] >= 1
    assert copilot["hooks"]["failed"] == []


@pytest.mark.parametrize("harness", ["cursor", "github-copilot"])
def test_doctor_fails_when_a_project_hook_script_fails(
    runner: CliRunner,
    home: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    harness: str,
) -> None:
    monkeypatch.setattr(wrapper_factories, "_on_windows", lambda: True)
    project = _project(tmp_path)
    _install(runner, harness, "--project", str(project))
    dispatcher = project / ".apothem" / "support" / harness / "hooks" / "dispatch.py"
    assert dispatcher.is_file()
    dispatcher.write_text("raise SystemExit(3)\n", encoding="utf-8")

    code, payload = _doctor(runner, "--project", str(project))

    assert code == 1, payload
    failed = [check for check in payload["checks"] if check["status"] == "fail"]
    assert [check["code"] for check in failed] == ["hook.start_failed"]
    assert failed[0]["harness"] == harness
    # The script itself ran and exited 3, so the probe started the interpreter.
    assert "(exit 3" in failed[0]["message"]


@pytest.mark.parametrize(
    ("windows", "keys", "read"),
    [
        pytest.param(True, ("bash", "powershell"), "powershell", id="windows"),
        pytest.param(False, ("bash", "powershell"), "bash", id="macos-and-linux"),
        pytest.param(True, ("command",), "command", id="windows-command-only"),
        pytest.param(False, ("command",), "command", id="posix-command-only"),
        pytest.param(True, ("bash",), None, id="windows-bash-only"),
    ],
)
def test_doctor_reads_the_hook_line_the_harness_runs_on_this_platform(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    windows: bool,
    keys: tuple[str, ...],
    read: str | None,
) -> None:
    # GitHub Copilot runs "powershell" on Windows and "bash" on macOS and Linux,
    # and falls back to "command" when the platform's key is absent. Each line
    # here ends with its own key name, so the argv shows which one was read.
    python = Path(sys.executable).as_posix()
    script = (tmp_path / "hooks" / "dispatch.py").as_posix()
    entry: dict[str, str] = {"type": "command"}
    for key in keys:
        line = f'"{python}" -E -s "{script}" --contract copilot {key}'
        entry[key] = f"& {line}" if key == "powershell" else line
    hook_file = tmp_path / "apothem.json"
    document = {"version": 1, "hooks": {"sessionStart": [entry]}}
    hook_file.write_text(json.dumps(document), encoding="utf-8")
    record = SimpleNamespace(targets=[SimpleNamespace(path=str(hook_file))])
    monkeypatch.setattr(install_ledger, "latest_record", lambda package_key: record)
    monkeypatch.setattr(_doctor_hooks, "_on_windows", lambda: windows)

    argvs = _doctor_hooks.registered_hook_argvs("github_copilot")

    argv = [python, "-E", "-s", script, "--contract", "copilot", read]
    assert argvs == ([] if read is None else [argv])


def test_doctor_fails_when_an_installed_harness_does_not_verify(
    runner: CliRunner, home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install(runner, "codex")
    from apothem.harnesses.codex import CodexAdapter

    monkeypatch.setattr(CodexAdapter, "verify", lambda self: False)

    code, payload = _doctor(runner)

    assert code == 1, payload
    codes = [c["code"] for c in payload["checks"] if c["status"] == "fail"]
    assert codes == ["harness.verify_failed"]


def test_doctor_reports_an_invalid_profile_with_its_code(
    runner: CliRunner, home: Path
) -> None:
    profile = home / ".config" / "apothem" / "profile.yaml"
    profile.write_text("identity: [unclosed\n", encoding="utf-8")

    code, payload = _doctor(runner)

    assert code == 1, payload
    assert payload["profile_valid"] is False
    assert payload["profile_error_code"] == "profile.yaml_invalid"
    codes = [c["code"] for c in payload["checks"] if c["status"] == "fail"]
    assert codes == ["profile.yaml_invalid"]


def test_doctor_hook_probe_imports_in_a_fresh_interpreter() -> None:
    """``doctor`` loads its hook probe before anything imports the install driver.

    In-process tests import the driver shim first, which hides an import cycle
    that only a fresh interpreter (the real ``apothem doctor``) meets.
    """
    src_root = Path(apothem.__file__).resolve().parents[1]
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        part for part in (str(src_root), env.get("PYTHONPATH", "")) if part
    )
    result = subprocess.run(
        [sys.executable, "-c", "import apothem.cli._doctor_hooks"],
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stderr
