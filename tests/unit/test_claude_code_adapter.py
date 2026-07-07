# SPDX-License-Identifier: MIT

"""Unit tests for the claude-code harness adapter.

Protocol-conformance and install-smoke tests for the adapter.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from apothem.harnesses import HarnessAdapter
from apothem.harnesses import claude_code as claude_code_pkg
from apothem.harnesses.claude_code import ClaudeCodeAdapter


@pytest.fixture
def adapter() -> ClaudeCodeAdapter:
    return ClaudeCodeAdapter()


def test_capabilities_mcp_and_permission_surfaces() -> None:
    """MCP registers outside settings.json; permissions carry three tiers.

    MCP servers register via ``claude mcp add`` into ``~/.claude.json``
    (user/local scope) and project ``.mcp.json`` — not ``settings.json``.
    Permissions carry three tiers (``allow``/``ask``/``deny``).
    """
    caps_path = Path(claude_code_pkg.__file__).parent / "capabilities.yml"
    caps = yaml.safe_load(caps_path.read_text(encoding="utf-8"))

    mcp = " ".join(caps["mcp_servers"])
    assert "claude.json" in mcp
    assert ".mcp.json" in mcp
    assert "settings.json" not in mcp

    permissions = caps["context_ignore_surface"]
    assert "ask" in permissions
    assert "deny" in permissions


def test_protocol_conformance(adapter: ClaudeCodeAdapter) -> None:
    assert isinstance(adapter, HarnessAdapter)


def test_name(adapter: ClaudeCodeAdapter) -> None:
    assert adapter.name == "claude-code"


def test_output_path_is_path(adapter: ClaudeCodeAdapter) -> None:
    assert isinstance(adapter.output_path, Path)


def test_is_installed_returns_bool(adapter: ClaudeCodeAdapter) -> None:
    result = adapter.is_installed()
    assert isinstance(result, bool)


def test_install_accepts_empty_profile(
    adapter: ClaudeCodeAdapter,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "config"
    monkeypatch.setattr(type(adapter), "output_path", property(lambda self: target))
    adapter.install({})  # must not raise


def test_install_renders_hook_paths_and_propagates_support_trees(
    adapter: ClaudeCodeAdapter,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A full install writes settings.json with rendered absolute hook paths.

    The template's ``${HARNESS_ROOT}`` tokens resolve to the forward-slash
    absolute harness root, the deny list scopes the site exclusion to the
    generated build output, and the conformity gate plus schema fixtures
    land under the Apothem support subtree the hook entries point at.
    """
    target = tmp_path / "CLAUDE.md"
    monkeypatch.setattr(type(adapter), "output_path", property(lambda self: target))

    adapter.install({})

    text = (tmp_path / "settings.json").read_text(encoding="utf-8")
    assert "${HARNESS_ROOT}" not in text
    settings = json.loads(text)
    root_posix = tmp_path.resolve().as_posix()
    session_args = settings["hooks"]["SessionStart"][0]["hooks"][0]["args"]
    assert session_args == [
        f"{root_posix}/.apothem/support/hooks/dispatch.py",
        "SessionStart",
    ]
    deny = set(settings["permissions"]["deny"])
    assert "Read(**/site/dist/**)" in deny
    assert "Read(**/site/**)" not in deny
    # The rendered hook paths resolve to on-disk scripts of the same install.
    assert (tmp_path / ".apothem" / "support" / "hooks" / "dispatch.py").is_file()
    assert (tmp_path / ".apothem" / "support" / "conformity" / "gate.py").is_file()
    assert (tmp_path / ".apothem" / "support" / "schemas").is_dir()


def test_install_projects_profile_into_claude_md_managed_block(
    adapter: ClaudeCodeAdapter,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two distinct profiles yield distinct CLAUDE.md managed blocks.

    The profile-derived identity/rule content appears verbatim inside the
    Apothem sentinels; the block differs across profiles; operator prose outside
    the sentinels survives; and re-install with the same profile is idempotent.
    """
    target = tmp_path / "settings.json"
    monkeypatch.setattr(type(adapter), "output_path", property(lambda self: target))
    claude_md = tmp_path / "CLAUDE.md"

    # Operator prose authored before any install must survive the merge.
    claude_md.write_text("# My Notes\n\nKeep my own instructions.\n", encoding="utf-8")

    profile_a = {"identity": {"name": "Ada Lovelace"}, "rules": ["rule-alpha"]}
    adapter.install(profile_a)
    text_a = claude_md.read_text(encoding="utf-8")

    assert "BEGIN APOTHEM MANAGED BLOCK" in text_a
    assert "Keep my own instructions." in text_a  # operator prose preserved
    assert "Ada Lovelace" in text_a
    assert "rule-alpha" in text_a

    # Idempotent re-install with the same profile is byte-identical.
    adapter.install(profile_a)
    assert claude_md.read_text(encoding="utf-8") == text_a

    # A distinct profile yields a distinct managed block.
    profile_b = {"identity": {"name": "Grace Hopper"}, "rules": ["rule-beta"]}
    adapter.install(profile_b)
    text_b = claude_md.read_text(encoding="utf-8")

    assert text_a != text_b
    assert "Grace Hopper" in text_b
    assert "rule-beta" in text_b
    # The replaced block no longer carries profile A's distinctive content.
    block_b = text_b.split("BEGIN APOTHEM MANAGED BLOCK")[1]
    assert "Ada Lovelace" not in block_b
    assert "rule-alpha" not in block_b
    # Exactly one managed block; operator prose still present.
    assert text_b.count("BEGIN APOTHEM MANAGED BLOCK") == 1
    assert "Keep my own instructions." in text_b


def test_install_interpreter_failure_leaves_no_literal_python_bin(
    adapter: ClaudeCodeAdapter,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A hook-interpreter resolution failure never leaves literal ${PYTHON_BIN}.

    H8 regression: ``resolve_python_bin`` is resolved BEFORE the manifest tree is
    written, so when it raises (no real CPython >= 3.10 on the host) the install
    aborts with nothing on disk — never a half-written ``settings.json`` whose
    every hook ``command`` still carries the unresolved ``${PYTHON_BIN}`` token
    (which would then invoke a nonexistent binary at hook-run time).
    """
    from apothem.harnesses.claude_code import install as install_mod

    target = tmp_path / "settings.json"
    monkeypatch.setattr(type(adapter), "output_path", property(lambda self: target))

    def _boom() -> Path:
        raise RuntimeError("no real CPython >= 3.10 interpreter found for hook wiring")

    monkeypatch.setattr(install_mod, "resolve_python_bin", _boom)

    with pytest.raises(RuntimeError):
        adapter.install({})

    # No tree was written at all — resolution precedes every write.
    assert not target.exists()
    # And, defensively, no file anywhere under the harness root carries the token.
    for path in tmp_path.rglob("*"):
        if path.is_file():
            assert "${PYTHON_BIN}" not in path.read_text(encoding="utf-8")


def test_uninstall_noop_when_not_installed(
    adapter: ClaudeCodeAdapter, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing = tmp_path / "nonexistent_config"
    monkeypatch.setattr(type(adapter), "output_path", property(lambda self: missing))
    adapter.uninstall()  # must not raise when output_path does not exist


def test_uninstall_keeps_operator_keys_and_strips_apothem(
    adapter: ClaudeCodeAdapter, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Surgical uninstall: install a real settings.json, add an operator key
    # and an operator-added deny permission, uninstall, and assert the operator
    # content survives while Apothem's keys and hook handlers are removed — with
    # NO whole-file .bak sibling in the operator directory (the pre-mutation file
    # is captured under the Apothem backup root instead).
    from apothem.harnesses._shared import install_driver

    monkeypatch.setattr(install_driver, "BACKUP_ROOT", tmp_path / "apothem-backups")
    # The manifest write_text target is ${HARNESS_ROOT}/settings.json and the
    # harness root is output_path.parent, so output_path must be settings.json.
    target = tmp_path / "settings.json"
    monkeypatch.setattr(type(adapter), "output_path", property(lambda self: target))

    adapter.install({})
    installed = json.loads(target.read_text(encoding="utf-8"))
    assert "hooks" in installed  # Apothem wired hook handlers
    # The operator augments the Apothem-installed config.
    installed["operatorCustom"] = {"keep": True}
    installed["permissions"]["deny"].append("Read(operator-secret/**)")
    target.write_text(json.dumps(installed, indent=2), encoding="utf-8")

    adapter.uninstall()

    assert target.is_file()  # operator content remains, so the file is kept
    remaining = json.loads(target.read_text(encoding="utf-8"))
    assert remaining["operatorCustom"] == {"keep": True}
    assert remaining["permissions"]["deny"] == ["Read(operator-secret/**)"]
    assert "hooks" not in remaining  # Apothem hook handlers stripped
    assert "allow" not in remaining.get("permissions", {})
    # No destructive whole-file .bak sibling in the operator directory.
    assert not list(tmp_path.glob("settings.json.*.bak"))
    # The pre-mutation file is recoverable from the Apothem backup root.
    assert list((tmp_path / "apothem-backups").rglob("settings.json"))
