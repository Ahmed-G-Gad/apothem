# SPDX-License-Identifier: MIT

"""Unit tests for the antigravity harness adapter.

Protocol-conformance and install-smoke tests for the adapter, and the move of
the Apothem plugin to ``~/.gemini/config/plugins/apothem/``, the folder
Antigravity CLI 1.0.2 and later load plugins from. Earlier Apothem releases
wrote the plugin to ``~/.gemini/antigravity-cli/plugins/apothem/``; an install
made there is migrated by ``update`` and cleaned by ``uninstall``. The rollback
of that update is covered by
``tests/integration/test_rollback_restores_pre_install_state.py``.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest
import yaml

from apothem.harnesses import HarnessAdapter
from apothem.harnesses import antigravity as antigravity_pkg
from apothem.harnesses._shared import install_driver
from apothem.harnesses.antigravity import AntigravityAdapter
from apothem.lib import install_ledger

#: The plugin folder Antigravity CLI loads, and the one earlier releases wrote,
#: both relative to the harness root ``~/.gemini/``.
_PLUGIN = Path("config") / "plugins" / "apothem"
_OLD_PLUGIN = Path("antigravity-cli") / "plugins" / "apothem"


@pytest.fixture
def adapter() -> AntigravityAdapter:
    return AntigravityAdapter()


@pytest.fixture
def gemini(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the user home and the backup root into *tmp_path*; return ``~/.gemini``."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setattr(install_driver, "BACKUP_ROOT", tmp_path / "apothem-backups")
    return home / ".gemini"


def _revert_to_the_old_plugin_folder(gemini: Path) -> Path:
    """Rebuild the layout an install made before the plugin moved.

    Earlier Apothem releases wrote the plugin to
    ``~/.gemini/antigravity-cli/plugins/apothem/``, kept ``~/.gemini/GEMINI.md``
    where it is now, and wrote nothing under ``~/.gemini/config/``. Moving the
    plugin folder back and removing the two folders the move leaves empty
    reproduces that disk state.
    """
    old = gemini / _OLD_PLUGIN
    old.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(gemini / _PLUGIN), str(old))
    (gemini / "config" / "plugins").rmdir()
    (gemini / "config").rmdir()
    return old


def _add_cli_app_data(gemini: Path) -> dict[Path, bytes]:
    """Write files that Antigravity and another plugin keep beside the old folder.

    ``~/.gemini/antigravity-cli/`` is the CLI's own app-data folder, and a plugin
    another tool installed there is not Apothem's to remove. ``~/.gemini/antigravity/``
    is the App's app-data folder, where Antigravity also keeps its MCP OAuth
    tokens and session transcripts.
    """
    files = {
        gemini / "antigravity-cli" / "settings.json": b'{"theme": "dark"}\n',
        gemini / "antigravity-cli" / "plugins" / "other" / "plugin.json": (
            b'{"name": "other"}\n'
        ),
        gemini / "antigravity" / "mcp_oauth_tokens.json": b'{"server": "token"}\n',
        gemini / "antigravity" / "brain" / "session" / "transcript.jsonl": b"{}\n",
    }
    for path, data in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return files


def _old_plugin_backups() -> list[Path]:
    """Return each backup of the old plugin folder under the Apothem backup root."""
    if not install_driver.BACKUP_ROOT.is_dir():
        return []
    return sorted(
        manifest.parent
        for manifest in install_driver.BACKUP_ROOT.rglob("plugin.json")
        if manifest.parent.as_posix().endswith(_OLD_PLUGIN.as_posix())
    )


def _snapshot(root: Path) -> dict[str, bytes | None]:
    """Map every path under *root* to its bytes (``None`` for a folder)."""
    return {
        path.relative_to(root).as_posix(): None if path.is_dir() else path.read_bytes()
        for path in sorted(root.rglob("*"))
    }


def test_capabilities_declare_native_mcp_surface() -> None:
    """MCP is native via the ``mcpServers`` object in ``mcp_config.json``.

    The capabilities file must name the native MCP surface rather than an
    empty list — Antigravity supports MCP through the operator-owned
    ``mcp_config.json`` ``mcpServers`` object.
    """
    caps_path = Path(antigravity_pkg.__file__).parent / "capabilities.yml"
    caps = yaml.safe_load(caps_path.read_text(encoding="utf-8"))

    assert caps["mcp_servers"], "antigravity MCP surface must not be the empty list"
    assert any("mcp_config.json" in entry for entry in caps["mcp_servers"])


def test_capabilities_commands_route_through_skills() -> None:
    """Command-like prompts migrate to skills on Antigravity CLI.

    The migration convention routes commands through skills, so the
    capability value must reflect the skill-based command surface.
    """
    caps_path = Path(antigravity_pkg.__file__).parent / "capabilities.yml"
    caps = yaml.safe_load(caps_path.read_text(encoding="utf-8"))

    assert caps["custom_command_support"] == "skills"


def test_protocol_conformance(adapter: AntigravityAdapter) -> None:
    assert isinstance(adapter, HarnessAdapter)


def test_name(adapter: AntigravityAdapter) -> None:
    assert adapter.name == "antigravity"


def test_output_path_is_path(adapter: AntigravityAdapter) -> None:
    assert isinstance(adapter.output_path, Path)


def test_is_installed_returns_bool(adapter: AntigravityAdapter) -> None:
    result = adapter.is_installed()
    assert isinstance(result, bool)


def test_install_accepts_empty_profile(
    adapter: AntigravityAdapter,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "GEMINI.md"
    monkeypatch.setattr(type(adapter), "output_path", property(lambda self: target))
    adapter.install({})

    plugin_path = tmp_path / _PLUGIN / "plugin.json"
    plugin = json.loads(plugin_path.read_text(encoding="utf-8"))
    assert plugin["name"] == "apothem"
    assert (tmp_path / _PLUGIN / "skills").is_dir()
    assert (tmp_path / _PLUGIN / "rules").is_dir()
    assert not (tmp_path / "antigravity-cli").exists()
    assert adapter.verify()


def test_uninstall_noop_when_not_installed(
    adapter: AntigravityAdapter, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing = tmp_path / "nonexistent_config"
    monkeypatch.setattr(type(adapter), "output_path", property(lambda self: missing))
    adapter.uninstall()  # must not raise when output_path does not exist


def test_uninstall_strips_block_and_keeps_operator_prose(
    adapter: AntigravityAdapter, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Surgical uninstall: install the GEMINI.md managed block over operator
    # prose, uninstall, and assert the operator prose survives, the Apothem block
    # is removed, and no whole-file .bak sibling is left beside the operator file.
    monkeypatch.setattr(install_driver, "BACKUP_ROOT", tmp_path / "apothem-backups")
    # The manifest target is ${HARNESS_ROOT}/GEMINI.md and the harness root is
    # output_path.parent, so name the output file GEMINI.md so they coincide.
    target = tmp_path / "GEMINI.md"
    operator_prose = "# Operator notes\n\nKeep my own guidance.\n"
    target.write_text(operator_prose, encoding="utf-8")
    monkeypatch.setattr(type(adapter), "output_path", property(lambda self: target))

    adapter.install({})
    assert "APOTHEM MANAGED BLOCK" in target.read_text(encoding="utf-8")

    adapter.uninstall()

    remainder = target.read_text(encoding="utf-8")
    assert "Keep my own guidance." in remainder
    assert "APOTHEM MANAGED BLOCK" not in remainder
    assert not list(tmp_path.glob("GEMINI.md.*.bak"))


# ---------------------------------------------------------------------------
# the plugin's move from ~/.gemini/antigravity-cli/plugins/ to
# ~/.gemini/config/plugins/
# ---------------------------------------------------------------------------


def test_update_moves_the_plugin_out_of_the_old_folder_after_a_backup(
    adapter: AntigravityAdapter, gemini: Path
) -> None:
    adapter.install({})
    old = _revert_to_the_old_plugin_folder(gemini)
    # The old folder holds what an earlier Apothem release wrote there, plus a
    # skill no release ships, to show that the whole folder is removed.
    skill = next((old / "skills").glob("*/SKILL.md"))
    rule = next((old / "rules").glob("*.md"))
    legacy_only = old / "skills" / "legacy-only-skill" / "SKILL.md"
    legacy_only.parent.mkdir()
    legacy_only.write_text("---\nname: legacy-only-skill\n---\n", encoding="utf-8")
    saved_before = {
        path.relative_to(old): path.read_bytes()
        for path in (old / "plugin.json", skill, rule, legacy_only)
    }
    app_data = _add_cli_app_data(gemini)

    adapter.update({})

    assert not old.exists()
    plugin = gemini / _PLUGIN
    manifest = json.loads((plugin / "plugin.json").read_text(encoding="utf-8"))
    assert manifest["name"] == "apothem"
    assert (plugin / skill.relative_to(old)).is_file()
    assert (plugin / rule.relative_to(old)).is_file()
    assert not (plugin / legacy_only.relative_to(old)).exists()
    # No copy of a skill is left outside the new plugin folder.
    assert all(plugin in path.parents for path in gemini.rglob("SKILL.md"))
    # The old folder was backed up whole before it was removed.
    [backup] = _old_plugin_backups()
    for relative, data in saved_before.items():
        assert (backup / relative).read_bytes() == data, relative
    # The CLI's own app data and the other plugin are left as they were.
    for path, data in app_data.items():
        assert path.read_bytes() == data, path


def test_uninstall_over_the_old_plugin_folder_removes_it_after_a_backup(
    adapter: AntigravityAdapter, gemini: Path
) -> None:
    # An install from before the move, uninstalled without an update in between:
    # no install entry targets the old plugin folder any longer.
    anchor = gemini / "GEMINI.md"
    anchor.parent.mkdir(parents=True)
    anchor.write_text("# Operator notes\n\nKeep my own guidance.\n", encoding="utf-8")
    adapter.install({})
    old = _revert_to_the_old_plugin_folder(gemini)
    app_data = _add_cli_app_data(gemini)

    adapter.uninstall()

    assert not old.exists()
    assert not (gemini / _PLUGIN).exists()
    assert not list(gemini.rglob("SKILL.md"))
    remainder = anchor.read_text(encoding="utf-8")
    assert "Keep my own guidance." in remainder
    assert "APOTHEM MANAGED BLOCK" not in remainder
    [backup] = _old_plugin_backups()
    manifest = json.loads((backup / "plugin.json").read_text(encoding="utf-8"))
    assert manifest["name"] == "apothem"
    assert list((backup / "skills").glob("*/SKILL.md"))
    # The uninstall record references that backup, so retention keeps it.
    marker = install_ledger.latest_record("antigravity", kind=None)
    assert marker is not None
    assert marker.kind == "uninstall"
    assert backup in {
        Path(target.backup_ref) for target in marker.targets if target.backup_ref
    }
    for path, data in app_data.items():
        assert path.read_bytes() == data, path


def test_old_plugin_folder_reads_installed_but_unverified_until_updated(
    adapter: AntigravityAdapter, gemini: Path
) -> None:
    adapter.install({})
    _revert_to_the_old_plugin_folder(gemini)

    # GEMINI.md still carries the managed block, so the install is detected,
    # but the plugin folder Antigravity CLI loads is missing.
    assert adapter.is_installed() is True
    assert adapter.verify() is False

    adapter.update({})

    assert adapter.verify() is True


def test_uninstall_without_an_install_changes_nothing(
    adapter: AntigravityAdapter, gemini: Path
) -> None:
    # The sweep checks the old plugin folder and the two retired paths, finds
    # none of them, and so removes nothing and takes no backup.
    _add_cli_app_data(gemini)
    other = gemini / "config" / "plugins" / "other" / "plugin.json"
    other.parent.mkdir(parents=True)
    other.write_bytes(b'{"name": "other"}\n')
    before = _snapshot(gemini.parent)

    adapter.uninstall()

    assert _snapshot(gemini.parent) == before
    assert not install_driver.BACKUP_ROOT.exists()


def test_old_plugin_folder_alone_reads_installed_and_is_uninstalled(
    adapter: AntigravityAdapter, gemini: Path
) -> None:
    # An install from before the move whose GEMINI.md block is gone: the plugin
    # folder an earlier release wrote is the only trace left. It still proves
    # an install, so the uninstall gate lets the sweep run.
    adapter.install({})
    old = _revert_to_the_old_plugin_folder(gemini)
    (gemini / "GEMINI.md").unlink()

    assert adapter.is_installed() is True
    assert adapter.verify() is False

    adapter.uninstall()

    assert not old.exists()
    assert adapter.is_installed() is False
    assert _old_plugin_backups()
    marker = install_ledger.latest_record("antigravity", kind=None)
    assert marker is not None
    assert marker.kind == "uninstall"


def test_a_plugin_folder_without_apothem_files_does_not_prove_an_install(
    adapter: AntigravityAdapter, gemini: Path
) -> None:
    # Another tool's plugin of the same name, with none of Apothem's
    # `.apothem/` support files, is not evidence that Apothem installed.
    other = gemini / _OLD_PLUGIN / "plugin.json"
    other.parent.mkdir(parents=True)
    other.write_bytes(b'{"name": "apothem"}\n')

    assert adapter.is_installed() is False


_SKILL_TEXT = "---\nname: my-own\n---\n"


def _link_folder(link: Path, target: Path) -> None:
    """Make *link* a junction to *target* on Windows, else a symbolic link.

    Always a junction on Windows, even where the process may create symbolic
    links (CI runners can): the Windows run covers the junction, which
    ``is_symlink()`` does not see.
    """
    if sys.platform == "win32":
        import _winapi

        _winapi.CreateJunction(str(target), str(link))
    else:
        link.symlink_to(target, target_is_directory=True)


def _link_old_plugins_folder_to_the_new_one(gemini: Path) -> Path:
    """Make ``antigravity-cli/plugins`` another name for ``config/plugins``."""
    live = gemini / "config" / "plugins"
    link = gemini / "antigravity-cli" / "plugins"
    link.parent.mkdir(parents=True, exist_ok=True)
    _link_folder(link, live)
    return live / "apothem"


def test_a_link_between_the_plugin_folders_keeps_the_live_plugin(
    adapter: AntigravityAdapter, gemini: Path
) -> None:
    # The old plugins folder is a link onto the live one (a junction on
    # Windows), so the stale path `antigravity-cli/plugins/apothem` names the
    # live plugin. The sweep must not back it up and remove it, and an
    # operator's own file in it stays.
    adapter.install({})
    plugin = _link_old_plugins_folder_to_the_new_one(gemini)
    own = plugin / "skills" / "my-own" / "SKILL.md"
    own.parent.mkdir(parents=True)
    own.write_text(_SKILL_TEXT, encoding="utf-8")

    updated = adapter.update({})

    assert own.is_file()
    assert (plugin / "plugin.json").is_file()
    assert _old_plugin_backups() == []
    assert adapter.verify() is True
    link = gemini / "antigravity-cli" / "plugins"
    assert [w.message for w in updated.warnings if str(link) in w.message]

    removed = adapter.uninstall()

    # Uninstall removes Apothem's files from the plugin, not the operator's,
    # and says the link it kept stays behind.
    assert own.is_file()
    assert not (plugin / "plugin.json").exists()
    assert not removed.errors
    assert any(
        str(link) in w.message and "after an uninstall" in w.message
        for w in removed.warnings
    )


def test_a_dry_run_leaves_a_linked_old_folder_alone(
    adapter: AntigravityAdapter, gemini: Path
) -> None:
    adapter.install({})
    _link_old_plugins_folder_to_the_new_one(gemini)

    run = adapter.preview({})

    swept = [r for r in run.results if r.operation == "sweep_stale"]
    old = [
        r for r in swept if r.path.endswith("apothem") and "antigravity-cli" in r.path
    ]
    assert [r.outcome for r in old] == ["warning"]
    assert str(gemini / "antigravity-cli" / "plugins") in old[0].message
