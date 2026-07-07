# SPDX-License-Identifier: MIT

"""Unit tests for the codebuddy harness adapter.

Protocol-conformance and install-smoke tests for the adapter.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

import apothem.harnesses.codebuddy as codebuddy_pkg
from apothem.harnesses import HarnessAdapter
from apothem.harnesses.codebuddy import CodeBuddyAdapter

_ADAPTER_DIR = Path(codebuddy_pkg.__file__).resolve().parent


def _capabilities() -> dict[str, object]:
    return yaml.safe_load(
        (_ADAPTER_DIR / "capabilities.yml").read_text(encoding="utf-8")
    )


@pytest.fixture
def adapter() -> CodeBuddyAdapter:
    return CodeBuddyAdapter()


def test_protocol_conformance(adapter: CodeBuddyAdapter) -> None:
    assert isinstance(adapter, HarnessAdapter)


def test_name(adapter: CodeBuddyAdapter) -> None:
    assert adapter.name == "codebuddy"


def test_output_path_is_path(adapter: CodeBuddyAdapter) -> None:
    assert isinstance(adapter.output_path, Path)


def test_is_installed_returns_bool(adapter: CodeBuddyAdapter) -> None:
    result = adapter.is_installed()
    assert isinstance(result, bool)


def test_install_accepts_empty_profile(
    adapter: CodeBuddyAdapter,
    tmp_path: Path,
) -> None:
    # Project-scope adapter: the target is resolved under --project.
    adapter.install({}, project=tmp_path)  # must not raise


def test_uninstall_noop_when_not_installed(
    adapter: CodeBuddyAdapter, tmp_path: Path
) -> None:
    # No config file present under the project root -> uninstall is a noop.
    adapter.uninstall(project=tmp_path)  # must not raise when target absent


def test_uninstall_strips_block_and_keeps_operator_prose(
    adapter: CodeBuddyAdapter, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Surgical uninstall: install a real managed block over operator prose,
    # uninstall, and assert the operator prose survives, the Apothem block is
    # gone, and no whole-file .bak sibling is left in the operator directory.
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


def test_capabilities_template_path_resolves_to_existing_file() -> None:
    # The declared system-prompt template must name a real on-disk template,
    # not a non-existent .j2 variant.
    capabilities = _capabilities()
    template_rel = capabilities["system_prompt_template_path"]
    assert isinstance(template_rel, str)
    assert (_ADAPTER_DIR / template_rel).is_file()


def test_capabilities_names_native_mcp_surface() -> None:
    # CodeBuddy MCP is a vendor-native, operator-owned surface at
    # .codebuddy/settings.json the adapter recognizes.
    capabilities = _capabilities()
    mcp = capabilities["mcp_servers"]
    assert isinstance(mcp, list)
    assert mcp
    assert any(".codebuddy/settings.json" in str(e) for e in mcp)


def test_capabilities_layered_context_names_rules_directory() -> None:
    # The workspace rules surface is a .codebuddy/rules/*.md directory, not a
    # single file.
    capabilities = _capabilities()
    assert ".codebuddy/rules" in str(capabilities["layered_context_surface"])
