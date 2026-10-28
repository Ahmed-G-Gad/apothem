# SPDX-License-Identifier: MIT

"""The Kiro subagent renderer writes the frontmatter Kiro reads.

Kiro reads a custom agent from ``.kiro/agents/<name>.md``: Markdown with YAML
frontmatter, the body being the system prompt (IDE 1.0 and CLI V3,
https://kiro.dev/docs/custom-agents/ and .../configuration-reference/, retrieved
2026-10-27). ``tools`` is a list of category tags (``read``, ``write``, ``shell``,
``web``, ``subagent``). These tests pin, for every agent in the corpus, the exact
frontmatter the renderer writes and the rules behind it: the source grant mapped
to tags, a tag left out when the source denies any tool it covers, a grant that
loses every tag written as ``tools: []``, the keys the renderer must never write,
and that the engine emits no JSON profile and no CLI 2.x ``allowedTools``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from apothem.harnesses._shared.install_driver_agent_emitters import AGENT_EMITTERS
from apothem.harnesses._shared.install_driver_agent_kiro import (
    kiro_agent_text,
    kiro_tool_tags,
)

_AGENT_DIR = Path(__file__).resolve().parents[2] / "src" / "apothem" / "agents"
_SOURCES = sorted(p for p in _AGENT_DIR.glob("*.md") if p.name != "README.md")

#: stem -> the exact Kiro ``tools`` list, in source-grant order. ``Read``, ``Glob``
#: and ``Grep`` are ``read``; ``Write`` and ``Edit`` are ``write``; ``Bash`` is
#: ``shell``; ``WebSearch`` and ``WebFetch`` are ``web``. The grants never name a
#: tag the source denies, and ``quality-gate`` lists ``Bash`` first.
_TOOLS: dict[str, list[str]] = {
    "citation-auditor": ["read", "web"],
    "codebase-explorer": ["read", "shell"],
    "convention-auditor": ["read"],
    "dependency-auditor": ["read", "shell"],
    "design-critic": ["read", "shell"],
    "fact-checker": ["read", "web"],
    "mcp-builder": ["read", "write", "shell"],
    "memory-auditor": ["read"],
    "prompt-evaluator": ["read", "shell"],
    "quality-gate": ["shell", "read"],
    "refactor-surgeon": ["read", "write", "shell"],
    "research-scout": ["read", "web"],
    "security-scanner": ["read", "shell"],
    "test-runner": ["read", "shell"],
}

_TAGS = {"read", "write", "shell", "web", "subagent"}

#: Keys the Kiro file may not carry: the model (an id Kiro's model service does not
#: know can fail the first prompt), the authorization and resource keys the install
#: does not own, the CLI 2.x profile keys V3 skips, and Apothem's metadata.
_BANNED = (
    "model",
    "permissions",
    "excludedTools",
    "resources",
    "mcpServers",
    "hooks",
    "prompt",
    "includeMcpJson",
    "includePowers",
    "welcomeMessage",
    "allowedTools",
    "toolsSettings",
    "disallowedTools",
    "maxTurns",
    "version",
    "updated",
    "portability",
)


def _source_parts(path: Path) -> tuple[dict[str, object], str]:
    """Return the source frontmatter and body, read without the renderer."""
    text = path.read_text(encoding="utf-8")
    end = text.index("\n---\n", 4)
    loaded = yaml.safe_load(text[4:end])
    assert isinstance(loaded, dict)
    return loaded, text[end + 5 :].strip()


def _split(text: str) -> tuple[str, str]:
    """Return the frontmatter block (with its fences) and the body of *text*."""
    end = text.index("\n---\n", 4) + 5
    return text[:end], text[end:]


def _fields(text: str) -> dict[str, object]:
    head, _ = _split(text)
    loaded = yaml.safe_load(head[4 : head.index("\n---\n", 4)])
    assert isinstance(loaded, dict)
    return loaded


def _quote(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _agent(tmp_path: Path, frontmatter: str) -> Path:
    path = tmp_path / "probe-agent.md"
    path.write_text(f"---\n{frontmatter}---\n\nBody line.\n", encoding="utf-8")
    return path


def test_the_table_covers_exactly_the_agent_corpus() -> None:
    assert {p.stem for p in _SOURCES} == set(_TOOLS)
    assert len(_SOURCES) == 14


def test_the_kiro_row_holds_back_no_agent_and_keeps_the_source_file_name() -> None:
    row = AGENT_EMITTERS["kiro_agents"]
    assert row.renderer is kiro_agent_text
    assert row.exclude == frozenset()
    assert row.target_extension is None
    assert row.remove_stale_markdown is False
    assert row.target_name(Path("quality-gate.md")) == "quality-gate.md"


@pytest.mark.parametrize("source", _SOURCES, ids=lambda p: p.stem)
def test_frontmatter_is_exact(source: Path) -> None:
    source_fields, _ = _source_parts(source)
    head, _ = _split(kiro_agent_text(source))
    assert head == (
        "---\n"
        f"name: {_quote(str(source_fields['name']))}\n"
        f"description: {_quote(str(source_fields['description']))}\n"
        f"tools: {json.dumps(_TOOLS[source.stem])}\n"
        "---\n"
    )


@pytest.mark.parametrize("source", _SOURCES, ids=lambda p: p.stem)
def test_frontmatter_parses_with_only_kiro_keys_and_tags(source: Path) -> None:
    fields = _fields(kiro_agent_text(source))
    assert set(fields) == {"name", "description", "tools"}
    assert fields["name"] == source.stem
    assert isinstance(fields["description"], str)
    assert fields["description"]
    assert fields["tools"] == _TOOLS[source.stem]
    assert set(_TOOLS[source.stem]) <= _TAGS
    for banned in _BANNED:
        assert banned not in fields, (source.stem, banned)


@pytest.mark.parametrize("source", _SOURCES, ids=lambda p: p.stem)
def test_the_description_is_the_source_description(source: Path) -> None:
    """Kiro's main agent picks a subagent from its description, so it is kept whole."""
    source_fields, _ = _source_parts(source)
    assert (
        _fields(kiro_agent_text(source))["description"]
        == (source_fields["description"])
    )


@pytest.mark.parametrize("source", _SOURCES, ids=lambda p: p.stem)
def test_a_denied_tool_never_reaches_the_allowlist(source: Path) -> None:
    """No tag in ``tools`` covers a tool the source denies."""
    source_fields, _ = _source_parts(source)
    denied = {
        item.strip().lower()
        for item in str(source_fields["disallowedTools"]).split(",")
    }
    tags = _fields(kiro_agent_text(source))["tools"]
    assert isinstance(tags, list)
    if {"write", "edit"} & denied:
        assert "write" not in tags, source.stem
    if "bash" in denied:
        assert "shell" not in tags, source.stem
    if "agent" in denied:
        assert "subagent" not in tags, source.stem


@pytest.mark.parametrize("source", _SOURCES, ids=lambda p: p.stem)
def test_body_is_the_source_body_and_the_file_has_no_bom_or_cr(source: Path) -> None:
    text = kiro_agent_text(source)
    _, body = _split(text)
    assert body == "\n" + _source_parts(source)[1] + "\n"
    assert not text.startswith("﻿")
    assert "\r" not in text
    assert text.endswith("\n")
    assert not text.endswith("\n\n")


@pytest.mark.parametrize("source", _SOURCES, ids=lambda p: p.stem)
def test_the_file_is_markdown_with_no_cli_2x_profile_keys(source: Path) -> None:
    """V3 skips a profile that carries ``allowedTools`` without ``permissions``."""
    text = kiro_agent_text(source)
    assert text.startswith("---\nname: ")
    assert "allowedTools" not in text.split("\n---\n", 1)[0]
    assert not text.lstrip().startswith("{")
    row = AGENT_EMITTERS["kiro_agents"]
    assert row.target_name(source) == source.name
    assert source.name.endswith(".md")


def test_a_short_agent_renders_to_this_exact_text(tmp_path: Path) -> None:
    source = _agent(
        tmp_path,
        'name: "probe-agent"\nversion: "0.1.0"\nupdated: "2026-10-27"\n'
        "description: 'Probes the edge: colons, a hash # and commas.'\n"
        'tools: "Read, Bash(git status), mcp__x__*, MultiEdit, TodoWrite, Agent, '
        'Glob, WebFetch, web-search"\n'
        'disallowedTools: "Write, PowerShell, Bash(rm *)"\n'
        'maxTurns: 7\nportability: "universal"\n',
    )
    # A patterned grant has no tag form and is left out; MultiEdit is a write tool
    # the source also denies through Write, so the write tag is dropped; the
    # PowerShell and patterned Bash denials drop the shell tag; TodoWrite and the
    # mcp__ entry have no Kiro tag.
    assert kiro_agent_text(source) == (
        '---\nname: "probe-agent"\n'
        'description: "Probes the edge: colons, a hash # and commas."\n'
        'tools: ["read", "subagent", "web"]\n'
        "---\n\nBody line.\n"
    )


def test_names_match_case_and_separators(tmp_path: Path) -> None:
    source = _agent(
        tmp_path,
        'name: "probe-agent"\ndescription: "d"\n'
        'tools: "read, web_fetch, GREP, Notebook-Edit"\n',
    )
    assert _fields(kiro_agent_text(source))["tools"] == ["read", "web", "write"]


def test_a_denied_tool_drops_the_whole_tag(tmp_path: Path) -> None:
    """``write`` also covers Edit, so denying Edit must not leave Write granted."""
    source = _agent(
        tmp_path,
        'name: "probe-agent"\ndescription: "d"\n'
        'tools: "Read, Write"\ndisallowedTools: "Edit"\n',
    )
    assert kiro_tool_tags(source) == ["read"]


@pytest.mark.parametrize(
    ("granted", "denied"),
    [
        ("Read, Write", "MultiEdit"),
        ("Read, Bash", "PowerShell"),
        ("Read, Agent", "Task"),
    ],
)
def test_a_denial_of_a_tool_the_tag_covers_drops_the_tag_by_itself(
    tmp_path: Path, granted: str, denied: str
) -> None:
    """MultiEdit, PowerShell and Task have no grant form in the corpus, only denials."""
    source = _agent(
        tmp_path,
        f'name: "probe-agent"\ndescription: "d"\ntools: "{granted}"\n'
        f'disallowedTools: "{denied}"\n',
    )
    assert kiro_tool_tags(source) == ["read"]


def test_a_grant_that_loses_every_tag_is_an_empty_list_not_a_missing_key(
    tmp_path: Path,
) -> None:
    """The source grant is never widened to every tool."""
    source = _agent(
        tmp_path,
        'name: "probe-agent"\ndescription: "d"\ntools: "Monitor, mcp__x__tool"\n',
    )
    assert "\ntools: []\n" in kiro_agent_text(source)
    assert _fields(kiro_agent_text(source))["tools"] == []


def test_a_grant_denied_in_full_is_an_empty_list(tmp_path: Path) -> None:
    source = _agent(
        tmp_path,
        'name: "probe-agent"\ndescription: "d"\n'
        'tools: "Read, Glob"\ndisallowedTools: "Read"\n',
    )
    assert _fields(kiro_agent_text(source))["tools"] == []


def test_a_source_with_denials_and_no_grant_gets_the_remaining_tags(
    tmp_path: Path,
) -> None:
    source = _agent(
        tmp_path,
        'name: "probe-agent"\ndescription: "d"\n'
        'disallowedTools: "Write, Edit, MultiEdit, Monitor"\n',
    )
    assert _fields(kiro_agent_text(source))["tools"] == [
        "read",
        "shell",
        "web",
        "subagent",
    ]


def test_a_source_that_restricts_nothing_writes_no_tool_key(tmp_path: Path) -> None:
    source = _agent(tmp_path, 'name: "probe-agent"\ndescription: "d"\n')
    assert kiro_tool_tags(source) is None
    assert set(_fields(kiro_agent_text(source))) == {"name", "description"}


def test_a_repeated_tag_is_written_once_in_first_appearance_order(
    tmp_path: Path,
) -> None:
    source = _agent(
        tmp_path,
        'name: "probe-agent"\ndescription: "d"\ntools: "Bash, Read, Grep, PowerShell"\n',
    )
    assert _fields(kiro_agent_text(source))["tools"] == ["shell", "read"]
