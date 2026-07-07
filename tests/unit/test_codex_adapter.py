# SPDX-License-Identifier: MIT

"""Unit tests for the codex harness adapter.

Protocol-conformance and install-smoke tests for the adapter.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from apothem.harnesses import HarnessAdapter
from apothem.harnesses import codex as codex_pkg
from apothem.harnesses.codex import CodexAdapter


@pytest.fixture
def adapter() -> CodexAdapter:
    return CodexAdapter()


def test_capabilities_declare_native_mcp_surface() -> None:
    """MCP is native via config.toml ``[mcp_servers]`` tables.

    The capabilities file must name the native MCP surface rather than an
    empty list — Codex supports MCP through ``[mcp_servers.<name>]`` tables
    in the operator-owned ``config.toml``.
    """
    caps_path = Path(codex_pkg.__file__).parent / "capabilities.yml"
    caps = yaml.safe_load(caps_path.read_text(encoding="utf-8"))

    assert caps["mcp_servers"], "codex MCP surface must not be the empty list"
    assert any("config.toml" in entry for entry in caps["mcp_servers"])


def test_protocol_conformance(adapter: CodexAdapter) -> None:
    assert isinstance(adapter, HarnessAdapter)


def test_name(adapter: CodexAdapter) -> None:
    assert adapter.name == "codex"


def test_output_path_is_path(adapter: CodexAdapter) -> None:
    assert isinstance(adapter.output_path, Path)


def test_output_path_honors_codex_home(
    adapter: CodexAdapter,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex-home"))

    assert adapter.output_path == tmp_path / "codex-home" / "AGENTS.md"


def test_is_installed_returns_bool(adapter: CodexAdapter) -> None:
    result = adapter.is_installed()
    assert isinstance(result, bool)


def test_install_accepts_empty_profile(
    adapter: CodexAdapter,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "AGENTS.md"
    monkeypatch.setattr(type(adapter), "output_path", property(lambda self: target))
    adapter.install({})  # must not raise
    assert target.is_file()
    assert (tmp_path / "hooks.json").is_file()
    assert (tmp_path / "hooks" / "dispatch.py").is_file()
    assert adapter.verify()


def test_install_renders_dispatch_path_into_hooks_json(
    adapter: CodexAdapter,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A full install renders ``${HARNESS_ROOT}`` into hooks.json commands.

    Both the POSIX (``python3``) and Windows (``py -3``) command strings
    must point at the installed dispatcher by forward-slash absolute path.
    """
    target = tmp_path / "AGENTS.md"
    monkeypatch.setattr(type(adapter), "output_path", property(lambda self: target))

    adapter.install({})

    text = (tmp_path / "hooks.json").read_text(encoding="utf-8")
    assert "${HARNESS_ROOT}" not in text
    parsed = json.loads(text)
    root_posix = tmp_path.resolve().as_posix()
    session_hook = parsed["hooks"]["SessionStart"][0]["hooks"][0]
    assert session_hook["command"] == (
        f'python3 "{root_posix}/hooks/dispatch.py" SessionStart'
    )
    assert session_hook["commandWindows"] == (
        f'py -3 "{root_posix}/hooks/dispatch.py" SessionStart'
    )
    # The rendered command path resolves to the dispatcher of this install.
    assert (tmp_path / "hooks" / "dispatch.py").is_file()


def test_uninstall_noop_when_not_installed(
    adapter: CodexAdapter, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing = tmp_path / "nonexistent_config"
    monkeypatch.setattr(type(adapter), "output_path", property(lambda self: missing))
    adapter.uninstall()  # must not raise when output_path does not exist


def test_uninstall_strips_block_and_keeps_operator_prose(
    adapter: CodexAdapter, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Surgical uninstall: install the AGENTS.md managed block over operator
    # prose, uninstall, and assert the operator prose survives, the Apothem block
    # is removed, and no whole-file .bak sibling is left beside the operator file.
    from apothem.harnesses._shared import install_driver

    monkeypatch.setattr(install_driver, "BACKUP_ROOT", tmp_path / "apothem-backups")
    # The manifest target is ${HARNESS_ROOT}/AGENTS.md and the harness root is
    # output_path.parent, so name the output file AGENTS.md so they coincide.
    target = tmp_path / "AGENTS.md"
    operator_prose = "# Operator notes\n\nKeep my own guidance.\n"
    target.write_text(operator_prose, encoding="utf-8")
    monkeypatch.setattr(type(adapter), "output_path", property(lambda self: target))

    adapter.install({})
    assert "APOTHEM MANAGED BLOCK" in target.read_text(encoding="utf-8")

    adapter.uninstall()

    remainder = target.read_text(encoding="utf-8")
    assert "Keep my own guidance." in remainder
    assert "APOTHEM MANAGED BLOCK" not in remainder
    assert not list(tmp_path.glob("AGENTS.md.*.bak"))
