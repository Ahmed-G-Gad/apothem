# SPDX-License-Identifier: MIT

"""Tests for the gated operator-owned native-config apply path.

The four materializer adapters (opencode, hermes, open_claw, qwen_code) write
their native config through ``apply_operator_owned_content`` so the write gets
the same backup + unified-diff + destructive-authorization gate that
claude_code's settings.json receives — and YAML targets now key-merge instead
of clobbering operator content.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from apothem.harnesses._shared import install_driver


def test_yaml_merge_preserves_operator_keys(tmp_path: Path) -> None:
    """Installing hermes-shaped YAML over an operator config keeps operator keys."""
    target = tmp_path / "config.yaml"
    target.write_text(
        "channels:\n  slack:\n    workspace: acme-team\nskills:\n  config: [x]\n",
        encoding="utf-8",
    )
    incoming = "skills:\n  config: [apothem-skill]\nauxiliary:\n  mcp: {}\n"

    result = install_driver.apply_operator_owned_content(
        target,
        incoming,
        install_root=tmp_path,
        harness_name="hermes",
    )

    assert result.outcome == "updated"
    merged = yaml.safe_load(target.read_text(encoding="utf-8"))
    # Operator-only key preserved.
    assert merged["channels"]["slack"]["workspace"] == "acme-team"
    # Incoming managed keys applied.
    assert merged["skills"]["config"] == ["apothem-skill"]
    assert "auxiliary" in merged
    # The result carries a unified diff for operator review.
    assert "diff" in result.detail


def test_gate_decline_leaves_operator_file_untouched(tmp_path: Path) -> None:
    """Declining the authorize gate skips the write; the operator file is intact."""
    target = tmp_path / "opencode.json"
    original = '{\n  "operator": "keep-me"\n}\n'
    target.write_text(original, encoding="utf-8")

    result = install_driver.apply_operator_owned_content(
        target,
        '{\n  "instructions": ["x"]\n}\n',
        install_root=tmp_path,
        harness_name="opencode",
        authorize=lambda _request: False,
    )

    assert result.outcome == "skipped"
    assert result.detail.get("destructive_gate") == "required"
    assert target.read_text(encoding="utf-8") == original


def test_clean_install_writes_content_verbatim(tmp_path: Path) -> None:
    """With no existing target the content is written verbatim (header intact)."""
    target = tmp_path / "config.yaml"
    content = "# managed by Apothem\nskills:\n  config: [a]\n"

    result = install_driver.apply_operator_owned_content(
        target,
        content,
        install_root=tmp_path,
        harness_name="hermes",
    )

    assert result.outcome == "created"
    assert target.read_text(encoding="utf-8") == content
