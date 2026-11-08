# SPDX-License-Identifier: MIT

"""``apothem rollback`` returns a harness to its exact pre-install state.

Rollback used to restore only the files an install had overwritten: every file
and directory the install created stayed behind, a directory the install
replaced kept the install's extra files, and two backups taken in the same
second could be restored to the wrong path. Rollback now reverses the recorded
install target by target — restoring backups to the recorded paths, removing
what the install created, and removing the directories it created once empty.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from click.testing import CliRunner

from apothem.cli import main
from apothem.harnesses._shared import install_driver
from apothem.harnesses._shared.install_driver_pathsafety import _is_link
from apothem.lib import install_ledger
from apothem.lib.harness_registry import get_harness_entry, load_adapter_class

_PROFILE = {"identity": {"name": "Rollback Probe"}}


def _snapshot(root: Path) -> dict[str, str]:
    """Map every path under *root* to a content hash (``dir`` for directories)."""
    state: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        rel = str(path.relative_to(root))
        if path.is_dir():
            state[rel] = "dir"
        else:
            state[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return state


def _rollback(harness_id: str, *extra: str) -> dict[str, object]:
    result = CliRunner().invoke(
        main, ["rollback", "--harness", harness_id, *extra, "--yes", "--json"]
    )
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.delenv("CODEX_HOME", raising=False)
    return home


@pytest.mark.parametrize("harness_id", ["claude-code", "hermes", "codex"])
def test_rollback_of_a_first_install_restores_the_empty_home(
    harness_id: str, home: Path
) -> None:
    before = _snapshot(home)
    adapter = load_adapter_class(get_harness_entry(harness_id))()
    adapter.install(_PROFILE)
    assert _snapshot(home) != before

    _rollback(harness_id, "--last")

    assert _snapshot(home) == before


def test_rollback_restores_a_replaced_directory_exactly(home: Path) -> None:
    # The operator has their own skills/<name>/ where Apothem ships one: the
    # install replaces it, and rollback must bring back exactly the operator's
    # directory, not the operator's files plus Apothem's.
    skills = home / ".claude" / "skills"
    operator_skill = skills / "dev-toolkit"
    operator_skill.mkdir(parents=True)
    (operator_skill / "NOTES.md").write_text("operator notes\n", encoding="utf-8")
    before = _snapshot(home)
    adapter = load_adapter_class(get_harness_entry("claude-code"))()
    adapter.install(_PROFILE)
    assert (operator_skill / "SKILL.md").is_file()

    _rollback("claude-code", "--last")

    assert _snapshot(home) == before


def test_rollback_of_the_plugin_move_restores_the_old_plugin_folder(
    home: Path,
) -> None:
    # Apothem releases before the move wrote the Antigravity plugin to
    # ~/.gemini/antigravity-cli/plugins/apothem/ and nothing under
    # ~/.gemini/config/. The update that moves it to
    # ~/.gemini/config/plugins/apothem/ backs the old folder up and removes it
    # whole; rolling that update back must bring the old folder back exactly
    # and remove the new one with the folders the update created for it.
    gemini = home / ".gemini"
    old = gemini / "antigravity-cli" / "plugins" / "apothem"
    new = gemini / "config" / "plugins" / "apothem"
    adapter = load_adapter_class(get_harness_entry("antigravity"))()
    adapter.install(_PROFILE)
    old.parent.mkdir(parents=True)
    shutil.move(str(new), str(old))
    (gemini / "config" / "plugins").rmdir()
    (gemini / "config").rmdir()
    before = _snapshot(home)
    adapter.update(_PROFILE)
    assert not old.exists()
    assert (new / "plugin.json").is_file()

    _rollback("antigravity", "--last")

    assert _snapshot(home) == before
    assert (old / "plugin.json").is_file()
    assert not (gemini / "config").exists()


def test_rollback_of_a_record_that_swept_the_app_folder_leaves_it_in_place(
    home: Path, tmp_path: Path
) -> None:
    # Releases before this fix listed ~/.gemini/antigravity/ as a stale path,
    # so their install records name it as a swept target with a backup. That
    # folder is the Antigravity App's data, which the App has kept writing
    # since. Rolling such a record back must not restore the old copy over it.
    gemini = home / ".gemini"
    adapter = load_adapter_class(get_harness_entry("antigravity"))()
    adapter.install(_PROFILE)
    record = install_ledger.latest_record("antigravity")
    assert record is not None
    app = gemini / "antigravity"
    stale_copy = tmp_path / "old-backup" / "antigravity"
    stale_copy.mkdir(parents=True)
    (stale_copy / "mcp_oauth_tokens.json").write_bytes(b'{"server": "old"}\n')
    pre_fix = replace(
        record,
        targets=(
            install_ledger.LedgerTarget(
                path=str(app),
                mode="sweep_stale",
                ownership_class="apothem-owned",
                backup_ref=str(stale_copy),
                outcome="updated",
            ),
            *record.targets,
        ),
    )
    install_ledger.append_record(
        replace(pre_fix, install_id=install_ledger.generate_ulid())
    )
    app.mkdir(parents=True)
    (app / "mcp_oauth_tokens.json").write_bytes(b'{"server": "new"}\n')

    report = _rollback("antigravity", "--last")

    assert (app / "mcp_oauth_tokens.json").read_bytes() == b'{"server": "new"}\n'
    [kept] = [
        row
        for row in report["results"]  # type: ignore[union-attr]
        if Path(str(row["path"])) == app
    ]
    # Only files missing now would come back; this one is there, so it stays.
    assert kept["outcome"] == "unchanged"
    assert str(stale_copy) in str(kept["message"])


@pytest.mark.skipif(sys.platform != "win32", reason="Windows junctions")
def test_a_junction_at_the_old_plugin_path_is_left_alone_and_rolls_back(
    home: Path,
) -> None:
    # The old plugin path is a junction to a folder of the operator's that is
    # not the new plugin folder. The update must neither back it up nor report
    # it removed, and rolling the update back must succeed and leave it as is.
    import _winapi

    gemini = home / ".gemini"
    adapter = load_adapter_class(get_harness_entry("antigravity"))()
    adapter.install(_PROFILE)
    elsewhere = home / "my-plugins" / "apothem"
    elsewhere.mkdir(parents=True)
    (elsewhere / "notes.md").write_bytes(b"mine\n")
    link = gemini / "antigravity-cli" / "plugins" / "apothem"
    link.parent.mkdir(parents=True)
    _winapi.CreateJunction(str(elsewhere), str(link))
    assert _is_link(link)
    assert not _is_link(elsewhere)

    preview = adapter.preview(_PROFILE)
    [planned] = [
        r
        for r in preview.results
        if r.operation == "sweep_stale" and Path(r.path) == link
    ]
    assert planned.outcome == "unchanged"

    adapter.update(_PROFILE)

    record = install_ledger.latest_record("antigravity")
    assert record is not None
    assert not [t for t in record.targets if Path(t.path) == link]
    assert _is_link(link)
    assert (elsewhere / "notes.md").read_bytes() == b"mine\n"

    _rollback("antigravity", "--last")

    assert _is_link(link)
    assert (link / "notes.md").read_bytes() == b"mine\n"


def test_same_second_backups_restore_to_their_own_paths(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Pin the backup timestamp so the second install's backup collides with
    # the first one's name; rollback must still restore by recorded path.
    monkeypatch.setattr(install_driver, "_timestamp_slug", lambda: "20260101T000000Z")
    settings = home / ".qwen" / "settings.json"
    settings.parent.mkdir(parents=True)
    seed = '{"model": {"name": "operator-model"}}\n'
    settings.write_text(seed, encoding="utf-8")
    adapter = load_adapter_class(get_harness_entry("qwen-code"))()
    adapter.install(_PROFILE)
    adapter.uninstall()
    settings.write_text(seed, encoding="utf-8")
    adapter.install(_PROFILE)
    record = install_ledger.current_install_record("qwen_code", root=settings.parent)
    assert record is not None

    _rollback("qwen-code", "--install-id", record.install_id)

    assert settings.read_text(encoding="utf-8") == seed
    assert not (settings.parent / "settings.json.1").exists()


def test_rollback_record_references_the_backups_rollback_took(home: Path) -> None:
    # Rollback backs up what it replaces before restoring the operator's
    # directory; its ledger record references those backups so retention
    # keeps them while the record is kept.
    operator_skill = home / ".claude" / "skills" / "dev-toolkit"
    operator_skill.mkdir(parents=True)
    (operator_skill / "NOTES.md").write_text("operator notes\n", encoding="utf-8")
    adapter = load_adapter_class(get_harness_entry("claude-code"))()
    adapter.install(_PROFILE)

    _rollback("claude-code", "--last")

    marker = install_ledger.latest_record("claude_code", kind=None)
    assert marker is not None
    assert marker.kind == "rollback"
    refs = [Path(target.backup_ref) for target in marker.targets if target.backup_ref]
    assert refs
    backup_root = install_driver.BACKUP_ROOT.resolve()
    assert all(ref.resolve().is_relative_to(backup_root) for ref in refs)
    assert all(ref.exists() for ref in refs)
