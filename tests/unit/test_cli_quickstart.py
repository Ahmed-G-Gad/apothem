# SPDX-License-Identifier: MIT

"""UX-5 regression: the guided first-run ``quickstart`` command.

``apothem quickstart`` is the single guided first-run entry point. It composes
the UX-1..UX-4 building blocks (it does not duplicate them): ensure a profile
exists (scaffold + personalize nudge if missing), preview the blast radius,
confirm, install with the de-noised grouped notes, then print the recommended
next commands. ``--yes`` runs the whole sequence non-interactively; ``--format
json`` emits one structured summary of every step.

These tests drive the real CLI under an isolated HOME so no real harness state
is touched.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

import apothem.cli as cli
from apothem.cli import main
from apothem.harnesses._shared import install_driver

_PERSONALIZED = (
    "identity:\n  name: Ada Lovelace\n  email: ada@analytical.engine\n"
    "  github: adalovelace\nseriousness: PERSONAL_USE\n"
)


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """Isolate HOME + XDG so quickstart's default profile path lands under tmp."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))  # Windows HOME resolution
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    monkeypatch.setenv("APOTHEM_HOME", str(tmp_path / "apothem-home"))
    monkeypatch.setattr(install_driver, "BACKUP_ROOT", tmp_path / "backups")
    project = tmp_path / "proj"
    project.mkdir()
    return home, project


def test_quickstart_yes_fresh_runs_full_ordered_sequence(
    runner: CliRunner, env: tuple[Path, Path]
) -> None:
    """``--yes`` on a fresh machine runs profile->preview->install->next in order."""
    home, project = env
    result = runner.invoke(
        main, ["quickstart", "--project", str(project), "--no-color", "--yes"]
    )
    assert result.exit_code == 0, result.output
    out = result.output

    # The canonical guided sequence, in order.
    i_profile = out.find("Created a starter profile")
    i_preview = out.find("will write")  # the blast-radius preview heading
    i_install = out.find("Installed")
    i_next = out.find("Recommended next step")
    assert -1 < i_profile < i_preview < i_install < i_next, out

    # De-noised output (UX-1 grouped Note, never the per-cell flood).
    assert "Note:" in out
    assert "Warning:" not in out
    # Personalize nudge (UX-3) and a profile actually scaffolded (UX-3 enrich).
    assert "Personalize" in out
    assert (home / ".config" / "apothem" / "profile.yaml").is_file()
    # Recommended next step names the follow-on commands, pointing at the
    # project root the operator actually installed into (join wrapped lines —
    # the console soft-wraps long paths).
    flat = out.replace("\n", "")
    assert f"verify --harness all --project {project}" in flat
    assert "apothem doctor" in out


def test_quickstart_json_emits_one_structured_summary(
    runner: CliRunner, env: tuple[Path, Path]
) -> None:
    """``--format json`` emits a single document summarizing each guided step."""
    _, project = env
    result = runner.invoke(
        main,
        ["quickstart", "--project", str(project), "--format", "json", "--yes"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)  # exactly one JSON document
    assert payload["command"] == "quickstart"
    assert payload["status"] == "success"
    assert [s["step"] for s in payload["steps"]] == ["profile", "install", "recommend"]
    profile_step = payload["steps"][0]
    assert profile_step["outcome"] == "created"
    install_step = payload["steps"][1]
    assert install_step["files_written"]  # the install really ran
    assert payload["recommended_next"][0].startswith("apothem verify")


def test_quickstart_interactive_decline_at_confirm_writes_nothing(
    runner: CliRunner, env: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Declining the blast-radius confirmation aborts before any harness write."""
    home, project = env
    monkeypatch.setattr(cli, "_stdin_is_interactive", lambda: True)
    # First prompt: create the starter profile (yes). Second: proceed with the
    # writes (no) -> abort before any harness file is written.
    result = runner.invoke(
        main,
        ["quickstart", "--project", str(project), "--no-color"],
        input="y\nn\n",
    )
    assert result.exit_code != 0  # click.Abort
    assert "Proceed and write" in result.output  # the confirm was reached
    # The profile was scaffolded, but no harness config was written anywhere.
    assert (home / ".config" / "apothem" / "profile.yaml").is_file()
    assert [p for p in project.rglob("*") if p.is_file()] == []
    assert not (home / ".claude" / "settings.json").exists()


def test_quickstart_existing_invalid_profile_emits_structured_error(
    runner: CliRunner, env: tuple[Path, Path]
) -> None:
    """An existing-but-invalid profile fails with the standard error envelope.

    Regression: the existing-profile path loads the profile for the
    personalize nudge; a validation failure there must produce the same
    structured diagnostic as install/update/verify, never a raw traceback.
    """
    home, project = env
    profile = home / ".config" / "apothem" / "profile.yaml"
    profile.parent.mkdir(parents=True)
    profile.write_text("identity: [unclosed\n", encoding="utf-8")

    result = runner.invoke(
        main,
        ["quickstart", "--project", str(project), "--format", "json", "--yes"],
    )
    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)  # exactly one JSON document, no traceback
    assert payload["command"] == "quickstart"
    assert payload["status"] == "error"
    assert payload["error"]

    plain = runner.invoke(
        main, ["quickstart", "--project", str(project), "--no-color", "--yes"]
    )
    assert plain.exit_code == 1, plain.output
    assert "Error:" in plain.output
    assert "Traceback" not in plain.output


def test_quickstart_existing_profile_is_not_recreated(
    runner: CliRunner, env: tuple[Path, Path]
) -> None:
    """A personalized profile is kept (outcome 'existing'); no placeholder advisory."""
    home, project = env
    profile = home / ".config" / "apothem" / "profile.yaml"
    profile.parent.mkdir(parents=True)
    profile.write_text(_PERSONALIZED, encoding="utf-8")

    result = runner.invoke(
        main,
        ["quickstart", "--project", str(project), "--format", "json", "--yes"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["steps"][0]["outcome"] == "existing"
    assert payload["steps"][0]["placeholder_identity"] == []
    # No placeholder advisory in the install warnings for a personalized identity.
    install_warnings = payload["steps"][1]["warnings"]
    assert not any(
        w.get("operation") == "placeholder_identity" for w in install_warnings
    )
