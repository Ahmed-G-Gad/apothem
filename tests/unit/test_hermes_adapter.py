# SPDX-License-Identifier: MIT

"""Unit tests for the hermes harness adapter.

Protocol-conformance and install-smoke tests for the adapter.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

import apothem.harnesses.hermes as hermes_pkg
from apothem.harnesses import HarnessAdapter
from apothem.harnesses.hermes import HermesAdapter

_ADAPTER_DIR = Path(hermes_pkg.__file__).resolve().parent


def _capabilities() -> dict[str, object]:
    return yaml.safe_load(
        (_ADAPTER_DIR / "capabilities.yml").read_text(encoding="utf-8")
    )


@pytest.fixture
def adapter() -> HermesAdapter:
    return HermesAdapter()


def test_protocol_conformance(adapter: HermesAdapter) -> None:
    assert isinstance(adapter, HarnessAdapter)


def test_name(adapter: HermesAdapter) -> None:
    assert adapter.name == "hermes"


def test_output_path_is_path(adapter: HermesAdapter) -> None:
    assert isinstance(adapter.output_path, Path)


def test_is_installed_returns_bool(adapter: HermesAdapter) -> None:
    result = adapter.is_installed()
    assert isinstance(result, bool)


def test_install_accepts_empty_profile(
    adapter: HermesAdapter,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "config"
    monkeypatch.setattr(type(adapter), "output_path", property(lambda self: target))
    adapter.install({})  # must not raise


def test_uninstall_noop_when_not_installed(
    adapter: HermesAdapter, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing = tmp_path / "nonexistent_config"
    monkeypatch.setattr(type(adapter), "output_path", property(lambda self: missing))
    adapter.uninstall()  # must not raise when output_path does not exist


def test_uninstall_keeps_operator_keys_and_strips_apothem(
    adapter: HermesAdapter, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Surgical uninstall of the materializer-rendered config.yaml: install
    # with an MCP server (so Apothem writes mcp_servers), add operator
    # channels/auth keys, uninstall, and assert the operator keys survive while
    # Apothem's server entries are removed — with NO whole-file .bak sibling.
    from apothem.harnesses._shared import install_driver

    monkeypatch.setattr(install_driver, "BACKUP_ROOT", tmp_path / "apothem-backups")
    target = tmp_path / "config.yaml"
    monkeypatch.setattr(type(adapter), "output_path", property(lambda self: target))

    adapter.install({"mcp_servers": {"demo": {"command": "demo-bin"}}})
    doc = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    assert "demo" in doc["mcp_servers"]  # Apothem-authored MCP server
    doc["channels"] = {"slack": "xoxb-token"}
    doc["auth"] = {"token": "operator-secret"}
    target.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")

    adapter.uninstall()

    assert target.is_file()  # operator content remains
    remaining = yaml.safe_load(target.read_text(encoding="utf-8"))
    assert remaining["channels"] == {"slack": "xoxb-token"}
    assert remaining["auth"] == {"token": "operator-secret"}
    assert "mcp_servers" not in remaining
    assert not list(tmp_path.glob("config.yaml.*.bak"))


def test_capabilities_declare_mcp_subagent_and_memory() -> None:
    # Hermes documents the top-level mcp_servers block, delegation/delegate_task
    # subagent dispatch, and durable memory at ~/.hermes/memories/.
    capabilities = _capabilities()
    assert capabilities["mcp_servers"]
    assert capabilities["sub_agent_dispatch"] is True
    assert "memories" in str(capabilities["agent_memory_surface"])


def test_update_moves_servers_out_of_the_auxiliary_model_slot(
    adapter: HermesAdapter, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Earlier releases wrote the profile's servers under auxiliary.mcp, which
    # Hermes reads as the auxiliary model slot for MCP tool dispatch. An update
    # over such a config moves them to the top-level mcp_servers block and
    # leaves the operator's own auxiliary routing alone.
    from apothem.lib import install_ledger
    from apothem.lib.install_ledger import LedgerRecord, LedgerTarget

    target = tmp_path / ".hermes" / "config.yaml"
    target.parent.mkdir()
    monkeypatch.setattr(type(adapter), "output_path", property(lambda self: target))
    profile = {
        "mcp_servers": {"fs": {"transport": "stdio", "command": "npx", "args": ["srv"]}}
    }
    legacy = {
        "auxiliary": {
            "compression": {"provider": "openrouter"},
            "mcp": {"fs": {"command": "npx", "args": ["srv"]}},
        }
    }
    target.write_text(yaml.safe_dump(legacy, sort_keys=False), encoding="utf-8")
    # The install record an earlier release left (no ownership recorded).
    install_ledger.append_record(
        LedgerRecord.create(
            harness="hermes",
            root=target.parent,
            kind="install",
            targets=(LedgerTarget(str(target), "write_text", "operator-owned"),),
        )
    )

    adapter.update(profile)

    doc = yaml.safe_load(target.read_text(encoding="utf-8"))
    assert doc["mcp_servers"] == {"fs": {"command": "npx", "args": ["srv"]}}
    assert doc["auxiliary"] == {"compression": {"provider": "openrouter"}}

    adapter.uninstall()
    remaining = yaml.safe_load(target.read_text(encoding="utf-8"))
    assert remaining == {"auxiliary": {"compression": {"provider": "openrouter"}}}
