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
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

import apothem
from apothem.cli import _doctor_hooks, main
from apothem.harnesses._shared import install_driver
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


def _doctor(runner: CliRunner) -> tuple[int, dict]:
    result = runner.invoke(main, ["doctor", "--json"])
    return result.exit_code, json.loads(result.stdout)


def _install(runner: CliRunner, harness: str) -> None:
    result = runner.invoke(main, ["install", "--harness", harness, "--json"])
    assert result.exit_code == 0, result.output


def _row(payload: dict, name: str) -> dict:
    return next(row for row in payload["harnesses"] if row["name"] == name)


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


def test_doctor_checks_the_hooks_of_the_root_it_examines(
    runner: CliRunner, home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A newer install at a since-deleted ``CODEX_HOME`` does not stand in."""
    _install(runner, "codex")
    elsewhere = tmp_path / "codex-elsewhere"
    monkeypatch.setenv("CODEX_HOME", str(elsewhere))
    _install(runner, "codex")
    monkeypatch.delenv("CODEX_HOME")
    shutil.rmtree(elsewhere)
    dispatcher = home / ".codex" / "hooks" / "dispatch.py"
    dispatcher.write_text("raise SystemExit(3)\n", encoding="utf-8")

    code, payload = _doctor(runner)

    assert code == 1, payload
    codex = _row(payload, "codex")
    assert codex["status"] == "hook_failed"
    assert codex["hooks"]["probed"] >= 1
    assert "dispatch.py" in codex["hooks"]["failed"][0]["command"]


def test_doctor_checks_the_hooks_of_the_project_it_is_given(
    runner: CliRunner, home: Path, tmp_path: Path
) -> None:
    """A newer install in a since-deleted project does not stand in."""
    first, second = tmp_path / "first", tmp_path / "second"
    for project in (first, second):
        project.mkdir()
        result = runner.invoke(
            main,
            ["install", "--harness", "cursor", "--project", str(project), "--yes"],
        )
        assert result.exit_code == 0, result.output
    shutil.rmtree(second)
    # Healthy first: the hook command (with PowerShell's "&" on Windows) starts.
    result = runner.invoke(main, ["doctor", "--json", "--project", str(first)])
    payload = json.loads(result.stdout)
    assert result.exit_code == 0, payload
    assert _row(payload, "cursor")["hooks"] == {"probed": 1, "failed": []}
    dispatcher = first / ".apothem" / "support" / "cursor" / "hooks" / "dispatch.py"
    assert dispatcher.is_file()
    dispatcher.write_text("raise SystemExit(3)\n", encoding="utf-8")

    result = runner.invoke(main, ["doctor", "--json", "--project", str(first)])

    payload = json.loads(result.stdout)
    assert result.exit_code == 1, payload
    cursor = _row(payload, "cursor")
    assert cursor["status"] == "hook_failed"
    assert cursor["hooks"]["probed"] >= 1
    command = os.path.normcase(cursor["hooks"]["failed"][0]["command"])
    assert os.path.normcase(str(first / ".apothem")) in command
    assert os.path.normcase(str(second)) not in command


def test_doctor_reports_the_hook_check_not_run_for_a_root_with_no_record(
    runner: CliRunner, home: Path
) -> None:
    _install(runner, "codex")
    # The only record now names another root (an install of an earlier spelling).
    ledger = install_ledger.ledger_path("codex")
    text = ledger.read_text(encoding="utf-8")
    ledger.write_text(
        text.replace(json.dumps(str(home / ".codex"))[1:-1], "elsewhere"),
        encoding="utf-8",
    )

    code, payload = _doctor(runner)

    codex = _row(payload, "codex")
    assert codex["status"] == "ok", payload
    assert codex["hooks"] is None
    unchecked = [c for c in payload["checks"] if c["code"] == "hook.unchecked"]
    assert [c["harness"] for c in unchecked] == ["codex"]
    assert "--project" not in unchecked[0]["fix"]
    assert code == 0
    # The plain report says so too, rather than leaving the Hooks cell blank.
    plain = runner.invoke(main, ["doctor"])
    assert plain.exit_code == 0, plain.output
    assert "not checked" in plain.output
    assert "no install record for" in plain.output
    # The last line says what was not checked rather than that all passed.
    flat = " ".join(plain.output.split())
    assert "All checks passed" not in flat
    assert "the hook commands of codex were not checked" in flat


def test_doctor_finds_the_install_under_another_spelling_of_its_folder(
    runner: CliRunner, home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A ``CODEX_HOME`` spelled another way still names the folder installed to."""
    codex_home = tmp_path / "cx"
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    _install(runner, "codex")
    (codex_home / "hooks" / "dispatch.py").write_text(
        "raise SystemExit(3)\n", encoding="utf-8"
    )
    (tmp_path / "step").mkdir()
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "step" / ".." / "cx"))

    code, payload = _doctor(runner)

    assert code == 1, payload
    codex = _row(payload, "codex")
    assert codex["status"] == "hook_failed"
    assert not [c for c in payload["checks"] if c["code"] == "hook.unchecked"]


def test_doctor_finds_the_install_under_another_letter_case_of_its_folder(
    runner: CliRunner, home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """On a case-insensitive file system, ``CODEX_HOME`` may change its case."""
    codex_home = tmp_path / "cx"
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    _install(runner, "codex")
    if not (tmp_path / "CX").is_dir():
        pytest.skip("this file system tells letter cases apart")
    (codex_home / "hooks" / "dispatch.py").write_text(
        "raise SystemExit(3)\n", encoding="utf-8"
    )
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "CX"))

    code, payload = _doctor(runner)

    assert code == 1, payload
    assert _row(payload, "codex")["status"] == "hook_failed"
    assert not [c for c in payload["checks"] if c["code"] == "hook.unchecked"]


def test_a_spelling_in_another_letter_case_is_matched_by_file_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Where the OS does not fold case (macOS), the file ID joins the spellings.

    ``same_location`` is made to answer no, as it does on macOS, so this runs
    the file-ID branch on every case-insensitive file system.
    """
    (tmp_path / "cx").mkdir()
    (tmp_path / "other").mkdir()
    if not (tmp_path / "CX").is_dir():
        pytest.skip("this file system tells letter cases apart")
    monkeypatch.setattr(_doctor_hooks, "same_location", lambda left, right: False)

    assert _doctor_hooks._same_folder(str(tmp_path / "cx"), tmp_path / "CX")
    assert not _doctor_hooks._same_folder(str(tmp_path / "cx"), tmp_path / "other")


def test_two_folders_that_differ_only_in_letter_case_stay_apart(
    tmp_path: Path,
) -> None:
    """On a case-sensitive file system ``cx`` and ``CX`` are two folders."""
    (tmp_path / "cx").mkdir()
    try:
        (tmp_path / "CX").mkdir()
    except FileExistsError:
        pytest.skip("this file system folds letter case")

    assert not _doctor_hooks._same_folder(str(tmp_path / "cx"), tmp_path / "CX")


@pytest.mark.parametrize(
    ("name", "os_name", "quoted"),
    [
        ("plain dir", "nt", '"{}"'),
        ("a $HOME `x` it's", "nt", "'{}'"),
        ("plain dir", "posix", None),
        ("a $HOME `x` it's", "posix", None),
    ],
)
def test_the_project_in_a_fix_is_quoted_for_the_shell(
    name: str,
    os_name: str,
    quoted: str | None,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nothing in the path expands in the shell the command is pasted into.

    On Windows double quotes suit PowerShell and cmd alike, except for a path
    with ``$`` or a backtick, which PowerShell expands there: that one goes in
    PowerShell single quotes, each ``'`` doubled. Elsewhere, POSIX quoting.
    """
    from apothem.cli import _cmd_doctor, _shell_args

    project = tmp_path / name
    with monkeypatch.context() as patch:
        patch.setattr(_shell_args.os, "name", os_name)
        command = _cmd_doctor._update_command("cursor", project)
    prefix = "update --harness cursor --project "
    if quoted is None:
        assert command == prefix + shlex.quote(str(project))
        assert shlex.split(command)[-1] == str(project)
    else:
        assert command == prefix + quoted.format(str(project).replace("'", "''"))


def test_doctor_names_the_project_in_a_project_harness_fix(
    runner: CliRunner, home: Path, tmp_path: Path
) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    result = runner.invoke(
        main, ["install", "--harness", "cursor", "--project", str(project), "--yes"]
    )
    assert result.exit_code == 0, result.output
    ledger = install_ledger.ledger_path("cursor")
    text = ledger.read_text(encoding="utf-8")
    ledger.write_text(
        text.replace(json.dumps(str(project))[1:-1], "elsewhere"), encoding="utf-8"
    )

    result = runner.invoke(main, ["doctor", "--json", "--project", str(project)])

    payload = json.loads(result.stdout)
    unchecked = [c for c in payload["checks"] if c["code"] == "hook.unchecked"]
    assert [c["harness"] for c in unchecked] == ["cursor"]
    quoted = f'"{project}"' if os.name == "nt" else shlex.quote(str(project))
    assert f"update --harness cursor --project {quoted}" in unchecked[0]["fix"]


@pytest.mark.parametrize(
    "command",
    [
        '& "py" "x/hooks/dispatch.py" --contract cursor sessionStart',
        'py "x/hooks/dispatch.py" --contract cursor sessionStart',
    ],
)
def test_a_shell_form_hook_drops_the_powershell_call_operator(command: str) -> None:
    argv = _doctor_hooks._handler_argv({"command": command})
    assert argv == ["py", "x/hooks/dispatch.py", "--contract", "cursor", "sessionStart"]


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
