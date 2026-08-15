# SPDX-License-Identifier: MIT

"""Characterization coverage for the AI-surface scanner's CLI entry point.

``main`` is the only surface an operator actually invokes, and it was the last
dark region of ``scan_ai_surfaces`` — the piece that decides what a missing
inventory does, where the two documents land, and what the shell sees on the
way out.

The contract worth pinning is the operator-facing one: the exit code, the
stream each message goes to, and the fact that both documents are written
before anything is reported. A scanner that emitted its summary and then failed
to write would look successful in a log.

The scanner walks a real directory tree, so every test builds one under
``tmp_path`` and points ``--root`` at it. Nothing here touches the repository's
own ``.audit/`` tree.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from apothem.audit.scan_ai_surfaces import main


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """Build a minimal tree with an inventory and one present surface."""
    (tmp_path / ".audit").mkdir()
    (tmp_path / ".audit" / "inventory.json").write_text(
        json.dumps({"files": []}), encoding="utf-8"
    )
    (tmp_path / "AGENTS.md").write_text(
        "# Agents\n\n## Plans Discipline\n\nPlans live under .apothem/plans/.\n",
        encoding="utf-8",
    )
    return tmp_path


def run(workspace: Path, *extra: str) -> int:
    """Invoke ``main`` against the workspace with both outputs redirected."""
    return main(
        [
            "--inventory",
            str(workspace / ".audit" / "inventory.json"),
            "--coarse",
            str(workspace / ".audit" / "absent-coarse.json"),
            "--root",
            str(workspace),
            "--out-json",
            str(workspace / "out" / "ai-surfaces.json"),
            "--out-md",
            str(workspace / "out" / "ai-surfaces.md"),
            *extra,
        ]
    )


def test_main_writes_both_documents_and_exits_zero(workspace: Path) -> None:
    """A successful run leaves the JSON envelope and its markdown mirror."""
    code = run(workspace)

    assert code == 0
    assert (workspace / "out" / "ai-surfaces.json").exists()
    assert (workspace / "out" / "ai-surfaces.md").exists()


def test_main_creates_the_output_directory_it_was_given(workspace: Path) -> None:
    """Neither emitter requires the caller to have made the parent tree.

    The default output path is under ``.audit/``, which is generated state a
    clean checkout does not carry, so the run has to make its own way there.
    """
    assert not (workspace / "out").exists()

    run(workspace)

    assert (workspace / "out").is_dir()


def test_main_reports_a_missing_inventory_on_stderr_and_exits_one(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The one failure path: no inventory, no scan, exit 1.

    The message goes to stderr rather than stdout, so a caller piping the
    summary into another tool gets an empty pipe rather than an error string
    parsed as data.
    """
    code = main(["--inventory", str(tmp_path / "absent.json"), "--root", str(tmp_path)])

    captured = capsys.readouterr()
    assert code == 1
    assert "inventory not found" in captured.err
    assert captured.out == ""


def test_main_prints_a_single_summary_line_to_stdout(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The summary is one parseable line naming every count that matters."""
    run(workspace)

    summary = capsys.readouterr().out.strip().splitlines()[0]

    assert summary.startswith("scan_ai_surfaces: candidates=")
    for field in (
        "present=",
        "absent=",
        "mandatory-absent=",
        "pairs=",
        "plan-actions=",
    ):
        assert field in summary


def test_main_names_missing_mandatory_surfaces_on_stderr(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Absent mandatory surfaces are named individually, not just counted.

    The count goes in the stdout summary and the names go to stderr, so the
    operator sees which files to author without the summary line growing
    unbounded with the number of them.
    """
    run(workspace)

    captured = capsys.readouterr()
    assert "mandatory-absent: " in captured.err
    assert "CLAUDE.md" in captured.err


def test_main_anchors_the_envelope_to_the_inventory_digest(workspace: Path) -> None:
    """The output records which inventory snapshot it was computed against.

    That digest is how a downstream pass detects a stale scan, so it has to
    be the hash of the file actually read rather than a recomputed guess.
    """
    inventory = workspace / ".audit" / "inventory.json"
    expected = hashlib.sha256(inventory.read_bytes()).hexdigest()

    run(workspace)
    payload = json.loads(
        (workspace / "out" / "ai-surfaces.json").read_text(encoding="utf-8")
    )

    assert payload["inventory-source-sha256"] == expected


def test_main_records_the_coarse_digest_only_when_that_file_exists(
    workspace: Path,
) -> None:
    """The coarse pre-scan is optional, and its absence is not an error."""
    run(workspace)
    without = json.loads(
        (workspace / "out" / "ai-surfaces.json").read_text(encoding="utf-8")
    )

    coarse = workspace / ".audit" / "coarse.json"
    coarse.write_text('{"drift": []}', encoding="utf-8")
    main(
        [
            "--inventory",
            str(workspace / ".audit" / "inventory.json"),
            "--coarse",
            str(coarse),
            "--root",
            str(workspace),
            "--out-json",
            str(workspace / "out" / "ai-surfaces.json"),
            "--out-md",
            str(workspace / "out" / "ai-surfaces.md"),
        ]
    )
    with_coarse = json.loads(
        (workspace / "out" / "ai-surfaces.json").read_text(encoding="utf-8")
    )

    assert without["coarse-source-sha256"] is None
    assert with_coarse["coarse-source-sha256"] is not None


def test_main_finds_a_surface_that_exists_under_the_given_root(
    workspace: Path,
) -> None:
    """``--root`` is what the candidate paths resolve against.

    The workspace carries an AGENTS.md and nothing else, so exactly one
    surface should come back present — which also proves the scan is reading
    the given root rather than the working directory.
    """
    run(workspace)
    payload = json.loads(
        (workspace / "out" / "ai-surfaces.json").read_text(encoding="utf-8")
    )

    present = [s for s in payload["surfaces"] if s["presence"] == "present"]

    assert [s["path"] for s in present] == ["AGENTS.md"]
