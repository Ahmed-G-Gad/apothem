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
from pathlib import Path

import pytest
from click.testing import CliRunner

from apothem.cli import main
from apothem.harnesses._shared import install_driver

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
