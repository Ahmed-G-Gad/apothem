# SPDX-License-Identifier: MIT

"""Behavioral tests for the read-only ``status`` and ``diff`` CLI commands.

Both commands are inspection-only: they report install / verify / drift state
(``status``) and the pending dry-run plan with diffs (``diff``) without writing
to disk. The tests assert the stable JSON envelopes, per-adapter failure
isolation, project-scope graceful degradation, and the read-only invariant.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from apothem.cli import main
from apothem.harnesses._shared import install_driver
from apothem.harnesses._shared.install_driver import (
    MaterializationResult,
    MaterializationRun,
)
from apothem.lib.harness_registry import SUPPORTED_HARNESS_IDS, iter_harness_entries


def _write_valid_profile(path: Path) -> None:
    path.write_text("identity:\n  name: Example User\n", encoding="utf-8")


# -----------------------------------------------------------------------
# status
# -----------------------------------------------------------------------


def test_status_lists_every_registered_harness(runner: CliRunner) -> None:
    result = runner.invoke(main, ["status"])
    assert result.exit_code == 0, result.output
    # Every registered harness id appears exactly once in the plain table.
    for harness_id in SUPPORTED_HARNESS_IDS:
        assert harness_id in result.output


def test_status_json_envelope_one_entry_per_harness(runner: CliRunner) -> None:
    result = runner.invoke(main, ["status", "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output.strip())
    assert data["command"] == "status"
    assert data["status"] == "success"
    assert data["harness"] == "all"
    results = data["results"]
    assert len(results) == len(SUPPORTED_HARNESS_IDS)
    seen = {row["harness"] for row in results}
    assert seen == set(SUPPORTED_HARNESS_IDS)
    for row in results:
        # Documented key set: harness + installed + verified + drift.
        assert {"harness", "installed", "verified", "drift"} <= set(row)
        assert isinstance(row["installed"], bool)
        assert isinstance(row["verified"], bool)
        assert isinstance(row["drift"], str)


def test_status_drift_is_absent_when_not_installed(runner: CliRunner) -> None:
    result = runner.invoke(main, ["status", "--json"])
    data = json.loads(result.output.strip())
    rows = {row["harness"]: row for row in data["results"]}
    for row in rows.values():
        if not row["installed"] and row["drift"] != "needs-project":
            assert row["drift"] == "absent"


def test_status_project_scope_degrades_without_project(runner: CliRunner) -> None:
    result = runner.invoke(main, ["status", "--json"])
    data = json.loads(result.output.strip())
    project_ids = {
        entry.public_id for entry in iter_harness_entries() if entry.scope == "project"
    }
    rows = {row["harness"]: row for row in data["results"]}
    for harness_id in project_ids:
        assert rows[harness_id]["drift"] == "needs-project"
        assert rows[harness_id]["installed"] is False
    # The command does not crash and still exits 0.
    assert result.exit_code == 0


def test_status_isolates_per_adapter_failure(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    from apothem.cli import _load_adapter_for_entry as _real_load

    def _exploding_load(entry):  # type: ignore[no-untyped-def]
        # One specific adapter raises while loading; every other adapter loads
        # normally so the sweep must still report the rest.
        if entry.public_id == "claude-code":
            raise RuntimeError("boom: adapter exploded")
        return _real_load(entry)

    monkeypatch.setattr("apothem.cli._load_adapter_for_entry", _exploding_load)
    result = runner.invoke(main, ["status", "--json"])
    # A per-adapter failure degrades that row but does not abort the sweep.
    assert result.exit_code == 2, result.output
    data = json.loads(result.output.strip())
    assert len(data["results"]) == len(SUPPORTED_HARNESS_IDS)
    rows = {row["harness"]: row for row in data["results"]}
    assert rows["claude-code"]["outcome"] == "error"
    # Other adapters still rendered their normal status rows.
    other = next(r for r in SUPPORTED_HARNESS_IDS if r != "claude-code")
    assert "installed" in rows[other]


# -----------------------------------------------------------------------
# diff
# -----------------------------------------------------------------------


def test_diff_requires_harness(runner: CliRunner) -> None:
    result = runner.invoke(main, ["diff"])
    assert result.exit_code != 0
    assert "harness" in result.output.lower()


def test_diff_rejects_all(runner: CliRunner, tmp_path: Path) -> None:
    profile = tmp_path / "profile.yaml"
    _write_valid_profile(profile)
    result = runner.invoke(
        main, ["diff", "--harness", "all", "--profile", str(profile)]
    )
    assert result.exit_code == 1, result.output


def test_diff_shows_planned_changes(runner: CliRunner, tmp_path: Path) -> None:
    profile = tmp_path / "profile.yaml"
    _write_valid_profile(profile)
    result = runner.invoke(
        main, ["diff", "--harness", "claude-code", "--profile", str(profile)]
    )
    assert result.exit_code == 0, result.output
    assert "Pending changes for" in result.output
    assert "claude-code" in result.output


def test_diff_json_envelope_parity(runner: CliRunner, tmp_path: Path) -> None:
    profile = tmp_path / "profile.yaml"
    _write_valid_profile(profile)
    result = runner.invoke(
        main,
        ["diff", "--harness", "claude-code", "--profile", str(profile), "--json"],
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output.strip())
    assert data["command"] == "diff"
    assert data["status"] == "dry_run"
    assert data["harness"] == "claude-code"
    assert data["files_written"] == []
    assert "materialization" in data
    assert isinstance(data["results"], list)
    for row in data["results"]:
        assert row["harness"] == "claude-code"
        assert {"outcome", "operation", "path"} <= set(row)


def test_diff_project_scope_requires_project(runner: CliRunner, tmp_path: Path) -> None:
    profile = tmp_path / "profile.yaml"
    _write_valid_profile(profile)
    result = runner.invoke(
        main, ["diff", "--harness", "cursor", "--profile", str(profile)]
    )
    assert result.exit_code == 1, result.output
    assert "project" in result.output.lower()


def test_diff_project_scope_with_project(runner: CliRunner, tmp_path: Path) -> None:
    profile = tmp_path / "profile.yaml"
    _write_valid_profile(profile)
    project = tmp_path / "proj"
    project.mkdir()
    result = runner.invoke(
        main,
        [
            "diff",
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
    assert data["command"] == "diff"
    assert data["status"] == "dry_run"


# -----------------------------------------------------------------------
# read-only invariant
# -----------------------------------------------------------------------


def test_status_is_read_only(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    backup_root = tmp_path / "backups"
    monkeypatch.setattr(install_driver, "BACKUP_ROOT", backup_root)
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    before = {p.name for p in scratch.iterdir()}
    result = runner.invoke(main, ["status", "--project", str(scratch)])
    after = {p.name for p in scratch.iterdir()}
    assert result.exit_code in (0, 2), result.output
    # No backups created, no files written into the scratch project tree.
    assert before == after
    assert not backup_root.exists()


def test_diff_is_read_only(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    backup_root = tmp_path / "backups"
    monkeypatch.setattr(install_driver, "BACKUP_ROOT", backup_root)
    profile = tmp_path / "profile.yaml"
    _write_valid_profile(profile)
    project = tmp_path / "proj"
    project.mkdir()
    before = {p.name for p in project.iterdir()}
    result = runner.invoke(
        main,
        [
            "diff",
            "--harness",
            "cursor",
            "--profile",
            str(profile),
            "--project",
            str(project),
        ],
    )
    after = {p.name for p in project.iterdir()}
    assert result.exit_code == 0, result.output
    assert before == after
    assert not backup_root.exists()


# -----------------------------------------------------------------------
# Rich-markup escaping of operator/file-derived text
# -----------------------------------------------------------------------

# A path segment and a diff line that both carry Rich-markup control
# sequences. Interpolated raw into a ``console.print`` markup string these
# either raise ``rich.markup.MarkupError`` (unbalanced tags) or silently
# restyle the output; each dynamic site must pass through ``escape()``.
_BRACKET_PATH = "config/weird[bold]dir[/]/settings.json"
_BRACKET_DIFF = "\n".join(
    [
        "--- before",
        "+++ after",
        "+added [green]literal[/] value",
        "-removed [/unbalanced tag",
        " context [dim]run[/dim] line",
    ]
)


def test_diff_escapes_bracketed_path_and_diff_lines(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Bracket-bearing path/diff content renders without a MarkupError.

    The dry-run plan is operator- and file-derived: a target path or a diff
    line may contain ``[...]`` sequences that Rich would parse as markup. The
    render path must escape every dynamic segment so the literal text survives
    verbatim and the console never raises ``rich.markup.MarkupError``.
    """
    profile = tmp_path / "profile.yaml"
    _write_valid_profile(profile)

    crafted = MaterializationRun(
        harness="claude-code",
        dry_run=True,
        results=(
            MaterializationResult(
                outcome="updated",
                operation="write_managed_file",
                path=_BRACKET_PATH,
                message="would update",
                detail={"diff": _BRACKET_DIFF},
            ),
        ),
    )
    monkeypatch.setattr("apothem.cli._cmd_diff._dry_run_plan", lambda *a, **k: crafted)

    result = runner.invoke(
        main,
        ["diff", "--harness", "claude-code", "--profile", str(profile), "--verbose"],
    )

    # No MarkupError bubbled up as a nonzero exit or a raised exception, and
    # the render completed.
    assert result.exception is None, result.exception
    assert result.exit_code == 0, result.output
    # The bracketed path and diff-line content survive verbatim (escaped, not
    # dropped or restyled away).
    assert _BRACKET_PATH in result.output
    assert "+added [green]literal[/] value" in result.output
    assert "-removed [/unbalanced tag" in result.output


def test_migrate_workspace_escapes_bracketed_base_path(
    runner: CliRunner, tmp_path: Path
) -> None:
    """A ``--project`` root carrying markup brackets renders without error.

    ``migrate-workspace`` interpolates the resolved base path into a styled
    ``console.print`` line; a bracketed directory name must be escaped so the
    dry-run report renders faithfully instead of raising a MarkupError.
    """
    # An unbalanced open tag (``[bold]`` with no closing ``[/]``) is what Rich
    # would parse as markup and choke on; the bracket chars are still a legal
    # directory-name segment on every supported platform.
    project = tmp_path / "weird[bold]proj"
    project.mkdir()

    result = runner.invoke(
        main,
        ["migrate-workspace", "--project", str(project), "--dry-run"],
    )

    assert result.exception is None, result.exception
    assert result.exit_code == 0, result.output
    # The literal bracketed segment survives in the rendered line. Rich may
    # break the long absolute path across console lines — a narrow CI terminal
    # splits the basename itself (``weird[b\nold]proj``) — so collapse all
    # whitespace before the substring check. The whitespace-free needle still
    # discriminates the failure mode under test: had ``[bold]`` been parsed as
    # markup rather than escaped, the brackets would be consumed entirely
    # (``weirdproj``), which no amount of unwrapping restores.
    rendered = "".join(result.output.split())
    assert "weird[bold]proj" in rendered, result.output
