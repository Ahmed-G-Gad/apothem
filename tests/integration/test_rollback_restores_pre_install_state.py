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
from pathlib import Path

import pytest
from click.testing import CliRunner

from apothem.cli import main
from apothem.harnesses._shared import install_driver
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
