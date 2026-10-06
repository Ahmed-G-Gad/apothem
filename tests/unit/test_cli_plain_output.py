# SPDX-License-Identifier: MIT

"""Plain output stays line-intact when piped, and help epilogs keep their lines.

Rich falls back to an 80-column width when stdout is not a terminal, so a long
path in a success message was split across lines, and a copied path failed.
Click re-flowed every ``--help`` epilog into one paragraph, so the Examples,
Related commands and Exit codes lists ran together.
"""

from __future__ import annotations

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
def deep_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A HOME path long enough that an 80-column wrap would split it."""
    home = tmp_path / ("a-rather-long-directory-name-" * 3) / "home"
    home.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.delenv("COLUMNS", raising=False)
    monkeypatch.setenv("APOTHEM_HOME", str(tmp_path / "apothem-home"))
    monkeypatch.setattr(install_driver, "BACKUP_ROOT", tmp_path / "backups")
    profile = home / ".config" / "apothem" / "profile.yaml"
    profile.parent.mkdir(parents=True)
    profile.write_text(_PROFILE, encoding="utf-8")
    return home


def test_piped_success_message_keeps_the_path_on_one_line(
    runner: CliRunner, deep_home: Path
) -> None:
    settings = deep_home / ".claude" / "settings.json"
    assert len(str(settings)) > 80
    installed = runner.invoke(main, ["install", "--harness", "claude-code"])
    assert installed.exit_code == 0, installed.output
    verified = runner.invoke(main, ["verify", "--harness", "claude-code"])
    assert verified.exit_code == 0, verified.output
    for result in (installed, verified):
        assert any(str(settings) in line for line in result.output.splitlines()), (
            result.output
        )


@pytest.mark.parametrize(
    ("argv", "example_prefix", "minimum"),
    [
        (["verify", "--help"], "  apothem verify", 4),
        (["install", "--help"], "  apothem install", 4),
        (["doctor", "--help"], "  apothem doctor", 3),
    ],
)
def test_help_epilog_keeps_one_example_per_line(
    runner: CliRunner, argv: list[str], example_prefix: str, minimum: int
) -> None:
    result = runner.invoke(main, argv)
    assert result.exit_code == 0, result.output
    lines = result.output.splitlines()
    assert (
        sum(line.lstrip().startswith(example_prefix.strip()) for line in lines)
        >= minimum
    ), result.output
    assert any(line.strip() == "Exit codes:" for line in lines), result.output
    assert any(line.strip().startswith("64 ") for line in lines), result.output
