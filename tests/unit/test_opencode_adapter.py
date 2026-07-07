# SPDX-License-Identifier: MIT

"""Unit tests for the opencode harness adapter.

Protocol-conformance and install-smoke tests for the adapter.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

import apothem.harnesses.opencode as opencode_pkg
from apothem.harnesses import HarnessAdapter
from apothem.harnesses.opencode import OpenCodeAdapter

_ADAPTER_DIR = Path(opencode_pkg.__file__).resolve().parent


def _capabilities() -> dict[str, object]:
    return yaml.safe_load(
        (_ADAPTER_DIR / "capabilities.yml").read_text(encoding="utf-8")
    )


@pytest.fixture
def adapter() -> OpenCodeAdapter:
    return OpenCodeAdapter()


def test_protocol_conformance(adapter: OpenCodeAdapter) -> None:
    assert isinstance(adapter, HarnessAdapter)


def test_name(adapter: OpenCodeAdapter) -> None:
    assert adapter.name == "opencode"


def test_output_path_is_path(adapter: OpenCodeAdapter) -> None:
    assert isinstance(adapter.output_path, Path)


def test_is_installed_returns_bool(adapter: OpenCodeAdapter) -> None:
    result = adapter.is_installed()
    assert isinstance(result, bool)


def test_install_accepts_empty_profile(
    adapter: OpenCodeAdapter,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "config"
    monkeypatch.setattr(type(adapter), "output_path", property(lambda self: target))
    adapter.install({})  # must not raise


def test_uninstall_noop_when_not_installed(
    adapter: OpenCodeAdapter, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing = tmp_path / "nonexistent_config"
    monkeypatch.setattr(type(adapter), "output_path", property(lambda self: missing))
    adapter.uninstall()  # must not raise when output_path does not exist


def test_uninstall_keeps_operator_keys_and_strips_apothem(
    adapter: OpenCodeAdapter, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Surgical uninstall of the materializer-rendered opencode.json: install,
    # add an operator key, uninstall, and assert the operator key survives while
    # Apothem's keys are stripped — with NO whole-file .bak sibling.
    import json

    from apothem.harnesses._shared import install_driver

    monkeypatch.setattr(install_driver, "BACKUP_ROOT", tmp_path / "apothem-backups")
    target = tmp_path / "opencode.json"
    monkeypatch.setattr(type(adapter), "output_path", property(lambda self: target))

    adapter.install({})
    installed = json.loads(target.read_text(encoding="utf-8"))
    assert "instructions" in installed  # Apothem-authored key
    installed["operatorKey"] = True
    target.write_text(json.dumps(installed, indent=2), encoding="utf-8")

    adapter.uninstall()

    assert target.is_file()  # operator content remains
    remaining = json.loads(target.read_text(encoding="utf-8"))
    assert remaining.get("operatorKey") is True
    assert "$schema" not in remaining
    assert "instructions" not in remaining
    assert not list(tmp_path.glob("opencode.json.*.bak"))


def test_capabilities_declare_native_mcp_and_subagent_dispatch() -> None:
    # OpenCode documents a top-level mcp block and subagent dispatch; the
    # config is rendered directly with no Jinja template (n/a template path).
    capabilities = _capabilities()
    assert capabilities["mcp_servers"]
    assert capabilities["sub_agent_dispatch"] is True
    assert capabilities["system_prompt_template_path"] == "n/a"
