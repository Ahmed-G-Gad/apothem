# SPDX-License-Identifier: MIT

"""CLI-surface tests for the project-scope --project lifecycle.

The project-scope adapters (the ten adapters whose registry scope is
project-rooted) materialize into an operator-supplied project tree.
Every lifecycle command — install, verify, uninstall, update — must
accept --project and thread it to the adapter; commands invoked against
a project-scope adapter without --project must fail with a clear error
rather than silently operating on the wrong (or empty) location.

These tests drive the real cursor adapter (a representative project-scope
adapter) through a temporary project root, so the install -> verify ->
uninstall round-trip and the missing---project guard are exercised
end-to-end through the CLI.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from apothem.cli import main

_SENTINEL = Path(".cursor") / "rules" / "apothem-rules.mdc"


@pytest.fixture
def profile(tmp_path: Path) -> Path:
    path = tmp_path / "profile.yaml"
    path.write_text(
        "identity:\n  name: Test User\n"
        "preferences:\n  language: python\n"
        "seriousness: PERSONAL_USE\n",
        encoding="utf-8",
    )
    return path


def test_project_scope_install_verify_uninstall_round_trip(
    runner: CliRunner, profile: Path, tmp_path: Path
) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    target = project / _SENTINEL

    install = runner.invoke(
        main,
        [
            "install",
            "--harness",
            "cursor",
            "--profile",
            str(profile),
            "--project",
            str(project),
        ],
    )
    assert install.exit_code == 0, install.output
    assert target.is_file()

    verify = runner.invoke(
        main, ["verify", "--harness", "cursor", "--project", str(project)]
    )
    assert verify.exit_code == 0, verify.output

    uninstall = runner.invoke(
        main,
        ["uninstall", "--harness", "cursor", "--project", str(project), "--yes"],
    )
    assert uninstall.exit_code == 0, uninstall.output
    assert not target.exists()


def test_project_scope_install_json_reports_materialization_results(
    runner: CliRunner, profile: Path, tmp_path: Path
) -> None:
    project = tmp_path / "proj"
    project.mkdir()

    result = runner.invoke(
        main,
        [
            "install",
            "--harness",
            "cursor",
            "--profile",
            str(profile),
            "--project",
            str(project),
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    materialization = payload["materialization"]
    assert materialization["changed"] is True
    assert str(project / _SENTINEL) in materialization["files_written"]
    assert materialization["results"][0]["outcome"] == "warning"


def test_project_scope_install_dry_run_reports_without_writes(
    runner: CliRunner, profile: Path, tmp_path: Path
) -> None:
    project = tmp_path / "proj"
    project.mkdir()

    result = runner.invoke(
        main,
        [
            "install",
            "--harness",
            "cursor",
            "--profile",
            str(profile),
            "--project",
            str(project),
            "--dry-run",
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "dry_run"
    assert payload["files_written"] == []
    assert not (project / _SENTINEL).exists()


def test_project_scope_verify_reports_not_installed(
    runner: CliRunner, tmp_path: Path
) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    result = runner.invoke(
        main, ["verify", "--harness", "cursor", "--project", str(empty)]
    )
    assert result.exit_code == 1
    assert "NOT verified" in result.output


def test_project_scope_rejects_file_path(
    runner: CliRunner, profile: Path, tmp_path: Path
) -> None:
    project_file = tmp_path / "project.txt"
    project_file.write_text("not a directory", encoding="utf-8")

    result = runner.invoke(
        main,
        [
            "install",
            "--harness",
            "cursor",
            "--profile",
            str(profile),
            "--project",
            str(project_file),
            "--json",
        ],
    )

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["error"]["code"] == "project.invalid_type"
    assert payload["files_written"] == []


@pytest.mark.parametrize("command", ["verify", "uninstall", "update"])
def test_project_scope_command_without_project_errors(
    runner: CliRunner, command: str, profile: Path
) -> None:
    args = [command, "--harness", "cursor"]
    if command == "update":
        args.extend(["--profile", str(profile)])
    if command == "uninstall":
        args.append("--yes")
    result = runner.invoke(main, args)
    assert result.exit_code != 0
    assert "project-scope harnesses require --project" in result.output
