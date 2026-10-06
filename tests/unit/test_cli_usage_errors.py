# SPDX-License-Identifier: MIT

"""Usage errors exit 64 and honor JSON mode.

Exit 2 is documented as a partial write (install, update, quickstart,
uninstall, rollback). Click also used 2 for every usage error, so automation
that rolls back on 2 would act on a mistyped flag. Usage errors now exit 64
(``EX_USAGE``), and under ``--json`` / ``--format json`` they print one JSON
error envelope with ``error.code == "cli.usage"`` instead of plain text.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from apothem.cli import main

_EX_USAGE = 64


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))


@pytest.mark.parametrize(
    "argv",
    [
        ["install", "--harness", "cursor", "--bogus"],
        ["install"],
        ["doctor", "--format", "xml"],
        ["instal", "--harness", "cursor"],
        ["profile", "nope"],
    ],
)
def test_plain_usage_errors_exit_64(runner: CliRunner, argv: list[str]) -> None:
    result = runner.invoke(main, argv)
    assert result.exit_code == _EX_USAGE, result.output
    assert "Usage:" in result.stderr
    assert "Error:" in result.stderr


@pytest.mark.parametrize(
    "argv",
    [
        ["install", "--harness", "cursor", "--bogus", "--json"],
        ["install", "--json"],
        ["verify", "--format", "json", "--nope"],
        ["quickstart", "--yes", "--json"],
        ["--json", "instal"],
    ],
)
def test_json_usage_errors_print_one_envelope(
    runner: CliRunner, argv: list[str]
) -> None:
    result = runner.invoke(main, argv)
    assert result.exit_code == _EX_USAGE, result.output
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == 1
    assert payload["status"] == "error"
    assert payload["error"]["code"] == "cli.usage"
    assert payload["error"]["reason"]
    assert "--help" in payload["error"]["fix"]


def test_help_and_version_still_exit_zero(runner: CliRunner) -> None:
    assert runner.invoke(main, ["--help"]).exit_code == 0
    assert runner.invoke(main, ["--version"]).exit_code == 0
    assert runner.invoke(main, ["install", "--help"]).exit_code == 0
