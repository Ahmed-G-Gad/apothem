# SPDX-License-Identifier: MIT

"""Unit tests for the gemini-cli harness adapter.

Protocol-conformance and install-smoke tests for the adapter.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from apothem.harnesses import HarnessAdapter
from apothem.harnesses import gemini_cli as gemini_pkg
from apothem.harnesses.gemini_cli import GeminiCliAdapter


@pytest.fixture
def adapter() -> GeminiCliAdapter:
    return GeminiCliAdapter()


def test_capabilities_declare_native_mcp_surface() -> None:
    """MCP is native via the ``mcpServers`` object in ``settings.json``.

    The capabilities file must name the native MCP surface rather than an
    empty list — Gemini CLI supports MCP through the operator-owned
    ``settings.json`` ``mcpServers`` object (stdio and HTTP transports).
    """
    caps_path = Path(gemini_pkg.__file__).parent / "capabilities.yml"
    caps = yaml.safe_load(caps_path.read_text(encoding="utf-8"))

    assert caps["mcp_servers"], "gemini-cli MCP surface must not be the empty list"
    assert any("settings.json" in entry for entry in caps["mcp_servers"])


def test_capabilities_memory_surface_is_context_anchor() -> None:
    """Memory lives in the GEMINI.md context anchor, not a memory directory.

    The Auto Memory feature stores durable memory in ``GEMINI.md`` via a
    review inbox; there is no ``.gemini/memory/`` directory, so the
    capability value must not claim one.
    """
    caps_path = Path(gemini_pkg.__file__).parent / "capabilities.yml"
    caps = yaml.safe_load(caps_path.read_text(encoding="utf-8"))

    assert ".gemini/memory/" not in caps["agent_memory_surface"]
    assert "GEMINI.md" in caps["agent_memory_surface"]


def test_capabilities_system_prompt_template_exists() -> None:
    """The declared system-prompt template path resolves to a real file.

    The adapter performs a raw template copy (no Jinja render), so the
    declared template path must point at an on-disk template rather than a
    non-existent rendered variant.
    """
    pkg_dir = Path(gemini_pkg.__file__).parent
    caps = yaml.safe_load((pkg_dir / "capabilities.yml").read_text(encoding="utf-8"))

    template_path = pkg_dir / caps["system_prompt_template_path"]
    assert template_path.is_file(), f"template not found: {template_path}"


def test_protocol_conformance(adapter: GeminiCliAdapter) -> None:
    assert isinstance(adapter, HarnessAdapter)


def test_name(adapter: GeminiCliAdapter) -> None:
    assert adapter.name == "gemini-cli"


def test_output_path_is_path(adapter: GeminiCliAdapter) -> None:
    assert isinstance(adapter.output_path, Path)


def test_is_installed_returns_bool(adapter: GeminiCliAdapter) -> None:
    result = adapter.is_installed()
    assert isinstance(result, bool)


def test_install_accepts_empty_profile(
    adapter: GeminiCliAdapter,
    tmp_path: Path,
) -> None:
    # Project-scope adapter: the target is resolved under --project.
    adapter.install({}, project=tmp_path)  # must not raise


def test_uninstall_noop_when_not_installed(
    adapter: GeminiCliAdapter, tmp_path: Path
) -> None:
    # No config file present under the project root -> uninstall is a noop.
    adapter.uninstall(project=tmp_path)  # must not raise when target absent


def test_uninstall_strips_block_and_keeps_operator_prose(
    adapter: GeminiCliAdapter, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Surgical uninstall: operator prose survives, the Apothem managed block
    # is removed, and no whole-file .bak sibling is left in the operator
    # directory (the pre-mutation file is backed up under the Apothem backup root).
    from apothem.harnesses._shared import install_driver

    monkeypatch.setattr(install_driver, "BACKUP_ROOT", tmp_path / "apothem-backups")
    target = adapter.resolve_output_path(tmp_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    operator_prose = "# Operator rules\n\nKeep my own guidance.\n"
    target.write_text(operator_prose, encoding="utf-8")

    adapter.install({}, project=tmp_path)
    assert "APOTHEM MANAGED BLOCK" in target.read_text(encoding="utf-8")

    adapter.uninstall(project=tmp_path)

    remainder = target.read_text(encoding="utf-8")
    assert "Keep my own guidance." in remainder
    assert "APOTHEM MANAGED BLOCK" not in remainder
    assert not list(target.parent.glob(f"{target.name}.*.bak"))
