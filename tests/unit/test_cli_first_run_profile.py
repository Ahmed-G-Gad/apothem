# SPDX-License-Identifier: MIT

"""First-run ``install`` on a clean HOME creates the default profile.

The single copy-ready command on the npm and direct-engine channels is
``install --harness <name>``. On a machine with no profile it used to exit 1
with "profile file does not exist" and a Fix naming a command that is not on
PATH for those channels. Now ``install`` without ``--profile`` scaffolds the
default profile (placeholder identity, with a notice) and proceeds; an
explicit ``--profile PATH`` that does not exist is still an error, and a
dry run never writes the profile.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from apothem.cli import main
from apothem.harnesses._shared import install_driver


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolate HOME so the default profile path lands under tmp."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.delenv("CODEX_HOME", raising=False)
    monkeypatch.setenv("APOTHEM_HOME", str(tmp_path / "apothem-home"))
    monkeypatch.setattr(install_driver, "BACKUP_ROOT", tmp_path / "backups")
    return home


def _default_profile(home: Path) -> Path:
    return home / ".config" / "apothem" / "profile.yaml"


def test_install_creates_the_default_profile_on_first_run(
    runner: CliRunner, home: Path
) -> None:
    """Plain ``install --harness claude-code`` on a clean HOME exits 0."""
    result = runner.invoke(main, ["install", "--harness", "claude-code", "--no-color"])
    assert result.exit_code == 0, result.output
    assert _default_profile(home).is_file()
    assert "Created a starter profile" in result.output
    assert (home / ".claude" / "settings.json").is_file()


def test_install_json_reports_the_created_profile(
    runner: CliRunner, home: Path
) -> None:
    """JSON mode records the scaffold as an advisory warning, not silence."""
    result = runner.invoke(main, ["install", "--harness", "claude-code", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "success"
    created = [
        w for w in payload["warnings"] if w.get("operation") == "profile_created"
    ]
    assert len(created) == 1
    assert created[0]["path"] == str(_default_profile(home))


def test_install_dry_run_never_writes_the_profile(
    runner: CliRunner, home: Path
) -> None:
    """A dry run previews with the starter profile in memory and writes nothing."""
    result = runner.invoke(
        main, ["install", "--harness", "claude-code", "--dry-run", "--json"]
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "dry_run"
    assert not _default_profile(home).exists()
    assert not (home / ".claude").exists()


def test_install_with_a_missing_explicit_profile_still_fails(
    runner: CliRunner, home: Path, tmp_path: Path
) -> None:
    """An explicit ``--profile`` path is never invented; the Fix is channel-neutral."""
    missing = tmp_path / "nope.yaml"
    result = runner.invoke(
        main,
        ["install", "--harness", "claude-code", "--profile", str(missing), "--json"],
    )
    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)
    assert payload["error"]["code"] == "profile.not_found"
    assert "Run 'apothem " not in payload["error"]["fix"]
    assert not missing.exists()
