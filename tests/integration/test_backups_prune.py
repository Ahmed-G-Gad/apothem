# SPDX-License-Identifier: MIT

"""``apothem backups prune`` bounds history without breaking rollback.

The command runs the install retention on demand: it keeps the newest N backup
sets per harness and the newest N install records per install root. The one
thing it must never do is remove a backup set the latest install record of an
install root references, because ``apothem rollback`` of the latest install
restores from exactly that set.
"""

from __future__ import annotations

import hashlib
import itertools
import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from apothem.cli import main
from apothem.harnesses._shared import install_driver
from apothem.lib import install_ledger
from apothem.schemas import profile_minimal_path

_END = "<!-- END APOTHEM MANAGED BLOCK -->"


def _cli(*args: str, exit_code: int = 0) -> dict[str, object]:
    result = CliRunner().invoke(main, [*args, "--json"])
    assert result.exit_code == exit_code, result.output
    payload: dict[str, object] = json.loads(result.output)
    return payload


def _rules(project: Path) -> Path:
    return project / ".cursor" / "rules" / "apothem-rules.mdc"


def _install(project: Path) -> None:
    _cli(
        "install",
        "--harness",
        "cursor",
        "--project",
        str(project),
        "--profile",
        str(profile_minimal_path()),
    )


def _drift(project: Path, marker: str) -> None:
    """Edit inside the managed block so the next install backs the file up."""
    rules = _rules(project)
    rules.write_text(
        rules.read_text(encoding="utf-8").replace(_END, f"{marker}\n{_END}"),
        encoding="utf-8",
    )


def _cursor_sets() -> list[str]:
    return sorted(
        path.parent.name for path in install_driver.BACKUP_ROOT.glob("*/cursor")
    )


def _tree_digest(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


@pytest.fixture
def two_projects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, Path, str]:
    """Cursor installed into two projects, the second one more recently.

    Project A's latest install backs up an operator-edited rules file; project
    B then installs three more times, so project A's latest backup set is
    older than the newest sets and a ``--keep 1`` prune reaches past it.
    Returns both projects and project A's edited rules text, which rollback of
    A's latest install must restore.
    """
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    counter = itertools.count()
    monkeypatch.setattr(
        install_driver,
        "_timestamp_slug",
        lambda: f"20260101T{next(counter):06d}Z",
    )
    project_a = tmp_path / "project-a"
    project_b = tmp_path / "project-b"
    project_a.mkdir()
    project_b.mkdir()

    _install(project_a)
    _drift(project_a, "drift a1")
    _install(project_a)
    _drift(project_a, "drift a2")
    edited = _rules(project_a).read_text(encoding="utf-8")
    _install(project_a)

    _install(project_b)
    for index in range(3):
        _drift(project_b, f"drift b{index}")
        _install(project_b)
    return project_a, project_b, edited


def _latest_install_sets(project: Path) -> set[str]:
    record = install_ledger.latest_record("cursor", root=project)
    assert record is not None
    root = install_driver.BACKUP_ROOT.resolve()
    return {
        Path(target.backup_ref).resolve().relative_to(root).parts[0]
        for target in record.targets
        if target.backup_ref
    }


def test_prune_never_removes_the_latest_install_backup_so_rollback_restores(
    two_projects: tuple[Path, Path, str],
) -> None:
    project_a, project_b, edited = two_projects
    latest_a = _latest_install_sets(project_a)
    latest_b = _latest_install_sets(project_b)
    before = _cursor_sets()
    # The scenario is meaningful only if A's latest set is not among the
    # newest one, so a plain newest-N cut would have removed it.
    assert latest_a
    assert not latest_a & set(before[-1:])

    payload = _cli("backups", "prune", "--harness", "cursor", "--keep", "1")

    assert payload["status"] == "success"
    assert payload["command"] == "backups prune"
    after = _cursor_sets()
    assert latest_a <= set(after)
    assert latest_b <= set(after)
    assert len(after) < len(before)
    removed = {
        Path(str(row["path"])).parent.name
        for row in payload["results"]  # type: ignore[union-attr]
        if row["outcome"] == "updated" and "backup set" in str(row["message"])
    }
    assert removed == set(before) - set(after)
    assert not removed & latest_a

    # Rollback of project A's latest install still restores the edited file.
    _cli(
        "rollback",
        "--harness",
        "cursor",
        "--project",
        str(project_a),
        "--last",
        "--yes",
    )
    assert _rules(project_a).read_text(encoding="utf-8") == edited


def test_dry_run_reports_without_changing_anything(
    two_projects: tuple[Path, Path, str], tmp_path: Path
) -> None:
    backups_before = _tree_digest(install_driver.BACKUP_ROOT)
    ledger = install_ledger.ledger_path("cursor")
    ledger_before = ledger.read_bytes()

    payload = _cli(
        "backups", "prune", "--harness", "cursor", "--keep", "1", "--dry-run"
    )

    assert payload["status"] == "dry_run"
    assert payload["action"] == "dry_run"
    messages = [str(row["message"]) for row in payload["results"]]  # type: ignore[union-attr]
    assert any(message.startswith("would remove backup set") for message in messages)
    assert _tree_digest(install_driver.BACKUP_ROOT) == backups_before
    assert ledger.read_bytes() == ledger_before


def test_prune_of_a_harness_without_history_reports_nothing_to_prune(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    payload = _cli("backups", "prune", "--harness", "claude-code")
    assert payload["status"] == "success"
    assert [row["outcome"] for row in payload["results"]] == ["unchanged"]  # type: ignore[union-attr]


def test_keep_below_one_is_a_usage_error() -> None:
    payload = _cli("backups", "prune", "--keep", "0", exit_code=64)
    error = payload["error"]
    assert isinstance(error, dict)
    assert error["code"] == "cli.usage"
    assert error["field"] == "keep"


def test_unknown_harness_is_an_expected_error() -> None:
    payload = _cli("backups", "prune", "--harness", "no-such-harness", exit_code=1)
    error = payload["error"]
    assert isinstance(error, dict)
    assert error["code"] == "harness.unknown"


def test_unreadable_ledger_is_reported_and_left_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    ledger = install_ledger.ledger_path("cursor")
    ledger.parent.mkdir(parents=True)
    ledger.write_text("not json\n{}\n", encoding="utf-8")

    payload = _cli("backups", "prune", "--harness", "cursor", exit_code=1)

    assert payload["status"] == "error"
    rows = payload["results"]
    assert isinstance(rows, list)
    assert [row["outcome"] for row in rows] == ["error"]
    assert ledger.read_text(encoding="utf-8") == "not json\n{}\n"
