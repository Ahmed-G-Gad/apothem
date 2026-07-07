# SPDX-License-Identifier: MIT

"""UX-3 regression: post-init personalize nudge + placeholder-identity advisory.

``profile init`` writes a scaffold whose identity fields still hold shipped
placeholder values ("Example User", "dev@example.invalid", "example-user"). The
command nudges the operator to personalize them, and any later install/update
run against a still-placeholder profile surfaces a single advisory note — never
blocking, since identity is never fabricated or coerced. The ``--format json``
envelope carries the advisory entry instead of a printed nudge.

These tests drive the real CLI under an isolated HOME so no real harness state
is touched.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

import apothem.cli as cli
from apothem.cli import main
from apothem.harnesses._shared import install_driver
from apothem.schemas import profile_example_path, profile_minimal_path

_PERSONALIZED = (
    "identity:\n  name: Ada Lovelace\n  email: ada@analytical.engine\n"
    "  github: adalovelace\nseriousness: PERSONAL_USE\n"
)


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolate HOME so user-scope installs land under tmp_path."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))  # Windows HOME resolution
    monkeypatch.setenv("APOTHEM_HOME", str(tmp_path / "apothem-home"))
    monkeypatch.setattr(install_driver, "BACKUP_ROOT", tmp_path / "backups")
    return home


def _scaffold_profile(runner: CliRunner, tmp_path: Path) -> Path:
    """Create a real scaffold via ``profile init`` and return its path."""
    profile = tmp_path / "scaffold.yaml"
    result = runner.invoke(main, ["profile", "init", "--profile", str(profile)])
    assert result.exit_code == 0, result.output
    return profile


def _placeholder_advisories(payload: dict) -> list[dict]:
    return [
        w for w in payload["warnings"] if w.get("operation") == "placeholder_identity"
    ]


def test_scaffold_install_emits_single_placeholder_advisory(
    runner: CliRunner, home: Path, tmp_path: Path
) -> None:
    """An unedited scaffold profile triggers exactly one advisory on install."""
    profile = _scaffold_profile(runner, tmp_path)

    plain = runner.invoke(
        main,
        [
            "install",
            "--harness",
            "claude-code",
            "--profile",
            str(profile),
            "--no-color",
        ],
    )
    assert plain.exit_code == 0, plain.output
    note_lines = [
        line
        for line in plain.output.splitlines()
        if line.startswith("Note:") and "placeholder" in line.lower()
    ]
    assert len(note_lines) == 1

    js = runner.invoke(
        main,
        [
            "install",
            "--harness",
            "claude-code",
            "--profile",
            str(profile),
            "--format",
            "json",
        ],
    )
    assert js.exit_code == 0, js.output
    advisories = _placeholder_advisories(json.loads(js.output))
    assert len(advisories) == 1
    assert set(advisories[0]["fields"]) == {"name", "email", "github"}


def test_personalized_install_emits_no_placeholder_advisory(
    runner: CliRunner, home: Path, tmp_path: Path
) -> None:
    """A personalized identity triggers no placeholder advisory."""
    profile = tmp_path / "personal.yaml"
    profile.write_text(_PERSONALIZED, encoding="utf-8")

    plain = runner.invoke(
        main,
        [
            "install",
            "--harness",
            "claude-code",
            "--profile",
            str(profile),
            "--no-color",
        ],
    )
    assert plain.exit_code == 0, plain.output
    assert "placeholder" not in plain.output.lower()

    js = runner.invoke(
        main,
        [
            "install",
            "--harness",
            "claude-code",
            "--profile",
            str(profile),
            "--format",
            "json",
        ],
    )
    assert js.exit_code == 0, js.output
    assert _placeholder_advisories(json.loads(js.output)) == []


def test_profile_init_plain_prints_personalize_nudge(
    runner: CliRunner, tmp_path: Path
) -> None:
    """``profile init`` plain output names the placeholder identity fields."""
    profile = tmp_path / "profile.yaml"
    result = runner.invoke(
        main, ["profile", "init", "--profile", str(profile), "--no-color"]
    )

    assert result.exit_code == 0, result.output
    out = result.output
    assert "Personalize your profile" in out
    for field in ("name", "email", "github"):
        assert field in out
    # Normalize whitespace before the substring check: Rich wraps the nudge at
    # the console width, and the wrap point depends on the temp-path length, so
    # the pointer can straddle a newline ("profile set \nidentity.name").
    assert "profile set identity.name" in " ".join(out.split())  # edit pointer


def test_profile_init_json_carries_advisory_not_printed_nudge(
    runner: CliRunner, tmp_path: Path
) -> None:
    """``profile init --json`` carries an advisory entry, no printed nudge."""
    profile = tmp_path / "profile.yaml"
    result = runner.invoke(
        main, ["profile", "init", "--profile", str(profile), "--json"]
    )

    assert result.exit_code == 0, result.output
    assert "Personalize your profile" not in result.output  # no plain nudge in JSON
    payload = json.loads(result.output)
    assert payload["status"] == "success"
    advisories = _placeholder_advisories(payload)
    assert len(advisories) == 1
    assert set(advisories[0]["fields"]) == {"name", "email", "github"}


def test_placeholder_constant_matches_shipped_scaffolds() -> None:
    """Drift guard: the detection constant matches both shipped scaffold files."""
    minimal = yaml.safe_load(profile_minimal_path().read_text(encoding="utf-8"))
    example = yaml.safe_load(profile_example_path().read_text(encoding="utf-8"))

    # Every identity field present in a scaffold must equal the detection token,
    # so the shipped scaffolds are always recognized as unpersonalized.
    for scaffold in (minimal, example):
        identity = scaffold["identity"]
        for field, value in identity.items():
            if field in cli._PLACEHOLDER_IDENTITY:
                assert value == cli._PLACEHOLDER_IDENTITY[field], (scaffold, field)
    # The minimal scaffold carries exactly the fields the nudge names.
    assert set(minimal["identity"]) == {"name", "email", "github"}
