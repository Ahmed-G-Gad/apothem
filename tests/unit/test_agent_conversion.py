# SPDX-License-Identifier: MIT

"""Converted agents keep their tool and turn limits, or drop the claim.

A source agent whose tool grant excludes Write and Edit is described as
read-only. Each converted agent must either carry a native restriction or make
no read-only claim:

- Codex custom agents accept ``sandbox_mode = "read-only"``; omitted
  ``model_reasoning_effort`` inherits the parent's effort
  (https://developers.openai.com/codex/subagents, retrieved 2026-10-02).
- Gemini CLI subagents accept a ``tools`` allowlist of Gemini tool names and
  ``max_turns`` (https://geminicli.com/docs/core/subagents, same date).
- Antigravity subagents take ``name`` and ``description``; an unmapped tool
  name can hang the subagent, so no tool list is emitted and the description
  drops the read-only claim (https://antigravity.google/docs/subagents).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

try:  # tomllib is stdlib from Python 3.11; pytest and mypy bring tomli on 3.10.
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10
    import tomli as tomllib

from apothem.harnesses._shared import install_driver
from apothem.lib.frontmatter import field_value

_PKG = Path(__file__).resolve().parents[2] / "src" / "apothem"
_AGENTS = sorted(p for p in (_PKG / "agents").glob("*.md") if p.name != "README.md")
_WRITE_TOOLS = {"write", "edit"}
_GEMINI_TOOLS = {
    "read_file",
    "read_many_files",
    "list_directory",
    "glob",
    "grep_search",
    "run_shell_command",
    "write_file",
    "replace",
    "google_web_search",
    "web_fetch",
    "write_todos",
}


def _names(path: Path, key: str) -> set[str]:
    raw = field_value(path, key) or ""
    return {item.strip().lower() for item in raw.split(",") if item.strip()}


def _read_only(path: Path) -> bool:
    return not (
        (_names(path, "tools") - _names(path, "disallowedTools")) & _WRITE_TOOLS
    )


def _fm(text: str) -> dict[str, object]:
    loaded = yaml.safe_load(text[4 : text.index("\n---\n", 4)])
    assert isinstance(loaded, dict)
    return loaded


def test_corpus_has_both_kinds_of_agent() -> None:
    kinds = {_read_only(p) for p in _AGENTS}
    assert kinds == {True, False}


def test_codex_agents_sandbox_read_only_agents_and_inherit_effort(
    tmp_path: Path,
) -> None:
    install_driver.run_install("codex", harness_root=tmp_path)
    for source in _AGENTS:
        data = tomllib.loads(
            (tmp_path / "agents" / f"{source.stem}.toml").read_text("utf-8")
        )
        assert "model_reasoning_effort" not in data, source.stem
        assert {"name", "description", "developer_instructions"} <= set(data)
        if _read_only(source):
            assert data.get("sandbox_mode") == "read-only", source.stem
        else:
            assert "sandbox_mode" not in data, source.stem


def test_gemini_agents_carry_tool_allowlist_and_turn_limit(tmp_path: Path) -> None:
    install_driver.run_install("gemini_cli", project_root=tmp_path)
    for source in _AGENTS:
        fields = _fm((tmp_path / ".gemini" / "agents" / source.name).read_text("utf-8"))
        tools = fields["tools"]
        assert isinstance(tools, list)
        assert tools
        assert set(tools) <= _GEMINI_TOOLS, source.stem
        if _read_only(source):
            assert not {"write_file", "replace"} & set(tools), source.stem
        assert fields["max_turns"] == int(field_value(source, "maxTurns") or 0)


def test_antigravity_agents_make_no_unenforced_read_only_claim(
    tmp_path: Path,
) -> None:
    install_driver.run_install("antigravity", harness_root=tmp_path)
    agents_dir = tmp_path / "antigravity-cli" / "plugins" / "apothem" / "agents"
    for source in _AGENTS:
        fields = _fm((agents_dir / source.name).read_text("utf-8"))
        assert set(fields) == {"name", "description"}, source.stem
        assert "read-only" not in str(fields["description"]).lower(), source.stem


@pytest.mark.parametrize(
    ("description", "expected"),
    [
        ("Read-only test runner — runs tests.", "Test runner — runs tests."),
        (
            "Auditor: checks files. Read-only: never fixes, never runs shell.",
            "Auditor: checks files. Never fixes, never runs shell.",
        ),
        ("Uses Grep plus read-only Bash.", "Uses Grep plus Bash."),
    ],
)
def test_read_only_claim_is_removed_cleanly(description: str, expected: str) -> None:
    from apothem.harnesses._shared.install_driver_converters import (
        _drop_read_only_claim,
    )

    assert _drop_read_only_claim(description) == expected
