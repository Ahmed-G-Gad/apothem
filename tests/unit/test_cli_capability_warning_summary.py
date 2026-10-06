# SPDX-License-Identifier: MIT

"""UX-1 regression: the capability-warning plain-mode downgrade.

Install/update materialization emits one capability-projection warning per
registry cell that is ``unsupported``/``discovery-pending`` for a harness —
83 across the seventeen adapters. The pre-UX-1 plain-text render printed one
``Warning:`` line per cell, a flood that buried the ``✓`` success lines on a
plain ``install --harness all``.

UX-1 reclassifies that flood: in plain mode each warned harness collapses to a
single grouped ``Note:`` line (count + a pointer to ``--verbose``); the full
per-cell detail prints only under ``--verbose``; and the ``--format json``
lifecycle envelope keeps every warning regardless of verbosity, so machine
consumers are unaffected.

Advisories (``outcome: "advisory"``, such as the shared-root advisory that names
the other tools loading a path an install writes) are not capability cells.
They print as their own ``Note:`` lines in both modes and ride the same JSON
``warnings`` array, so the grouped count covers capability cells only.

These tests drive the real seventeen-adapter registry through the CLI install
path under an isolated HOME so no real harness state is touched.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from click.testing import CliRunner

from apothem.cli import main
from apothem.harnesses._shared import install_driver

# ``Note: <harness> - N capabilit{y,ies} not projected; pass --verbose for detail``
_NOTE_RE = re.compile(
    r"^Note:\s+(?P<harness>[a-z0-9-]+)\s+-\s+(?P<count>\d+)\s+"
    r"capabilit(?:y|ies)\s+not projected; pass --verbose for detail$"
)
_PROFILE = (
    "identity:\n  name: Test User\n"
    "preferences:\n  language: python\n"
    "seriousness: PERSONAL_USE\n"
)


@pytest.fixture
def install_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """Isolate HOME/APOTHEM_HOME so install-all writes only under tmp_path.

    Global-scope adapters resolve their targets from the home directory; the
    redirect keeps every write inside the temp tree, and the BACKUP_ROOT
    override keeps any backup off the real machine. Returns ``(profile, project)``.
    """
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))  # Windows HOME resolution
    monkeypatch.setenv("APOTHEM_HOME", str(tmp_path / "apothem-home"))
    monkeypatch.setattr(install_driver, "BACKUP_ROOT", tmp_path / "backups")

    profile = tmp_path / "profile.yaml"
    profile.write_text(_PROFILE, encoding="utf-8")
    project = tmp_path / "proj"
    project.mkdir()
    return profile, project


def _install(runner: CliRunner, profile: Path, project: Path, *flags: str) -> list[str]:
    result = runner.invoke(
        main,
        [
            "install",
            "--harness",
            "all",
            "--profile",
            str(profile),
            "--project",
            str(project),
            "--no-color",
            *flags,
        ],
    )
    assert result.exit_code == 0, result.output
    return result.output.splitlines()


def test_plain_install_all_groups_warnings_into_one_note_per_harness(
    runner: CliRunner, install_env: tuple[Path, Path]
) -> None:
    """Plain install-all: zero per-cell ``Warning:`` lines, one Note per harness."""
    profile, project = install_env
    lines = _install(runner, profile, project)

    warning_lines = [line for line in lines if "Warning:" in line]
    note_lines = [line for line in lines if line.startswith("Note:")]
    capability_notes = [line for line in note_lines if _NOTE_RE.match(line)]

    # The flood is gone: not a single per-cell Warning line in plain mode.
    assert warning_lines == []
    # At least one harness has a non-projected capability, so a Note appears.
    assert capability_notes
    # Every capability Note matches the grouped summary shape (count + --verbose
    # pointer); other Note lines are advisories, which are never grouped.
    harnesses = []
    for line in capability_notes:
        match = _NOTE_RE.match(line)
        assert match is not None
        assert int(match["count"]) >= 1
        harnesses.append(match["harness"])
    # At most one Note line per warned harness — no harness summarized twice.
    assert len(harnesses) == len(set(harnesses))
    # The success/✓ lines still print alongside the grouped notes.
    assert any("Installed" in line for line in lines)


def test_verbose_install_all_prints_per_cell_warning_detail(
    runner: CliRunner, install_env: tuple[Path, Path]
) -> None:
    """``--verbose``: the grouped Note is replaced by one line per warned cell."""
    profile, project = install_env

    json_lines = _install(runner, profile, project, "--format", "json")
    payload = json.loads("\n".join(json_lines))
    total_warnings = sum(1 for w in payload["warnings"] if w["outcome"] == "warning")
    assert total_warnings > 16  # more per-cell warnings than harnesses

    verbose_lines = _install(runner, profile, project, "--verbose")
    warning_lines = [line for line in verbose_lines if line.startswith("Warning:")]
    summary_lines = [line for line in verbose_lines if _NOTE_RE.match(line)]

    # Under --verbose the grouped summary is suppressed in favour of detail.
    assert summary_lines == []
    # Exactly one Warning line per warning in the envelope — the full detail.
    assert len(warning_lines) == total_warnings
    # Each detail line is harness-attributed ("Warning: <harness> - <rationale>").
    for line in warning_lines:
        assert re.match(r"^Warning:\s+[a-z0-9-]+\s+-\s+\S", line), line


def test_json_warning_count_identical_with_and_without_verbose(
    runner: CliRunner, install_env: tuple[Path, Path]
) -> None:
    """``--format json`` carries the same warnings array regardless of verbosity."""
    profile, project = install_env

    plain = json.loads(
        "\n".join(_install(runner, profile, project, "--format", "json"))
    )
    verbose = json.loads(
        "\n".join(_install(runner, profile, project, "--format", "json", "--verbose"))
    )

    # Advisories depend on what earlier runs left on disk (a reader advisory
    # appears once another install has written a shared root), and both runs
    # share one HOME, so the comparison covers adapter warnings only.
    plain_warnings = [w for w in plain["warnings"] if w["outcome"] == "warning"]
    verbose_warnings = [w for w in verbose["warnings"] if w["outcome"] == "warning"]
    plain_msgs = sorted(str(w["message"]) for w in plain_warnings)
    verbose_msgs = sorted(str(w["message"]) for w in verbose_warnings)

    assert len(plain_warnings) == len(verbose_warnings)
    assert plain_msgs == verbose_msgs
    # The grouped plain-mode counts sum to the full envelope total (no data lost).
    note_total = sum(
        int(m["count"])
        for line in _install(runner, profile, project)
        if (m := _NOTE_RE.match(line))
    )
    capability_total = sum(
        1 for w in plain["warnings"] if w["operation"] == "capability_projection"
    )
    assert note_total == capability_total


def test_single_harness_plain_groups_verbose_expands(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A single project-scope harness: one Note in plain mode, full detail verbose."""
    # An empty home: a shared root that already holds another tool's Apothem
    # content would add a reader Note to the count.
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    profile = tmp_path / "profile.yaml"
    profile.write_text(_PROFILE, encoding="utf-8")

    def run(project: Path, *flags: str) -> str:
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
                "--no-color",
                *flags,
            ],
        )
        assert result.exit_code == 0, result.output
        return result.output

    plain_proj = tmp_path / "plain"
    plain_proj.mkdir()
    plain = run(plain_proj)
    plain_notes = [line for line in plain.splitlines() if line.startswith("Note:")]
    assert len(plain_notes) == 1
    assert _NOTE_RE.match(plain_notes[0]) is not None
    assert "Warning:" not in plain

    verbose_proj = tmp_path / "verbose"
    verbose_proj.mkdir()
    verbose = run(verbose_proj, "--verbose")
    verbose_warnings = [
        line for line in verbose.splitlines() if line.startswith("Warning:")
    ]
    grouped_count = int(_NOTE_RE.match(plain_notes[0])["count"])  # type: ignore[index]
    assert len(verbose_warnings) == grouped_count
    assert "Note:" not in verbose
