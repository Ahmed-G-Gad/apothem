# SPDX-License-Identifier: MIT

"""A write that a link leads out of the allowed folder names that link.

The write guard refuses a target that resolves outside the allowed folder
with ``target escapes the allowed materialization root``. When a link inside
that folder is what leads the target out, the refusal also records the link
and where it leads (``detail["symlink"]`` and ``detail["leads_to"]``), so the
CLI names the link and gives the fix. An escape spelled with ``..`` names no
link, and nor does a link above the allowed folder.

Creating a symbolic link needs a privilege some Windows hosts lack, so there
each link is a junction.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

from apothem.cli import main
from apothem.harnesses._shared import install_driver_pathsafety as pathsafety
from apothem.harnesses._shared.install_driver_backup import _replace_path
from apothem.harnesses._shared.install_driver_homelink import (
    link_refusal_reason_and_fix,
)
from apothem.harnesses._shared.install_driver_sweep import stale_blocker
from apothem.harnesses._shared.install_driver_written import remove_written
from tests._shared.case_sensitive import case_sensitive_folder

ESCAPE = "target escapes the allowed materialization root"


def _link(link: Path, target: Path) -> None:
    """Make *link* lead to *target*: a symbolic link, or a junction on Windows."""
    target.mkdir(parents=True, exist_ok=True)
    link.parent.mkdir(parents=True, exist_ok=True)
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        if sys.platform != "win32":
            pytest.skip("this host cannot create a directory link")
        import _winapi

        _winapi.CreateJunction(str(target), str(link))


def test_an_escape_through_a_user_level_link_names_the_link(tmp_path: Path) -> None:
    home = Path.home()
    outside = tmp_path / "outside" / "skills"
    _link(home / ".agents" / "skills", outside)
    target = home / ".agents" / "skills" / "x" / "SKILL.md"

    error = pathsafety._validate_target_path(target, allowed_root=home, operation="t")

    assert error is not None
    assert error.message == ESCAPE
    assert error.detail["symlink"] == str(home / ".agents" / "skills")
    assert error.detail["leads_to"] == str(outside.resolve())
    reason, fix = link_refusal_reason_and_fix(error) or ("", "")
    assert reason == (
        f"{ESCAPE}: {home / '.agents' / 'skills'} is a link to {outside.resolve()}"
    )
    assert fix.startswith(f"Replace the link {home / '.agents' / 'skills'} with ")


def test_an_escape_through_a_link_inside_a_project_names_that_link(
    tmp_path: Path,
) -> None:
    # The project folder the operator named is itself a link, and is followed;
    # the link inside it that leads out is the one named.
    project = tmp_path / "proj"
    _link(project, tmp_path / "real" / "proj")
    _link(project / ".cursor", tmp_path / "elsewhere")
    floor = pathsafety._allowed_write_root(None, project)

    # The floor object itself, as the writers pass it (see _write_boundary).
    error = pathsafety._validate_target_path(
        project / ".cursor" / "x.md", allowed_root=floor, operation="t"
    )

    assert error is not None
    assert error.message == ESCAPE
    assert error.detail["symlink"] == str(project / ".cursor")


def test_an_escape_spelled_with_dots_names_no_link(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    _link(tmp_path / "away", tmp_path / "outside")

    error = pathsafety._validate_target_path(
        root / ".." / "away" / "x.md", allowed_root=root, operation="t"
    )

    assert error is not None
    assert error.message == ESCAPE
    assert "symlink" not in error.detail


def test_an_escape_spelled_with_another_case_names_no_link(tmp_path: Path) -> None:
    # In a folder that tells ``root`` from ``Root``, ``Root`` is another
    # folder: its link is outside the allowed folder, so it is not the cause.
    base = tmp_path / "cs"
    case_sensitive_folder(base)
    root = base / "root"
    root.mkdir()
    _link(base / "Root" / "away", tmp_path / "outside")

    error = pathsafety._validate_target_path(
        base / "Root" / "away" / "x.md", allowed_root=root, operation="t"
    )

    assert error is not None
    assert error.message == ESCAPE
    assert "symlink" not in error.detail


def test_the_sweep_and_the_removals_still_refuse_an_escape_through_a_link(
    tmp_path: Path,
) -> None:
    # The stale sweep and both removal paths decide on the link check, not on
    # the link the refusal names: a path behind a user-level link that leads
    # out of the home is still refused with an error, now naming the link.
    home = Path.home()
    outside = tmp_path / "outside" / "skills"
    _link(home / ".agents" / "skills", outside)
    (outside / "x").mkdir()
    (outside / "x" / "SKILL.md").write_text("x\n", encoding="utf-8")
    target = home / ".agents" / "skills" / "x" / "SKILL.md"

    results = [
        stale_blocker(target, frozenset(), home),
        _replace_path(target, install_root=home, harness_name="t", allowed_root=home),
        remove_written(
            target,
            recorded=None,
            install_root=home,
            harness_name="t",
            allowed_root=home,
        ),
    ]

    for result in results:
        assert result is not None
        assert (result.outcome, result.message) == ("error", ESCAPE)
        assert result.detail["symlink"] == str(home / ".agents" / "skills")
    assert (outside / "x" / "SKILL.md").read_text(encoding="utf-8") == "x\n"


def test_a_link_above_the_allowed_folder_is_not_named(tmp_path: Path) -> None:
    # The allowed folder is reached through a link above it; the escape is
    # spelled with ``..``, so that link is not its cause.
    _link(tmp_path / "linked", tmp_path / "real")
    root = tmp_path / "linked" / "root"
    root.mkdir()

    error = pathsafety._validate_target_path(
        root / ".." / "x.md",
        allowed_root=pathsafety._normalized(root),
        operation="t",
    )

    assert error is not None
    assert "symlink" not in error.detail


def test_uninstall_names_a_user_level_link_that_leads_out_of_the_home(
    tmp_path: Path,
) -> None:
    home = Path.home()
    project = tmp_path / "proj"
    project.mkdir()
    profile = tmp_path / "prof" / "profile.yaml"
    made = CliRunner().invoke(main, ["profile", "init", "--profile", str(profile)])
    assert made.exit_code == 0, made.output
    installed = CliRunner().invoke(
        main,
        [
            "install",
            "--harness",
            "cursor",
            "--project",
            str(project),
            "--profile",
            str(profile),
            "--yes",
        ],
    )
    assert installed.exit_code == 0, installed.output
    skills = home / ".agents" / "skills"
    outside = tmp_path / "outside" / "skills"
    outside.parent.mkdir()
    shutil.move(str(skills), str(outside))
    _link(skills, outside)
    before = sorted(path for path in outside.rglob("*") if path.is_file())

    plain = CliRunner().invoke(
        main, ["uninstall", "--harness", "cursor", "--project", str(project), "--yes"]
    )
    as_json = CliRunner().invoke(
        main,
        [
            "uninstall",
            "--harness",
            "cursor",
            "--project",
            str(project),
            "--yes",
            "--json",
        ],
    )

    assert plain.exit_code != 0, plain.output
    problem = next(
        line for line in plain.output.splitlines() if "did not finish" in line
    )
    assert ESCAPE in problem
    assert f"{skills} is a link to {outside.resolve()}" in " ".join(
        plain.output.split()
    )
    assert "replace the link with a real folder" in " ".join(plain.output.split())
    payload = json.loads(as_json.output)
    summary = next(
        row
        for row in payload["results"]
        if row.get("operation") == "uninstall" and row.get("outcome") == "error"
    )
    assert summary["detail"] == {
        "symlink": str(skills),
        "leads_to": str(outside.resolve()),
    }
    steps = [row for row in payload["results"] if row.get("message") == ESCAPE]
    assert steps
    assert all(row["detail"]["symlink"] == str(skills) for row in steps)
    # The link still gets its own note that it was left in place.
    assert f"{skills} is a link (a symbolic link or a junction), so it was" in (
        " ".join(plain.output.split())
    )
    assert any(row.get("path") == str(skills) for row in payload["warnings"])
    # Nothing was written or removed through the link.
    assert sorted(path for path in outside.rglob("*") if path.is_file()) == before


def test_uninstall_names_a_link_that_keeps_installed_files(tmp_path: Path) -> None:
    # Apothem's own skill files reached through a link stay, and the summary
    # row names that link and where it leads, as it does for an escape.
    project = tmp_path / "proj"
    project.mkdir()
    profile = tmp_path / "prof" / "profile.yaml"
    made = CliRunner().invoke(main, ["profile", "init", "--profile", str(profile)])
    assert made.exit_code == 0, made.output
    installed = CliRunner().invoke(
        main,
        [
            "install",
            "--harness",
            "cursor",
            "--project",
            str(project),
            "--profile",
            str(profile),
            "--yes",
        ],
    )
    assert installed.exit_code == 0, installed.output
    skill = Path.home() / ".agents" / "skills" / "audit"
    outside = tmp_path / "outside" / "audit"
    outside.parent.mkdir()
    shutil.move(str(skill), str(outside))
    _link(skill, outside)

    as_json = CliRunner().invoke(
        main,
        [
            "uninstall",
            "--harness",
            "cursor",
            "--project",
            str(project),
            "--yes",
            "--json",
        ],
    )

    payload = json.loads(as_json.output)
    summary = next(
        row
        for row in payload["results"]
        if row.get("operation") == "uninstall" and row.get("outcome") == "error"
    )
    assert "reached through the link" in summary["message"]
    assert summary["detail"] == {
        "symlink": str(skill),
        "leads_to": str(outside.resolve()),
    }
