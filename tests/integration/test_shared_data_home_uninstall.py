# SPDX-License-Identifier: MIT

"""Integration tests for the shared-data-home uninstall safety guard.

The data home is shared across every harness rooted at the same base, so a
naive uninstall that removed it on the first harness would destroy data the
other installed harnesses still depend on. ``_remove_data_home`` consults the
install ledger and removes the shared data stores only when this is the LAST
harness referencing the home; ``plans/`` is never auto-removed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from apothem.harnesses._shared import install_driver
from apothem.harnesses._shared.install_driver import (
    _materialize_data_surfaces,
    _remove_data_home,
)
from apothem.lib import install_ledger
from apothem.lib.data_home import resolve_shared_data_home
from apothem.lib.install_ledger import LedgerRecord
from apothem.lib.memory import MemoryRecord, MemoryStore


@pytest.fixture(autouse=True)
def _isolate_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Redirect the ledger + backup roots so the guard touches no real state."""
    monkeypatch.setattr(install_ledger, "STATE_ROOT", tmp_path / "ledger-state")
    monkeypatch.setattr(install_driver, "BACKUP_ROOT", tmp_path / "backups")


def _record(record_id: str) -> MemoryRecord:
    return MemoryRecord(
        id=record_id,
        title="shared record",
        body="A record written into the shared data home.",
        kind="preference",
        created="2026-06-24T00:00:00Z",
    )


def _install_marker(harness: str, root: Path) -> None:
    """Append an `install` ledger record for *harness* at *root*."""
    install_ledger.append_record(
        LedgerRecord.create(harness=harness, root=root, kind="install")
    )


def _uninstall_marker(harness: str, root: Path) -> None:
    """Append an `uninstall` ledger record for *harness* at *root*."""
    install_ledger.append_record(
        LedgerRecord.create(harness=harness, root=root, kind="uninstall")
    )


def test_retains_shared_home_while_another_harness_installed(tmp_path: Path) -> None:
    # Arrange: two harnesses share the same project root; both are installed.
    root = tmp_path / "project"
    root.mkdir()
    _materialize_data_surfaces("zed", root)
    store = MemoryStore(resolve_shared_data_home(base=root))
    store.add(_record("rec-shared"))
    _install_marker("zed", root)
    _install_marker("trae", root)

    # Act: uninstall the first harness (trae still installed at the same root).
    result = _remove_data_home("zed", root=root, allowed_root=root)

    # Assert: the shared data stores are RETAINED — trae still needs them.
    home = resolve_shared_data_home(base=root)
    assert home.memory.is_dir()
    assert store.contains("rec-shared")
    assert result is not None
    assert result.outcome == "unchanged"
    assert "retained" in result.message


def test_removes_shared_stores_on_last_harness(tmp_path: Path) -> None:
    # Arrange: a single harness installed at the root, with an operator record.
    root = tmp_path / "project"
    root.mkdir()
    _materialize_data_surfaces("zed", root)
    MemoryStore(resolve_shared_data_home(base=root)).add(_record("rec-last"))
    _install_marker("zed", root)

    # Act: uninstall the only harness.
    result = _remove_data_home("zed", root=root, allowed_root=root)

    # Assert: the shared data stores are removed (last harness); a backup exists.
    home = resolve_shared_data_home(base=root)
    assert not home.memory.exists()
    assert not home.contexts.exists()
    assert not home.learning.exists()
    assert result is not None
    assert result.outcome == "updated"
    assert result.backup_path is not None


def test_removes_shared_stores_when_others_already_uninstalled(
    tmp_path: Path,
) -> None:
    # Arrange: trae was installed then uninstalled; zed remains and is last.
    root = tmp_path / "project"
    root.mkdir()
    _materialize_data_surfaces("zed", root)
    _install_marker("trae", root)
    _uninstall_marker("trae", root)
    _install_marker("zed", root)

    # Act: uninstall zed.
    result = _remove_data_home("zed", root=root, allowed_root=root)

    # Assert: removed — trae's latest record at this root is an uninstall.
    home = resolve_shared_data_home(base=root)
    assert not home.memory.exists()
    assert result is not None
    assert result.outcome == "updated"


def test_plans_dir_is_never_auto_removed(tmp_path: Path) -> None:
    # Arrange: a last-harness uninstall with an operator plans/ suite present.
    root = tmp_path / "project"
    root.mkdir()
    home = resolve_shared_data_home(base=root).ensure()
    plan_suite = home.plans / "my-suite"
    plan_suite.mkdir(parents=True)
    (plan_suite / "PROGRESS.md").write_text(
        "operator planning state\n", encoding="utf-8"
    )
    MemoryStore(home).ensure_initialized()
    _install_marker("zed", root)

    # Act: uninstall the last harness.
    _remove_data_home("zed", root=root, allowed_root=root)

    # Assert: data stores gone, but plans/ — operator state — survives intact.
    assert not home.memory.exists()
    assert (plan_suite / "PROGRESS.md").read_text(encoding="utf-8") == (
        "operator planning state\n"
    )


def test_returns_none_when_no_data_stores_exist(tmp_path: Path) -> None:
    # Arrange: no data home materialized at the root.
    root = tmp_path / "project"
    root.mkdir()
    _install_marker("zed", root)

    # Act / Assert: nothing to remove → None.
    assert _remove_data_home("zed", root=root, allowed_root=root) is None


def test_distinct_roots_do_not_count_as_co_occupants(tmp_path: Path) -> None:
    # Arrange: another harness installed at a DIFFERENT root must not retain
    # this root's shared home.
    root = tmp_path / "project-a"
    other_root = tmp_path / "project-b"
    root.mkdir()
    other_root.mkdir()
    _materialize_data_surfaces("zed", root)
    _install_marker("zed", root)
    _install_marker("trae", other_root)  # different shared home

    # Act: uninstall zed at root — trae's home is elsewhere.
    result = _remove_data_home("zed", root=root, allowed_root=root)

    # Assert: removed — the other harness's home does not overlap this root's.
    assert not resolve_shared_data_home(base=root).memory.exists()
    assert result is not None
    assert result.outcome == "updated"
