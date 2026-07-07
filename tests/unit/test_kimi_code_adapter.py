# SPDX-License-Identifier: MIT

"""Unit tests for the kimi_code harness adapter.

Protocol-conformance and install-smoke tests for the adapter.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

import apothem.harnesses.kimi_code as kimi_code_pkg
from apothem.harnesses import HarnessAdapter
from apothem.harnesses.kimi_code import KimiCodeAdapter

_ADAPTER_DIR = Path(kimi_code_pkg.__file__).resolve().parent


def _capabilities() -> dict[str, object]:
    return yaml.safe_load(
        (_ADAPTER_DIR / "capabilities.yml").read_text(encoding="utf-8")
    )


@pytest.fixture
def adapter() -> KimiCodeAdapter:
    return KimiCodeAdapter()


def test_protocol_conformance(adapter: KimiCodeAdapter) -> None:
    assert isinstance(adapter, HarnessAdapter)


def test_name(adapter: KimiCodeAdapter) -> None:
    assert adapter.name == "kimi-code"


def test_output_path_is_path(adapter: KimiCodeAdapter) -> None:
    assert isinstance(adapter.output_path, Path)


def test_output_path_targets_project_root_agents_md(
    adapter: KimiCodeAdapter, tmp_path: Path
) -> None:
    # The Kimi Code instruction surface is the project-root AGENTS.md.
    resolved = adapter.resolve_output_path(tmp_path)
    assert resolved == tmp_path / "AGENTS.md"


def test_is_installed_returns_bool(adapter: KimiCodeAdapter) -> None:
    result = adapter.is_installed()
    assert isinstance(result, bool)


def test_install_accepts_empty_profile(
    adapter: KimiCodeAdapter,
    tmp_path: Path,
) -> None:
    # Project-scope adapter: the target is resolved under --project.
    adapter.install({}, project=tmp_path)  # must not raise


def test_uninstall_noop_when_not_installed(
    adapter: KimiCodeAdapter, tmp_path: Path
) -> None:
    # No config file present under the project root -> uninstall is a noop.
    adapter.uninstall(project=tmp_path)  # must not raise when target absent


def test_uninstall_strips_block_and_keeps_operator_prose(
    adapter: KimiCodeAdapter, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Surgical uninstall: install a real managed block over operator prose,
    # uninstall, and assert the operator prose survives, the Apothem block is
    # gone, and no whole-file .bak sibling is left in the operator directory.
    from apothem.harnesses._shared import install_driver

    monkeypatch.setattr(install_driver, "BACKUP_ROOT", tmp_path / "apothem-backups")
    target = adapter.resolve_output_path(tmp_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    operator_prose = "# Operator instructions\n\nKeep my own guidance.\n"
    target.write_text(operator_prose, encoding="utf-8")

    adapter.install({}, project=tmp_path)
    assert "APOTHEM MANAGED BLOCK" in target.read_text(encoding="utf-8")

    adapter.uninstall(project=tmp_path)

    remainder = target.read_text(encoding="utf-8")
    assert "Keep my own guidance." in remainder
    assert "APOTHEM MANAGED BLOCK" not in remainder
    assert not list(target.parent.glob(f"{target.name}.*.bak"))


def test_capabilities_template_path_resolves_to_existing_file() -> None:
    # The declared system-prompt template must name a real on-disk template,
    # not a non-existent .j2 variant.
    capabilities = _capabilities()
    template_rel = capabilities["system_prompt_template_path"]
    assert isinstance(template_rel, str)
    assert (_ADAPTER_DIR / template_rel).is_file()


def test_capabilities_names_operator_owned_mcp_surface() -> None:
    # Kimi Code MCP is the operator-owned surface at .kimi-code/mcp.json the
    # adapter recognizes but does not author.
    capabilities = _capabilities()
    mcp = capabilities["mcp_servers"]
    assert isinstance(mcp, list)
    assert mcp
    assert any(".kimi-code/mcp.json" in str(e) for e in mcp)
    assert capabilities["mcp_servers_authored"] is False


def test_capabilities_layered_context_names_support_tree() -> None:
    # The layered-context surface is AGENTS.md plus the
    # .kimi-code/.apothem/support tree.
    capabilities = _capabilities()
    layered = str(capabilities["layered_context_surface"])
    assert "AGENTS.md" in layered
    assert ".kimi-code/.apothem/support" in layered


def test_capabilities_declares_native_memory_and_subagents() -> None:
    # Kimi Code reads AGENTS.md as durable context and dispatches sub-agents.
    capabilities = _capabilities()
    assert capabilities["sub_agent_dispatch"] is True
    assert capabilities["custom_command_support"] == "yes"
    assert "AGENTS.md" in str(capabilities["agent_memory_surface"])
