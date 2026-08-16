# SPDX-License-Identifier: MIT

"""Characterization coverage for the coarse surface scanner's CLI.

``scan_ai_surfaces_coarse`` is the cheap pre-scan that runs before the detailed
surface sweep: it asks only whether each instruction surface exists and whether
the mandatory blocks appear inside it. Its whole body lived in ``main`` and
none of it executed under the suite.

Two behaviors are worth pinning beyond the happy path. An absent mandatory
surface and a *present but incomplete* one produce different signals, and the
scanner reports optional surfaces that are present as hits rather than as
absences — the opt-in surfaces are recorded because they exist, not because
they are missing.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from apothem.audit.scan_ai_surfaces_coarse import (
    SEVERITY_HIGH,
    SEVERITY_MEDIUM,
    main,
)

MANDATORY = ("AGENTS.md", "CLAUDE.md")


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """Build a tree carrying only an inventory — every surface absent."""
    (tmp_path / ".audit").mkdir()
    (tmp_path / ".audit" / "inventory.json").write_text(
        json.dumps({"files": []}), encoding="utf-8"
    )
    return tmp_path


def run(workspace: Path) -> int:
    """Invoke ``main`` against the workspace with output redirected."""
    return main(
        [
            "--inventory",
            str(workspace / ".audit" / "inventory.json"),
            "--root",
            str(workspace),
            "--output",
            str(workspace / "out" / "coarse.json"),
        ]
    )


def payload_of(workspace: Path) -> dict:
    """Read the emitted document back."""
    return json.loads((workspace / "out" / "coarse.json").read_text(encoding="utf-8"))


def signals(workspace: Path) -> list[str]:
    """Return every signal the run emitted, in order."""
    return [hit["signal"] for hit in payload_of(workspace)["hits"]]


def test_main_writes_its_document_and_exits_zero(workspace: Path) -> None:
    """An empty tree is a valid scan result, not an error.

    Every surface being absent is exactly what this scanner exists to report,
    so it succeeds and records the absences rather than failing.
    """
    code = run(workspace)

    assert code == 0
    assert (workspace / "out" / "coarse.json").exists()


def test_main_reports_a_missing_inventory_on_stderr_and_exits_one(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The single failure path matches its sibling scanner's."""
    code = main(["--inventory", str(tmp_path / "absent.json"), "--root", str(tmp_path)])

    captured = capsys.readouterr()
    assert code == 1
    assert "inventory not found" in captured.err
    assert captured.out == ""


def test_main_flags_each_absent_mandatory_surface_at_high_severity(
    workspace: Path,
) -> None:
    """Both canonical instruction surfaces missing yields two high hits."""
    run(workspace)
    hits = payload_of(workspace)["hits"]

    absences = {
        h["signal"]: h["severity"] for h in hits if h["signal"].endswith("absent")
    }

    assert absences["agents-md-absent"] == SEVERITY_HIGH
    assert absences["claude-md-absent"] == SEVERITY_HIGH


def test_main_ranks_the_copilot_surface_below_the_canonical_pair(
    workspace: Path,
) -> None:
    """A missing Copilot surface is medium, not high.

    The distinction is deliberate: without AGENTS.md the downstream discipline
    has no source, whereas without the Copilot mirror that one harness simply
    falls back to its own defaults.
    """
    run(workspace)
    hits = {h["signal"]: h["severity"] for h in payload_of(workspace)["hits"]}

    assert hits["copilot-instructions-absent"] == SEVERITY_MEDIUM


def test_main_distinguishes_an_incomplete_surface_from_an_absent_one(
    workspace: Path,
) -> None:
    """A present surface missing its blocks reports a different signal.

    This is the check that makes the scan worth running on a repo that already
    has the files: presence alone is not coverage.
    """
    for name in MANDATORY:
        (workspace / name).write_text("# Title\n\nnothing canonical here\n", "utf-8")

    run(workspace)
    emitted = signals(workspace)

    assert "agents-md-absent" not in emitted
    assert any(s.startswith("instruction-surface-missing-block: ") for s in emitted)


def test_main_records_an_optional_surface_because_it_is_present(
    workspace: Path,
) -> None:
    """Opt-in surfaces are reported for existing, not for being missing.

    Note the scanner tests these with ``.exists()``, so a *directory* at an
    opt-in path also reads as an authored surface. Pinned as current
    behavior, not endorsed.
    """
    (workspace / ".cursorrules").write_text("rules\n", encoding="utf-8")

    run(workspace)

    assert ".cursorrules" in payload_of(workspace)["optional-surfaces-present"]
    assert any(s.startswith("optional-surface-present: ") for s in signals(workspace))


def test_main_summary_line_names_every_surface_class(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """One stdout line carries the whole verdict, keyed by surface."""
    run(workspace)

    summary = capsys.readouterr().out.strip()

    assert summary.startswith("scan_ai_surfaces_coarse: AGENTS.md=False")
    assert "CLAUDE.md=False" in summary
    assert "copilot-instructions=False" in summary
    assert "total hits=" in summary


def test_main_presence_flags_track_the_files_on_disk(workspace: Path) -> None:
    """The envelope's booleans are read from the tree, not from the hit list."""
    (workspace / "AGENTS.md").write_text("# Agents\n", encoding="utf-8")

    run(workspace)
    payload = payload_of(workspace)

    assert payload["agents-md-present"] is True
    assert payload["claude-md-present"] is False
    assert payload["hit-count"] == len(payload["hits"])
