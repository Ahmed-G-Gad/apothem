# SPDX-License-Identifier: MIT

"""Unit tests for the glm harness adapter.

Protocol-conformance and install-smoke tests for the adapter. GLM (Z.ai) is a
model backend, not a coding-agent tool: the adapter writes a single
Apothem-owned TOML provider file and authors no coding-agent cohort.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

import apothem.harnesses.glm as glm_pkg
from apothem.harnesses import HarnessAdapter
from apothem.harnesses.glm import GlmAdapter

_ADAPTER_DIR = Path(glm_pkg.__file__).resolve().parent


def _capabilities() -> dict[str, object]:
    return yaml.safe_load(
        (_ADAPTER_DIR / "capabilities.yml").read_text(encoding="utf-8")
    )


@pytest.fixture
def adapter() -> GlmAdapter:
    return GlmAdapter()


def test_protocol_conformance(adapter: GlmAdapter) -> None:
    assert isinstance(adapter, HarnessAdapter)


def test_name(adapter: GlmAdapter) -> None:
    assert adapter.name == "glm"


def test_output_path_is_path(adapter: GlmAdapter) -> None:
    assert isinstance(adapter.output_path, Path)


def test_is_installed_returns_bool(adapter: GlmAdapter) -> None:
    result = adapter.is_installed()
    assert isinstance(result, bool)


def test_install_accepts_empty_profile(
    adapter: GlmAdapter,
    tmp_path: Path,
) -> None:
    # Project-scope adapter: the target is resolved under --project.
    adapter.install({}, project=tmp_path)  # must not raise


def test_install_writes_provider_config(
    adapter: GlmAdapter,
    tmp_path: Path,
) -> None:
    # The Apothem-owned provider file lands at the resolved target and is
    # non-empty TOML carrying both backend base URLs.
    adapter.install({}, project=tmp_path)
    target = adapter.resolve_output_path(tmp_path)
    assert target.is_file()
    content = target.read_text(encoding="utf-8")
    assert "https://api.z.ai/api/anthropic" in content
    assert "https://api.z.ai/api/coding/paas/v4" in content


def test_uninstall_noop_when_not_installed(adapter: GlmAdapter, tmp_path: Path) -> None:
    # No config file present under the project root -> uninstall is a noop.
    adapter.uninstall(project=tmp_path)  # must not raise when target absent


def test_uninstall_removes_provider_file(
    adapter: GlmAdapter, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Install the Apothem-owned provider file, uninstall, and assert the file is
    # gone and no whole-file .bak sibling is left in the project directory.
    from apothem.harnesses._shared import install_driver

    monkeypatch.setattr(install_driver, "BACKUP_ROOT", tmp_path / "apothem-backups")
    adapter.install({}, project=tmp_path)
    target = adapter.resolve_output_path(tmp_path)
    assert target.is_file()

    adapter.uninstall(project=tmp_path)

    assert not target.exists()
    assert not list(target.parent.glob(f"{target.name}.*.bak"))


def test_capabilities_template_path_resolves_to_existing_file() -> None:
    # The declared system-prompt template must name a real on-disk template.
    capabilities = _capabilities()
    template_rel = capabilities["system_prompt_template_path"]
    assert isinstance(template_rel, str)
    assert (_ADAPTER_DIR / template_rel).is_file()


def test_capabilities_declares_no_mcp_surface() -> None:
    # GLM is a model backend; it hosts no MCP servers. The mcp_servers list is
    # empty, consistent with the registry's unsupported mcp_servers cell.
    capabilities = _capabilities()
    assert capabilities["mcp_servers"] == []


def test_capabilities_sub_agent_dispatch_is_false() -> None:
    # A model backend dispatches no sub-agents.
    capabilities = _capabilities()
    assert capabilities["sub_agent_dispatch"] is False
