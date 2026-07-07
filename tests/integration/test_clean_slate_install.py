# SPDX-License-Identifier: MIT

"""Integration coverage for the opt-in ``apothem install --clean`` path.

The engine is driven directly via ``python -m apothem`` against an isolated
``HOME`` so the destructive path is exercised end to end without touching the
operator's real home directory and without the network. Two cases are covered:
a dry run that previews and removes nothing, and a confirmed ``--yes`` run that
backs up, wipes the prior install state, restores the profile, and materializes
a fresh harness facade.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"

# The claude-code adapter materializes a HOME-relative singleton config.
HARNESS = "claude-code"
HARNESS_CONFIG_RELATIVE = Path(".claude") / "settings.json"

TIMEOUT_SECONDS = 180

MINIMAL_PROFILE = """\
identity:
  name: "Clean Slate Gate"
  role: "release engineer"
  email: "gate@example.invalid"
  website: "https://example.invalid"
  github: "clean-slate-gate"

preferences:
  language: "python"
  style: "concise"
  formatter: "ruff"
  test_framework: "pytest"

seriousness: PERSONAL_USE

rules:
  - "Keep generated harness output deterministic."
"""


def _arrange_home(tmp_path: Path) -> tuple[Path, Path]:
    """Build an isolated HOME pre-seeded with stale install state.

    Returns the home directory and the profile path inside it.
    """
    home = tmp_path / "home"
    # Stale prior install state across the bounded target set.
    (home / ".claude").mkdir(parents=True)
    (home / ".claude" / "stale.txt").write_text("stale", encoding="utf-8")
    (home / ".codex").mkdir(parents=True)
    (home / ".codex" / "stale.toml").write_text("old = true", encoding="utf-8")
    (home / ".agents").mkdir(parents=True)
    (home / ".agents" / "stale.md").write_text("# stale", encoding="utf-8")
    profile = home / ".config" / "apothem" / "profile.yaml"
    profile.parent.mkdir(parents=True)
    profile.write_text(MINIMAL_PROFILE, encoding="utf-8")
    # An unrelated ~/.config application that must survive untouched.
    other = home / ".config" / "other-app"
    other.mkdir(parents=True)
    (other / "keep.conf").write_text("preserve me", encoding="utf-8")
    return home, profile


def _isolated_env(home: Path, apothem_home: Path) -> dict[str, str]:
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env["PYTHONPATH"] = str(SRC_DIR)
    env["HOME"] = str(home)
    env["USERPROFILE"] = str(home)  # Windows HOME resolution
    env["APOTHEM_HOME"] = str(apothem_home)
    return env


def _run_install(
    home: Path, profile: Path, apothem_home: Path, *flags: str
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "apothem",
            "install",
            "--harness",
            HARNESS,
            "--profile",
            str(profile),
            *flags,
        ],
        cwd=str(REPO_ROOT),
        env=_isolated_env(home, apothem_home),
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        timeout=TIMEOUT_SECONDS,
    )


def test_clean_dry_run_previews_and_removes_nothing(tmp_path: Path) -> None:
    home, profile = _arrange_home(tmp_path)

    result = _run_install(
        home, profile, tmp_path / "apothem-home", "--clean", "--dry-run"
    )

    assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    # Nothing removed.
    assert (home / ".claude" / "stale.txt").exists()
    assert (home / ".codex" / "stale.toml").exists()
    assert profile.exists()
    # No fresh materialization happened in dry-run.
    assert not (home / HARNESS_CONFIG_RELATIVE).exists()
    # No backup written in dry-run.
    assert not (home / ".apothem" / "backups").exists()
    assert "dry-run" in result.stdout.lower()
    # The preview covers both phases: removals above, fresh writes below.
    assert "would install" in result.stdout.lower()


def test_clean_dry_run_json_emits_single_envelope(tmp_path: Path) -> None:
    """``install --clean --dry-run --json`` keeps the single-envelope contract.

    The envelope carries the materialization preview in ``results`` and the
    clean-slate removal preview under ``clean`` — one parseable JSON document,
    never silence.
    """
    home, profile = _arrange_home(tmp_path)

    result = _run_install(
        home, profile, tmp_path / "apothem-home", "--clean", "--dry-run", "--json"
    )

    assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    payload = json.loads(result.stdout)
    assert payload["status"] == "dry_run"
    assert payload["command"] == "install"
    assert payload["error"] is None
    clean = payload["clean"]
    assert clean["dry_run"] is True
    assert clean["backup_dir"] is None
    present = [t for t in clean["targets"] if t["present"]]
    assert present, "expected the seeded stale state in the removal preview"
    assert all(t["removed"] is False for t in clean["targets"])
    # Nothing removed, nothing written.
    assert (home / ".claude" / "stale.txt").exists()
    assert not (home / HARNESS_CONFIG_RELATIVE).exists()


def test_clean_yes_backs_up_wipes_restores_profile_and_materializes(
    tmp_path: Path,
) -> None:
    home, profile = _arrange_home(tmp_path)

    result = _run_install(home, profile, tmp_path / "apothem-home", "--clean", "--yes")

    assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"

    # Prior install state is wiped.
    assert not (home / ".claude" / "stale.txt").exists()
    assert not (home / ".codex" / "stale.toml").exists()
    assert not (home / ".agents" / "stale.md").exists()

    # Fresh facade materialized.
    assert (home / HARNESS_CONFIG_RELATIVE).is_file()

    # The profile (identity source of truth) is restored after the wipe.
    assert profile.is_file()
    assert "Clean Slate Gate" in profile.read_text(encoding="utf-8")

    # The unrelated ~/.config app is byte-for-byte preserved.
    preserved = home / ".config" / "other-app" / "keep.conf"
    assert preserved.read_text(encoding="utf-8") == "preserve me"

    # A timestamped backup of the prior state exists.
    backups = home / ".apothem" / "backups"
    assert backups.is_dir()
    backup_runs = list(backups.glob("clean-slate-*"))
    assert backup_runs, "expected a timestamped clean-slate backup directory"
    assert (backup_runs[0] / ".claude" / "stale.txt").read_text() == "stale"

    # The next-step banner names the verify command.
    assert "apothem verify" in result.stdout


def test_clean_without_yes_removes_nothing(tmp_path: Path) -> None:
    """The bounded set is never wiped without an explicit confirmation.

    Driven through a non-interactive subprocess (no TTY, ``stdin`` closed),
    a bare ``--clean`` must not remove any target: it either refuses outright
    (non-interactive without ``--yes``) or, where a prompt is attempted, the
    closed ``stdin`` declines every target. Either path leaves the prior
    install state intact — the safety invariant that matters.
    """
    home, profile = _arrange_home(tmp_path)

    _run_install(home, profile, tmp_path / "apothem-home", "--clean")

    assert (home / ".claude" / "stale.txt").exists()
    assert (home / ".codex" / "stale.toml").exists()
    assert (home / ".agents" / "stale.md").exists()
    assert profile.exists()
