# SPDX-License-Identifier: MIT

"""Install then uninstall reverses the data stores where the install wrote them.

The memory, contexts, and learning stores, and the operator ``plans/`` tree,
live under the shared working directory the profile's ``workspace`` block
resolves to. Install records that resolved home on its ledger record, and
uninstall and rollback reverse the stores at the recorded home. These tests
install and uninstall through real adapters with a temporary user home, under a
user-home scope and under a custom ``directory_name``, and check that the
stores are backed up and removed while ``plans/`` survives. A default-profile
case pins the unchanged behavior.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from apothem.harnesses import HarnessAdapter
from apothem.harnesses._shared import install_driver
from apothem.harnesses._shared.install_driver_lifecycle import _data_home_for
from apothem.harnesses.antigravity import AntigravityAdapter
from apothem.harnesses.codex import CodexAdapter
from apothem.harnesses.cursor import CursorAdapter
from apothem.lib.data_home import DataHome
from apothem.lib.install_ledger import LedgerRecord
from apothem.lib.memory import MemoryRecord, MemoryStore

#: Profile fragments naming the workspace. ``DEFAULT`` omits the block entirely.
USER_HOME_CUSTOM: dict[str, Any] = {
    "workspace": {"scope": "user-home", "directory_name": ".work"}
}
PROJECT_CUSTOM: dict[str, Any] = {"workspace": {"directory_name": ".work"}}
DEFAULT: dict[str, Any] = {}


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the user home at a temporary directory and redirect the backups."""
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setenv("USERPROFILE", str(fake_home))
    monkeypatch.setattr(install_driver, "BACKUP_ROOT", tmp_path / "backups")
    return fake_home


def _record(record_id: str) -> MemoryRecord:
    return MemoryRecord(
        id=record_id,
        title="operator record",
        body="A record the operator wrote into the shared working directory.",
        kind="preference",
        created="2026-10-15T00:00:00Z",
    )


def _user_scope_adapter(
    adapter_cls: type[HarnessAdapter], root: Path, monkeypatch: pytest.MonkeyPatch
) -> HarnessAdapter:
    """Return a user-scope adapter whose harness root is *root*."""
    adapter = adapter_cls()
    target = root / adapter.output_path.name
    monkeypatch.setattr(type(adapter), "output_path", property(lambda self: target))
    return adapter


def _backed_up(record_id: str) -> bool:
    """Return True when a backed-up memory store under the backup root holds *record_id*."""
    return any(
        record_id in path.read_text(encoding="utf-8")
        for path in install_driver.BACKUP_ROOT.rglob("records.json")
    )


@pytest.mark.parametrize(
    ("adapter_cls", "scope", "profile", "expect"),
    [
        pytest.param(
            CodexAdapter,
            "user",
            USER_HOME_CUSTOM,
            "user-home",
            id="codex-user-home-custom-name",
        ),
        pytest.param(
            CursorAdapter,
            "project",
            PROJECT_CUSTOM,
            "custom",
            id="cursor-project-local-custom-name",
        ),
        pytest.param(
            CursorAdapter,
            "project",
            USER_HOME_CUSTOM,
            "user-home",
            id="cursor-user-home-custom-name",
        ),
        pytest.param(
            CodexAdapter,
            "user",
            DEFAULT,
            "default",
            id="codex-default-control",
        ),
        pytest.param(
            CursorAdapter,
            "project",
            DEFAULT,
            "default",
            id="cursor-default-control",
        ),
    ],
)
def test_uninstall_reverses_stores_where_install_wrote_them(
    adapter_cls: type[HarnessAdapter],
    scope: str,
    profile: dict[str, Any],
    expect: str,
    tmp_path: Path,
    home: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange: install through the adapter, then seed operator state in the
    # shared home and a plan suite under its plans/ tree.
    install_root = tmp_path / ("project" if scope == "project" else "root")
    install_root.mkdir(parents=True, exist_ok=True)
    if scope == "project":
        adapter = adapter_cls()
        adapter.install(profile, project=install_root)
        uninstall_kwargs: dict[str, Any] = {"project": install_root}
    else:
        adapter = _user_scope_adapter(adapter_cls, install_root, monkeypatch)
        adapter.install(profile)
        uninstall_kwargs = {}
    expected_home = {
        "user-home": home / ".work",
        "custom": install_root / ".work",
        "default": install_root / ".apothem",
    }[expect]
    stores = DataHome.from_root(expected_home)
    assert stores.memory.is_dir(), "install did not write the stores at the home"
    MemoryStore(stores).add(_record("rec-operator"))
    plan = stores.plans / "my-suite" / "PROGRESS.md"
    plan.parent.mkdir(parents=True)
    plan.write_text("operator planning state\n", encoding="utf-8")

    # Act: uninstall the only harness at this root.
    adapter.uninstall(**uninstall_kwargs)

    # Assert: the stores are removed from the home they were written to, the
    # operator record is backed up before removal, and plans/ survives intact.
    assert not stores.memory.exists()
    assert not stores.contexts.exists()
    assert not stores.learning.exists()
    assert _backed_up("rec-operator")
    assert plan.read_text(encoding="utf-8") == "operator planning state\n"


def test_user_home_stores_are_removed_only_by_the_last_harness(
    tmp_path: Path, home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange: two user-scope harnesses at different roots share one user-home
    # working directory. Each install records that same home.
    codex = _user_scope_adapter(CodexAdapter, tmp_path / "codex-root", monkeypatch)
    antigravity = _user_scope_adapter(
        AntigravityAdapter, tmp_path / "antigravity-root", monkeypatch
    )
    codex.install(USER_HOME_CUSTOM)
    antigravity.install(USER_HOME_CUSTOM)
    stores = DataHome.from_root(home / ".work")
    MemoryStore(stores).add(_record("rec-shared"))

    # Act / Assert: uninstalling the first harness retains the shared stores,
    # because the other harness is still installed at its own root.
    codex.uninstall()
    assert stores.memory.is_dir()
    assert MemoryStore(stores).contains("rec-shared")

    # Act / Assert: uninstalling the last harness removes them.
    antigravity.uninstall()
    assert not stores.memory.exists()


def _record_with_home(data_home: Path, root: Path) -> LedgerRecord:
    return LedgerRecord.create(
        harness="codex", root=root, kind="install", data_home=str(data_home)
    )


def test_recorded_home_is_trusted_only_under_root_or_user_home(
    tmp_path: Path, home: Path
) -> None:
    root = tmp_path / "root"

    # A home one level under the user home or the install root is replayed.
    assert _data_home_for(_record_with_home(home / ".work", root), root=root) == (
        home / ".work"
    )
    assert _data_home_for(_record_with_home(root / "custom", root), root=root) == (
        root / "custom"
    )
    # Anything else is not trusted: the default home is used instead, so a
    # tampered ledger cannot point the removal at an arbitrary directory.
    for untrusted in (
        tmp_path / "elsewhere" / ".work",
        home / "nested" / ".work",
    ):
        assert _data_home_for(_record_with_home(untrusted, root), root=root) == (
            root / ".apothem"
        )
    # No record, or a record without a home, resolves to the default.
    assert _data_home_for(None, root=root) == root / ".apothem"


def test_data_home_round_trips_through_the_ledger_line(tmp_path: Path) -> None:
    record = LedgerRecord.create(
        harness="codex", root=tmp_path, kind="install", data_home="/x/.work"
    )
    restored = LedgerRecord.from_dict(json.loads(record.to_json_line()))
    assert restored.data_home == "/x/.work"

    legacy = json.loads(
        LedgerRecord.create(
            harness="codex", root=tmp_path, kind="install"
        ).to_json_line()
    )
    assert "data_home" not in legacy
    assert LedgerRecord.from_dict(legacy).data_home is None
