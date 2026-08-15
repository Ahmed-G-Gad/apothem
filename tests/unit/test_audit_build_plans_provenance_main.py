# SPDX-License-Identifier: MIT

"""Characterization coverage for the provenance builder's CLI entry point.

``main`` runs the whole three-pass pipeline: scan each plan file's body,
resolve a destination per suite, then build per-file records that inherit
their suite's verdict. Driving it end to end is also what exercises
``_derive_known_projects``, ``_record_for``, and the known-projects template
writer, none of which had any coverage.

Three behaviors here are easy to miss by reading and worth pinning:

- a plan-artifact that is not under the legacy ``.plans/`` root is skipped
  outright, not recorded with an empty suite;
- a plan-artifact the scanner cannot read as text still gets a record, with
  empty signals, so a suite migrates as a unit rather than as a text-only
  subset;
- when the operator supplies no known-projects file, the builder derives one
  from the signals it just observed and writes it back for review — a run
  with no registry is not the same as a run with an empty one.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from apothem.audit.build_plans_provenance import main

SUITE = "my-suite"
REPO_URL = "https://github.com/owner/some-project"


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """Build a legacy plan-suite tree plus the inventory that indexes it."""
    suite_dir = tmp_path / ".plans" / SUITE
    suite_dir.mkdir(parents=True)
    (suite_dir / "PROGRESS.md").write_text(
        f"---\nproject: some-project\ntitle: Progress\n---\n"
        f"# Progress\n\nWork tracked at {REPO_URL} for now.\n",
        encoding="utf-8",
    )
    (tmp_path / ".audit").mkdir()
    (tmp_path / ".audit" / "inventory.json").write_text(
        json.dumps(
            {
                "files": [
                    {"path": f".plans/{SUITE}/PROGRESS.md", "class": "plan-artifact"},
                    {"path": "src/apothem/cli/install.py", "class": "source"},
                ]
            }
        ),
        encoding="utf-8",
    )
    return tmp_path


def run(workspace: Path, known: Path | None = None) -> int:
    """Invoke ``main`` with every output redirected under the workspace."""
    return main(
        [
            "--inventory",
            str(workspace / ".audit" / "inventory.json"),
            "--root",
            str(workspace),
            "--known-projects",
            str(known or workspace / "known-projects.txt"),
            "--output-json",
            str(workspace / "out" / "provenance.json"),
            "--output-md",
            str(workspace / "out" / "provenance.md"),
        ]
    )


def payload_of(workspace: Path) -> dict:
    """Read the emitted JSON envelope back."""
    return json.loads((workspace / "out" / "provenance.json").read_text("utf-8"))


def test_main_writes_both_documents_and_exits_zero(workspace: Path) -> None:
    """A successful run leaves the JSON envelope and its markdown mirror."""
    code = run(workspace)

    assert code == 0
    assert (workspace / "out" / "provenance.json").exists()
    assert (workspace / "out" / "provenance.md").exists()


def test_main_reports_a_missing_inventory_on_stderr_and_exits_one(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The single failure path matches its sibling scanners'."""
    code = main(["--inventory", str(tmp_path / "absent.json"), "--root", str(tmp_path)])

    captured = capsys.readouterr()
    assert code == 1
    assert "inventory not found" in captured.err
    assert captured.out == ""


def test_main_records_only_plan_artifacts_under_the_legacy_root(
    workspace: Path,
) -> None:
    """A source file is filtered out; a plan file under ``.plans`` is kept."""
    run(workspace)
    payload = payload_of(workspace)

    assert [f["path"] for f in payload["files"]] == [f".plans/{SUITE}/PROGRESS.md"]
    assert list(payload["suites"]) == [SUITE]


def test_main_skips_a_plan_artifact_that_carries_no_suite(workspace: Path) -> None:
    """A plan-artifact outside ``.plans/`` is dropped, not filed under "".

    The builder is migration-era tooling scoped to the legacy layout; a record
    with no suite has no verdict to inherit, so it is skipped rather than
    given an empty one.
    """
    (workspace / "stray.md").write_text("# Stray\n", encoding="utf-8")
    inventory = workspace / ".audit" / "inventory.json"
    payload = json.loads(inventory.read_text(encoding="utf-8"))
    payload["files"].append({"path": "stray.md", "class": "plan-artifact"})
    inventory.write_text(json.dumps(payload), encoding="utf-8")

    run(workspace)

    assert "stray.md" not in [f["path"] for f in payload_of(workspace)["files"]]


def test_main_records_a_non_text_plan_artifact_with_empty_signals(
    workspace: Path,
) -> None:
    """A suite migrates as a unit, so a JSON capture is recorded too.

    It carries no body signals — the scan only reads the text extensions —
    but it still inherits its suite's verdict and appears in the per-file
    table.
    """
    (workspace / ".plans" / SUITE / "capture.json").write_text("{}", encoding="utf-8")
    inventory = workspace / ".audit" / "inventory.json"
    payload = json.loads(inventory.read_text(encoding="utf-8"))
    payload["files"].append(
        {"path": f".plans/{SUITE}/capture.json", "class": "plan-artifact"}
    )
    inventory.write_text(json.dumps(payload), encoding="utf-8")

    run(workspace)
    files = {f["path"]: f for f in payload_of(workspace)["files"]}
    capture = files[f".plans/{SUITE}/capture.json"]

    assert capture["signals"]["repo_urls"] == []
    assert capture["confidence"] == files[f".plans/{SUITE}/PROGRESS.md"]["confidence"]


def test_main_derives_a_known_projects_file_when_none_exists(
    workspace: Path,
) -> None:
    """With no registry, the builder writes one from the signals it observed.

    The derived file is a template for operator review, which is why it is
    persisted rather than held in memory: the next run should start from a
    ratified registry, not re-derive one.
    """
    registry = workspace / "known-projects.txt"
    assert not registry.exists()

    run(workspace)

    assert registry.exists()
    assert "some-project" in registry.read_text(encoding="utf-8")


def test_main_prefers_a_supplied_registry_over_deriving_one(
    workspace: Path,
) -> None:
    """An operator-ratified registry is used as-is and never overwritten."""
    registry = workspace / "known-projects.txt"
    registry.write_text("ratified = https://example.invalid/o/ratified\n", "utf-8")

    run(workspace)

    assert registry.read_text(encoding="utf-8").startswith("ratified = ")


def test_main_prints_a_summary_then_one_line_per_suite(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The operator gets a total, then each suite's verdict and destination."""
    run(workspace)
    lines = capsys.readouterr().out.strip().splitlines()

    assert lines[0].startswith("build_plans_provenance: 1 plan file(s) across 1 suite")
    assert "known-projects entries:" in lines[0]
    assert lines[1].strip().startswith(f"{SUITE} (1 files):")


def test_main_anchors_the_envelope_to_the_inventory_digest(
    workspace: Path,
) -> None:
    """The digest is how a downstream pass detects a stale provenance run."""
    expected = hashlib.sha256(
        (workspace / ".audit" / "inventory.json").read_bytes()
    ).hexdigest()

    run(workspace)

    assert payload_of(workspace)["inventory-source-sha256"] == expected


def test_main_gives_every_record_a_proposed_filename(workspace: Path) -> None:
    """Each record carries the name the migration would move it to.

    The frontmatter title wins over the heading, so the declared "Progress"
    is what the slug comes from.
    """
    run(workspace)
    record = payload_of(workspace)["files"][0]

    assert record["proposed-destination-filename"].endswith("--progress.md")
