# SPDX-License-Identifier: MIT

"""Unit tests for the antigravity harness adapter.

Protocol-conformance and install-smoke tests for the adapter.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from apothem.harnesses import HarnessAdapter
from apothem.harnesses import antigravity as antigravity_pkg
from apothem.harnesses.antigravity import AntigravityAdapter


@pytest.fixture
def adapter() -> AntigravityAdapter:
    return AntigravityAdapter()


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

    plugin_path = tmp_path / "antigravity-cli" / "plugins" / "apothem" / "plugin.json"
    plugin = json.loads(plugin_path.read_text(encoding="utf-8"))
    assert plugin["name"] == "apothem"
    assert (tmp_path / "antigravity-cli" / "plugins" / "apothem" / "skills").is_dir()
    assert (tmp_path / "antigravity-cli" / "plugins" / "apothem" / "rules").is_dir()
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
    from apothem.harnesses._shared import install_driver

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
