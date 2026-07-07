# SPDX-License-Identifier: MIT

"""Unit tests for the open-claw harness adapter.

Protocol-conformance and install-smoke tests for the adapter.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

import apothem.harnesses.open_claw as open_claw_pkg
from apothem.harnesses import HarnessAdapter
from apothem.harnesses.open_claw import OpenClawAdapter

_ADAPTER_DIR = Path(open_claw_pkg.__file__).resolve().parent


def _capabilities() -> dict[str, object]:
    return yaml.safe_load(
        (_ADAPTER_DIR / "capabilities.yml").read_text(encoding="utf-8")
    )


@pytest.fixture
def adapter() -> OpenClawAdapter:
    return OpenClawAdapter()


def test_protocol_conformance(adapter: OpenClawAdapter) -> None:
    assert isinstance(adapter, HarnessAdapter)


def test_name(adapter: OpenClawAdapter) -> None:
    assert adapter.name == "open-claw"


def test_output_path_is_path(adapter: OpenClawAdapter) -> None:
    assert isinstance(adapter.output_path, Path)


def test_is_installed_returns_bool(adapter: OpenClawAdapter) -> None:
    result = adapter.is_installed()
    assert isinstance(result, bool)


def test_install_accepts_empty_profile(
    adapter: OpenClawAdapter,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "config"
    monkeypatch.setattr(type(adapter), "output_path", property(lambda self: target))
    adapter.install({})  # must not raise


def test_uninstall_noop_when_not_installed(
    adapter: OpenClawAdapter, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing = tmp_path / "nonexistent_config"
    monkeypatch.setattr(type(adapter), "output_path", property(lambda self: missing))
    adapter.uninstall()  # must not raise when output_path does not exist


def test_uninstall_keeps_operator_keys_and_strips_apothem(
    adapter: OpenClawAdapter, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Surgical uninstall of the materializer-rendered openclaw.json: the
    # operator authors their own keys into the config; uninstall keeps them and
    # leaves no whole-file .bak sibling. (OpenClaw renders an empty {} config, so
    # an operator-free install is an Apothem-only file the uninstall deletes.)
    import json

    from apothem.harnesses._shared import install_driver

    monkeypatch.setattr(install_driver, "BACKUP_ROOT", tmp_path / "apothem-backups")
    target = tmp_path / "openclaw.json"
    monkeypatch.setattr(type(adapter), "output_path", property(lambda self: target))

    adapter.install({})
    # The operator authors their own configuration into the file.
    target.write_text(json.dumps({"operatorKey": "value"}, indent=2), encoding="utf-8")

    adapter.uninstall()

    assert target.is_file()
    remaining = json.loads(target.read_text(encoding="utf-8"))
    assert remaining == {"operatorKey": "value"}
    assert not list(tmp_path.glob("openclaw.json.*.bak"))


def test_uninstall_deletes_apothem_only_config(
    adapter: OpenClawAdapter, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # An Apothem-only config (empty render, no operator keys) is deleted.
    from apothem.harnesses._shared import install_driver

    monkeypatch.setattr(install_driver, "BACKUP_ROOT", tmp_path / "apothem-backups")
    target = tmp_path / "openclaw.json"
    monkeypatch.setattr(type(adapter), "output_path", property(lambda self: target))

    adapter.install({})
    assert target.is_file()

    adapter.uninstall()

    assert not target.exists()
    assert not list(tmp_path.glob("openclaw.json.*.bak"))


def test_capabilities_declare_subagent_dispatch_and_no_mcp_file() -> None:
    # Open-Claw documents subagents via agents.list[].subagents.allowAgents,
    # but MCP is a CLI-command surface with no adapter-owned config-file block.
    # Skills are an agents.defaults.skills allowlist, not an extraDirs loader.
    capabilities = _capabilities()
    assert capabilities["sub_agent_dispatch"] is True
    assert capabilities["mcp_servers"] == []
    assert capabilities["custom_command_support"] != "skills-extraDirs"
