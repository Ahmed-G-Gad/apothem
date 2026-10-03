# SPDX-License-Identifier: MIT

"""Backups and the install ledger stay bounded across repeated installs.

Every install that changes a file, every uninstall and every rollback adds a
timestamped backup set under ``~/.apothem/backups/``, and every pass appends a
ledger record. A retention policy keeps the newest ``BACKUP_KEEP`` install
records per root and backup sets per harness, never dropping what the kept
records reference, so ``rollback`` of a kept install and ``uninstall`` still
work after the older history is gone.
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


def _snapshot(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): (
            "dir" if path.is_dir() else hashlib.sha256(path.read_bytes()).hexdigest()
        )
        for path in sorted(root.rglob("*"))
    }


def _cli(*args: str) -> dict[str, object]:
    result = CliRunner().invoke(main, [*args, "--json"])
    assert result.exit_code == 0, result.output
    payload: dict[str, object] = json.loads(result.output)
    return payload


def test_thirty_installs_keep_bounded_history_and_still_reverse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    # One distinct backup timestamp per install pass.
    counter = itertools.count()
    monkeypatch.setattr(
        install_driver,
        "_timestamp_slug",
        lambda: f"20260101T{next(counter):06d}Z",
    )
    project = tmp_path / "project"
    project.mkdir()
    before = _snapshot(project)
    rules = project / ".cursor" / "rules" / "apothem-rules.mdc"
    common = ["--harness", "cursor", "--project", str(project)]
    profile = ["--profile", str(profile_minimal_path())]

    end = "<!-- END APOTHEM MANAGED BLOCK -->"
    for index in range(30):
        _cli("install", *common, *profile)
        # Drift inside the managed block, so the next install rewrites the
        # anchor and backs it up.
        rules.write_text(
            rules.read_text(encoding="utf-8").replace(end, f"drift {index}\n{end}"),
            encoding="utf-8",
        )
    edited = rules.read_text(encoding="utf-8")
    _cli("install", *common, *profile)

    keep = install_driver.BACKUP_KEEP
    sets = list(install_driver.BACKUP_ROOT.glob("*/cursor"))
    assert len(sets) <= keep, len(sets)
    records = install_ledger.read_records("cursor")
    assert len(records) <= keep, len(records)

    # The latest install still rolls back to the operator's edited anchor ...
    _cli("rollback", *common, "--last", "--yes")
    assert rules.read_text(encoding="utf-8") == edited
    # ... and uninstall still removes everything the first install created.
    _cli("uninstall", *common, "--yes")
    assert _snapshot(project) == before
