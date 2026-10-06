# SPDX-License-Identifier: MIT

"""Operator configs Apothem cannot rewrite losslessly are never replaced.

OpenCode reads JSONC, OpenClaw reads JSON5, and an operator may hand-write
either into a ``.json`` file Apothem merges into. The merge re-serializes
strict JSON, so it cannot keep comments, trailing commas, or JSON5 syntax.
The contract pinned here:

* when the merge would not change any value, the operator's bytes stay as they
  are (no rewrite, no backup, ``unchanged``);
* when the merge must change a value in a file it cannot round-trip, the write
  is refused with ``config.unparseable`` and the file is left untouched;
* a file that does not parse at all is refused the same way instead of being
  replaced wholesale with the rendered config.

The same rules hold for the YAML (Hermes) native config, whose comments PyYAML
drops on a rewrite.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from apothem.harnesses._shared import install_driver
from apothem.harnesses._shared.install_driver import MaterializationError
from apothem.lib.propagation import load_manifest

_JSONC = (
    "{\n"
    "  // operator note: keep this model\n"
    '  "model": "anthropic/operator-model",\n'
    '  "theme": "dark",\n'
    "}\n"
)

_JSON5 = (
    "// OpenClaw gateway config (JSON5)\n"
    "{\n"
    "  gateway: { port: 18789, },\n"
    "  agents: { defaults: { workspace: '~/.openclaw/workspace' } },\n"
    "}\n"
)

_INCOMING_OPENCODE = json.dumps(
    {
        "$schema": "https://opencode.ai/config.json",
        "instructions": ["~/.config/opencode/.apothem/support/rules/*.md"],
    },
    indent=2,
)


def _apply(target: Path, content: str) -> install_driver.MaterializationResult:
    return install_driver.apply_operator_owned_content(
        target,
        content,
        install_root=target.parent,
        harness_name="opencode",
    )


def test_jsonc_config_needing_change_is_refused_untouched(tmp_path: Path) -> None:
    target = tmp_path / "opencode.json"
    target.write_text(_JSONC, encoding="utf-8")

    result = _apply(target, _INCOMING_OPENCODE)

    assert result.outcome == "error"
    assert result.detail["code"] == "config.unparseable"
    assert "instructions" in result.detail["fix"]
    assert target.read_text(encoding="utf-8") == _JSONC
    assert result.backup_path is None


def test_json5_config_with_nothing_to_add_is_left_byte_identical(
    tmp_path: Path,
) -> None:
    target = tmp_path / "openclaw.json"
    target.write_text(_JSON5, encoding="utf-8")

    result = _apply(target, "{}\n")

    assert result.outcome == "unchanged"
    assert target.read_text(encoding="utf-8") == _JSON5


def test_jsonc_config_already_carrying_the_keys_is_left_byte_identical(
    tmp_path: Path,
) -> None:
    target = tmp_path / "opencode.json"
    text = (
        "{\n"
        "  // added by hand, as the refusal message asks\n"
        '  "$schema": "https://opencode.ai/config.json",\n'
        '  "instructions": ["~/.config/opencode/.apothem/support/rules/*.md",],\n'
        '  "model": "anthropic/operator-model",\n'
        "}\n"
    )
    target.write_text(text, encoding="utf-8")

    result = _apply(target, _INCOMING_OPENCODE)

    assert result.outcome == "unchanged"
    assert target.read_text(encoding="utf-8") == text


def test_strict_json_semantic_noop_keeps_operator_formatting(tmp_path: Path) -> None:
    target = tmp_path / "openclaw.json"
    text = '{"gateway":{"port":18789}}\n'
    target.write_text(text, encoding="utf-8")

    result = _apply(target, "{}\n")

    assert result.outcome == "unchanged"
    assert target.read_text(encoding="utf-8") == text


@pytest.mark.parametrize(
    ("name", "data", "incoming", "harness"),
    [
        pytest.param(
            "openclaw.json",
            b'{\r\n  "gateway": {"port": 18789}\r\n}\r\n',
            "{}\n",
            "opencode",
            id="json",
        ),
        pytest.param(
            "config.yaml",
            b"# my hermes config\r\nmodel:\r\n  default: operator-model\r\n",
            "# managed header\n{}\n",
            "hermes",
            id="yaml",
        ),
    ],
)
def test_crlf_config_with_nothing_to_add_keeps_its_line_endings(
    tmp_path: Path, name: str, data: bytes, incoming: str, harness: str
) -> None:
    target = tmp_path / name
    target.write_bytes(data)

    result = install_driver.apply_operator_owned_content(
        target, incoming, install_root=tmp_path, harness_name=harness
    )

    assert result.outcome == "unchanged"
    assert target.read_bytes() == data


def test_garbage_config_is_refused_not_replaced(tmp_path: Path) -> None:
    target = tmp_path / "opencode.json"
    garbage = "{ this is not json at all\n"
    target.write_text(garbage, encoding="utf-8")

    result = _apply(target, _INCOMING_OPENCODE)

    assert result.outcome == "error"
    assert result.detail["code"] == "config.unparseable"
    assert target.read_text(encoding="utf-8") == garbage


def test_yaml_with_comments_needing_change_is_refused(tmp_path: Path) -> None:
    target = tmp_path / "config.yaml"
    text = "# my hermes config\nmodel:\n  default: operator-model  # keep\n"
    target.write_text(text, encoding="utf-8")

    result = install_driver.apply_operator_owned_content(
        target,
        "# managed header\nmcp_servers:\n  fs:\n    command: npx\n",
        install_root=tmp_path,
        harness_name="hermes",
    )

    assert result.outcome == "error"
    assert result.detail["code"] == "config.unparseable"
    assert target.read_text(encoding="utf-8") == text


def test_yaml_with_comments_and_nothing_to_add_is_left_byte_identical(
    tmp_path: Path,
) -> None:
    target = tmp_path / "config.yaml"
    text = "# my hermes config\nmodel:\n  default: operator-model  # keep\n"
    target.write_text(text, encoding="utf-8")

    result = install_driver.apply_operator_owned_content(
        target,
        "# managed header\n{}\n",
        install_root=tmp_path,
        harness_name="hermes",
    )

    assert result.outcome == "unchanged"
    assert target.read_text(encoding="utf-8") == text


def test_unparseable_yaml_is_refused_not_replaced(tmp_path: Path) -> None:
    target = tmp_path / "config.yaml"
    broken = "model: [unclosed\n"
    target.write_text(broken, encoding="utf-8")

    result = install_driver.apply_operator_owned_content(
        target,
        "mcp_servers:\n  fs:\n    command: npx\n",
        install_root=tmp_path,
        harness_name="hermes",
    )

    assert result.outcome == "error"
    assert result.detail["code"] == "config.unparseable"
    assert target.read_text(encoding="utf-8") == broken


def test_manifest_json_target_that_is_jsonc_aborts_install(tmp_path: Path) -> None:
    """The claude-code settings.json manifest entry gets the same refusal."""
    harness_root = tmp_path / ".claude"
    harness_root.mkdir()
    settings = harness_root / "settings.json"
    text = '{\n  // mine\n  "model": "operator-choice",\n}\n'
    settings.write_text(text, encoding="utf-8")
    assert "claude_code" in load_manifest()

    with pytest.raises(MaterializationError) as caught:
        install_driver.run_install("claude_code", harness_root=harness_root)

    errors = caught.value.run.errors
    assert errors
    assert errors[0].detail["code"] == "config.unparseable"
    assert settings.read_text(encoding="utf-8") == text
    # Nothing else was materialized: the refusal happens before the trees.
    assert not (harness_root / "agents").exists()


def test_unchanged_merge_writes_the_merged_text_when_the_file_is_gone(
    tmp_path: Path,
) -> None:
    from apothem.harnesses._shared.install_driver_jsonmerge import _merged_bytes

    gone = tmp_path / "removed-after-read.json"

    assert _merged_bytes(gone, "{}\n", "{}\n") == b"{}\n"
