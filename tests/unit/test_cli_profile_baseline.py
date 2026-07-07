# SPDX-License-Identifier: MIT

"""CLI-surface tests for the ``--profile`` drift baseline on verify and status.

``verify`` and ``status`` accept ``--profile PATH`` (mirroring install / update
/ diff), naming the profile their fidelity check is resolved against:

- ``status`` compares each install against the chosen profile to classify
  drift; without ``--profile`` the default profile is the baseline.
- ``verify`` is structural by default (targets present and valid). With
  ``--profile`` it additionally requires fidelity, so a present-but-drifted
  install fails verify — answering "is THIS profile faithfully installed?".

The cursor adapter is project-scope, so an install into a temporary project
tree exercises the install -> drift/fidelity round-trip end-to-end through the
CLI without touching the operator's real home directory.
"""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from apothem.cli import main

_CURSOR_SENTINEL = Path(".cursor") / "rules" / "apothem-rules.mdc"


def _write_profile(path: Path, *, name: str) -> Path:
    path.write_text(
        f"identity:\n  name: {name}\n"
        "preferences:\n  language: python\n"
        "seriousness: PERSONAL_USE\n",
        encoding="utf-8",
    )
    return path


def _install_cursor(runner: CliRunner, profile: Path, project: Path) -> None:
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
        ],
    )
    assert result.exit_code == 0, result.output
    assert (project / _CURSOR_SENTINEL).is_file()


# -----------------------------------------------------------------------
# verify --profile (fidelity opt-in)
# -----------------------------------------------------------------------


def test_verify_profile_faithful_passes(runner: CliRunner, tmp_path: Path) -> None:
    profile = _write_profile(tmp_path / "profile.yaml", name="Alice")
    project = tmp_path / "proj"
    project.mkdir()
    _install_cursor(runner, profile, project)

    result = runner.invoke(
        main,
        [
            "verify",
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
    data = json.loads(result.output.strip())
    assert data["status"] == "success"
    assert data["verified"] is True
    assert data["results"][0]["drift"] == "in-sync"


def test_verify_profile_drift_fails(runner: CliRunner, tmp_path: Path) -> None:
    installed = _write_profile(tmp_path / "installed.yaml", name="Alice")
    other = _write_profile(tmp_path / "other.yaml", name="Bob")
    project = tmp_path / "proj"
    project.mkdir()
    _install_cursor(runner, installed, project)

    result = runner.invoke(
        main,
        [
            "verify",
            "--harness",
            "cursor",
            "--profile",
            str(other),
            "--project",
            str(project),
            "--json",
        ],
    )
    # Structurally present but drifted from the named profile -> verify fails.
    assert result.exit_code == 1, result.output
    data = json.loads(result.output.strip())
    assert data["verified"] is False
    row = data["results"][0]
    assert row["drift"] == "drift"
    assert "drift" in row["message"].lower()


def test_verify_without_profile_is_structural(
    runner: CliRunner, tmp_path: Path
) -> None:
    """Bare verify ignores any profile: a present install passes structurally."""
    installed = _write_profile(tmp_path / "installed.yaml", name="Alice")
    project = tmp_path / "proj"
    project.mkdir()
    _install_cursor(runner, installed, project)

    result = runner.invoke(
        main,
        ["verify", "--harness", "cursor", "--project", str(project), "--json"],
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output.strip())
    assert data["verified"] is True
    # No --profile means no fidelity verdict: the drift key is absent.
    assert "drift" not in data["results"][0]


def test_verify_explicit_bad_profile_errors(runner: CliRunner, tmp_path: Path) -> None:
    result = runner.invoke(
        main,
        [
            "verify",
            "--harness",
            "cursor",
            "--profile",
            str(tmp_path / "nope.yaml"),
            "--project",
            str(tmp_path),
        ],
    )
    assert result.exit_code != 0
    assert "profile" in result.output.lower()


# -----------------------------------------------------------------------
# status --profile (drift baseline)
# -----------------------------------------------------------------------


def test_status_profile_baseline_in_sync(runner: CliRunner, tmp_path: Path) -> None:
    profile = _write_profile(tmp_path / "profile.yaml", name="Alice")
    project = tmp_path / "proj"
    project.mkdir()
    _install_cursor(runner, profile, project)

    result = runner.invoke(
        main,
        ["status", "--profile", str(profile), "--project", str(project), "--json"],
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output.strip())
    cursor_row = next(r for r in data["results"] if r["harness"] == "cursor")
    assert cursor_row["installed"] is True
    assert cursor_row["drift"] == "in-sync"


def test_status_profile_baseline_detects_drift(
    runner: CliRunner, tmp_path: Path
) -> None:
    installed = _write_profile(tmp_path / "installed.yaml", name="Alice")
    other = _write_profile(tmp_path / "other.yaml", name="Bob")
    project = tmp_path / "proj"
    project.mkdir()
    _install_cursor(runner, installed, project)

    result = runner.invoke(
        main,
        ["status", "--profile", str(other), "--project", str(project), "--json"],
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output.strip())
    cursor_row = next(r for r in data["results"] if r["harness"] == "cursor")
    assert cursor_row["drift"] == "drift"


def test_status_profile_path_surfaced_in_envelope(
    runner: CliRunner, tmp_path: Path
) -> None:
    profile = _write_profile(tmp_path / "profile.yaml", name="Alice")
    result = runner.invoke(main, ["status", "--profile", str(profile), "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output.strip())
    assert data["profile_path"] == str(profile)


def test_status_explicit_bad_profile_errors(runner: CliRunner, tmp_path: Path) -> None:
    """An explicit --profile that cannot load is a user error, not silent drift."""
    result = runner.invoke(main, ["status", "--profile", str(tmp_path / "nope.yaml")])
    assert result.exit_code == 1, result.output
    assert "profile" in result.output.lower()
