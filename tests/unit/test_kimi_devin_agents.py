# SPDX-License-Identifier: MIT

"""Kimi Code and Devin Local subagent renderers write the frontmatter the vendors read.

Kimi Code takes ``.md`` files whose ``tools`` and ``disallowedTools`` are lists of
Kimi tool names (https://moonshotai.github.io/kimi-code/en/customization/agents.md
and .../reference/tools.md, retrieved 2026-10-27); Devin Local takes ``.md`` files
whose ``allowed-tools`` is a list of lowercase Devin tool names
(https://docs.devin.ai/cli/subagents.md, retrieved 2026-10-27). These tests pin,
for every agent in the corpus, the exact frontmatter each renderer writes, and the
rules behind it: the Kimi renames (``WebFetch`` is ``FetchURL``, ``TodoWrite`` is
``TodoList``) and drops, a Kimi grant that loses every name becomes ``tools: []``,
the Devin grant minus its denials, the three web agents Devin is not given, and
the keys neither renderer may write.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path

import pytest
import yaml

from apothem.harnesses._shared.install_driver_agent_emitters import AGENT_EMITTERS
from apothem.harnesses._shared.install_driver_agent_kimi_devin import (
    devin_agent_text,
    devin_allowed_tools,
    kimi_agent_text,
)

_AGENT_DIR = Path(__file__).resolve().parents[2] / "src" / "apothem" / "agents"
_SOURCES = sorted(p for p in _AGENT_DIR.glob("*.md") if p.name != "README.md")

#: stem -> (the exact Kimi ``tools`` list, the exact Kimi ``disallowedTools`` list),
#: in source order. ``WebFetch`` became ``FetchURL`` and ``TodoWrite`` became
#: ``TodoList``; MultiEdit, NotebookEdit, PowerShell, Monitor, Artifact, TaskCreate
#: and TaskUpdate have no Kimi tool and are left out.
_KIMI: dict[str, tuple[list[str], list[str]]] = {
    "citation-auditor": (
        ["Read", "Glob", "Grep", "WebSearch", "FetchURL"],
        ["Write", "Edit", "Bash", "Agent", "TodoList"],
    ),
    "codebase-explorer": (
        ["Read", "Glob", "Grep", "Bash"],
        ["Write", "Edit", "TodoList"],
    ),
    "convention-auditor": (
        ["Read", "Glob", "Grep"],
        ["Write", "Edit", "Bash", "TodoList"],
    ),
    "dependency-auditor": (
        ["Read", "Glob", "Grep", "Bash"],
        ["Write", "Edit", "TodoList"],
    ),
    "design-critic": (["Read", "Glob", "Grep", "Bash"], ["Write", "Edit", "TodoList"]),
    "fact-checker": (
        ["Read", "Glob", "Grep", "WebSearch", "FetchURL"],
        ["Write", "Edit", "TodoList"],
    ),
    "mcp-builder": (["Read", "Write", "Edit", "Glob", "Grep", "Bash"], []),
    "memory-auditor": (["Read", "Glob", "Grep"], ["Write", "Edit", "TodoList"]),
    "prompt-evaluator": (
        ["Read", "Glob", "Grep", "Bash"],
        ["Write", "Edit", "TodoList"],
    ),
    "quality-gate": (["Bash", "Read", "Glob", "Grep"], ["Write", "Edit", "TodoList"]),
    "refactor-surgeon": (["Read", "Write", "Edit", "Glob", "Grep", "Bash"], []),
    "research-scout": (
        ["Read", "Glob", "Grep", "WebSearch", "FetchURL"],
        ["Write", "Edit", "Bash", "Agent", "TodoList"],
    ),
    "security-scanner": (
        ["Read", "Glob", "Grep", "Bash"],
        ["Write", "Edit", "TodoList"],
    ),
    "test-runner": (["Read", "Glob", "Grep", "Bash"], ["Write", "Edit", "TodoList"]),
}

#: stem -> the exact Devin ``allowed-tools`` list the renderer compiles. ``Bash`` is
#: ``exec``; the web tools have no documented Devin name and are left out, which is
#: why the three web agents are held back (see ``_HELD_BACK``).
_DEVIN: dict[str, list[str]] = {
    "citation-auditor": ["read", "glob", "grep"],
    "codebase-explorer": ["read", "glob", "grep", "exec"],
    "convention-auditor": ["read", "glob", "grep"],
    "dependency-auditor": ["read", "glob", "grep", "exec"],
    "design-critic": ["read", "glob", "grep", "exec"],
    "fact-checker": ["read", "glob", "grep"],
    "mcp-builder": ["read", "write", "edit", "glob", "grep", "exec"],
    "memory-auditor": ["read", "glob", "grep"],
    "prompt-evaluator": ["read", "glob", "grep", "exec"],
    "quality-gate": ["exec", "read", "glob", "grep"],
    "refactor-surgeon": ["read", "write", "edit", "glob", "grep", "exec"],
    "research-scout": ["read", "glob", "grep"],
    "security-scanner": ["read", "glob", "grep", "exec"],
    "test-runner": ["read", "glob", "grep", "exec"],
}

#: The agents Devin Local is not given: the ones whose source grant names a web tool.
_HELD_BACK = {"citation-auditor", "fact-checker", "research-scout"}

_KIMI_TOOL_NAMES = {
    "Read",
    "Write",
    "Edit",
    "Grep",
    "Glob",
    "Bash",
    "WebSearch",
    "FetchURL",
    "TodoList",
    "Agent",
}
_DEVIN_TOOL_NAMES = {"read", "edit", "grep", "glob", "exec", "write"}

#: Keys neither vendor file may carry: Apothem metadata, the model, and keys that
#: would change what a project file can replace or dispatch.
_BANNED = (
    "model",
    "override",
    "subagents",
    "whenToUse",
    "max-nesting",
    "maxTurns",
    "version",
    "updated",
    "portability",
)


def _source_parts(path: Path) -> tuple[dict[str, object], str]:
    """Return the source frontmatter and body, read without the renderers."""
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


def _block(key: str, items: list[str]) -> str:
    """Return a YAML block list the way the renderers write it, or nothing."""
    if not items:
        return ""
    return f"{key}:\n" + "".join(f"  - {_quote(item)}\n" for item in items)


def _agent(tmp_path: Path, frontmatter: str) -> Path:
    path = tmp_path / "probe-agent.md"
    path.write_text(f"---\n{frontmatter}---\n\nBody line.\n", encoding="utf-8")
    return path


def test_the_tables_cover_exactly_the_agent_corpus() -> None:
    assert {p.stem for p in _SOURCES} == set(_KIMI) == set(_DEVIN)
    assert len(_SOURCES) == 14
    assert set(_DEVIN) >= _HELD_BACK


def test_the_held_back_agents_are_exactly_those_that_grant_a_web_tool() -> None:
    web = {
        p.stem
        for p in _SOURCES
        if re.search(r"Web(Search|Fetch)", str(_source_parts(p)[0].get("tools", "")))
    }
    assert web == _HELD_BACK


# --- Kimi Code ---------------------------------------------------------------


@pytest.mark.parametrize("source", _SOURCES, ids=lambda p: p.stem)
def test_kimi_frontmatter_is_exact(source: Path) -> None:
    source_fields, _ = _source_parts(source)
    tools, denied = _KIMI[source.stem]
    head, _ = _split(kimi_agent_text(source))
    assert head == (
        "---\n"
        f"name: {_quote(str(source_fields['name']))}\n"
        f"description: {_quote(str(source_fields['description']))}\n"
        f"{_block('tools', tools)}"
        f"{_block('disallowedTools', denied)}"
        "---\n"
    )


@pytest.mark.parametrize("source", _SOURCES, ids=lambda p: p.stem)
def test_kimi_frontmatter_parses_with_only_kimi_tool_names(source: Path) -> None:
    fields = _fields(kimi_agent_text(source))
    assert set(fields) <= {"name", "description", "tools", "disallowedTools"}
    assert fields["name"] == source.stem
    assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", str(fields["name"]))
    assert isinstance(fields["description"], str)
    assert fields["description"]
    tools, denied = _KIMI[source.stem]
    assert fields["tools"] == tools
    assert fields.get("disallowedTools", []) == denied
    for key in ("tools", "disallowedTools"):
        listed = fields.get(key, [])
        assert isinstance(listed, list)
        assert set(listed) <= _KIMI_TOOL_NAMES, (source.stem, key)
    for banned in _BANNED:
        assert banned not in fields, (source.stem, banned)


@pytest.mark.parametrize("source", _SOURCES, ids=lambda p: p.stem)
def test_kimi_never_names_a_claude_code_only_tool(source: Path) -> None:
    """Kimi matches names exactly and warns on one it has no tool for."""
    text = _split(kimi_agent_text(source))[0]
    for claude_only in (
        "WebFetch",
        "TodoWrite",
        "MultiEdit",
        "NotebookEdit",
        "PowerShell",
        "Monitor",
        "Artifact",
        "TaskCreate",
        "TaskUpdate",
    ):
        assert f'"{claude_only}"' not in text, (source.stem, claude_only)


@pytest.mark.parametrize("source", _SOURCES, ids=lambda p: p.stem)
def test_kimi_body_is_the_source_body_and_the_file_has_no_bom_or_cr(
    source: Path,
) -> None:
    text = kimi_agent_text(source)
    _, body = _split(text)
    assert body == "\n" + _source_parts(source)[1] + "\n"
    assert not text.startswith("﻿")
    assert "\r" not in text
    assert text.endswith("\n")
    assert not text.endswith("\n\n")


@pytest.mark.parametrize("source", _SOURCES, ids=lambda p: p.stem)
def test_no_kimi_body_holds_a_template_variable(source: Path) -> None:
    """Kimi renders the body as a ``${var}`` template, so a ``${`` could be filled in."""
    assert "${" not in kimi_agent_text(source)


def test_a_short_kimi_agent_renders_to_this_exact_text(tmp_path: Path) -> None:
    source = _agent(
        tmp_path,
        'name: "probe-agent"\nversion: "0.1.0"\nupdated: "2026-10-27"\n'
        "description: 'Probes the edge: colons, a hash # and commas.'\n"
        'tools: "Read, Bash(git status), mcp__x__*, MultiEdit, TodoWrite, Agent, '
        'Glob, WebFetch, web-search"\n'
        'disallowedTools: "Write, PowerShell, Bash(rm *)"\n'
        'maxTurns: 7\nportability: "universal"\n',
    )
    # A patterned grant has no Kimi form and is left out; a patterned denial
    # denies the whole tool. MultiEdit, PowerShell and the mcp__ entry have no
    # Kimi tool.
    assert kimi_agent_text(source) == (
        '---\nname: "probe-agent"\n'
        'description: "Probes the edge: colons, a hash # and commas."\n'
        "tools:\n"
        '  - "Read"\n  - "TodoList"\n  - "Agent"\n  - "Glob"\n  - "FetchURL"\n'
        '  - "WebSearch"\n'
        'disallowedTools:\n  - "Write"\n  - "Bash"\n'
        "---\n\nBody line.\n"
    )


def test_kimi_names_match_case_and_separators(tmp_path: Path) -> None:
    source = _agent(
        tmp_path,
        'name: "probe-agent"\ndescription: "d"\n'
        'tools: "read, web_fetch, GREP, todo-write"\n',
    )
    assert _fields(kimi_agent_text(source))["tools"] == [
        "Read",
        "FetchURL",
        "Grep",
        "TodoList",
    ]


def test_a_kimi_grant_with_no_kimi_tool_becomes_an_empty_list_not_a_missing_key(
    tmp_path: Path,
) -> None:
    """An omitted ``tools`` allows every Kimi tool; ``[]`` allows none."""
    source = _agent(
        tmp_path,
        'name: "probe-agent"\ndescription: "d"\ntools: "Monitor, mcp__x__tool"\n',
    )
    assert "\ntools: []\n" in kimi_agent_text(source)
    assert _fields(kimi_agent_text(source))["tools"] == []


def test_a_kimi_source_with_denials_and_no_grant_keeps_tools_out(
    tmp_path: Path,
) -> None:
    source = _agent(
        tmp_path,
        'name: "probe-agent"\ndescription: "d"\n'
        'disallowedTools: "Write, Edit, MultiEdit, Monitor"\n',
    )
    fields = _fields(kimi_agent_text(source))
    assert "tools" not in fields
    assert fields["disallowedTools"] == ["Write", "Edit"]


def test_a_kimi_source_that_restricts_nothing_writes_no_tool_key(
    tmp_path: Path,
) -> None:
    source = _agent(tmp_path, 'name: "probe-agent"\ndescription: "d"\n')
    fields = _fields(kimi_agent_text(source))
    assert set(fields) == {"name", "description"}


def test_an_empty_kimi_deny_list_is_left_out(tmp_path: Path) -> None:
    source = _agent(
        tmp_path,
        'name: "probe-agent"\ndescription: "d"\ntools: "Read"\ndisallowedTools: ""\n',
    )
    assert "disallowedTools" not in _fields(kimi_agent_text(source))


def test_the_kimi_name_falls_back_to_the_file_stem(tmp_path: Path) -> None:
    source = _agent(tmp_path, 'description: "d"\ntools: "Read"\n')
    assert 'name: "probe-agent"\n' in kimi_agent_text(source)


# --- Devin Local -------------------------------------------------------------


@pytest.mark.parametrize("source", _SOURCES, ids=lambda p: p.stem)
def test_devin_frontmatter_is_exact(source: Path) -> None:
    source_fields, _ = _source_parts(source)
    head, _ = _split(devin_agent_text(source))
    assert head == (
        "---\n"
        f"name: {_quote(str(source_fields['name']))}\n"
        f"description: {_quote(str(source_fields['description']))}\n"
        f"{_block('allowed-tools', _DEVIN[source.stem])}"
        "---\n"
    )


@pytest.mark.parametrize("source", _SOURCES, ids=lambda p: p.stem)
def test_devin_frontmatter_parses_with_lowercase_documented_tool_names(
    source: Path,
) -> None:
    fields = _fields(devin_agent_text(source))
    assert set(fields) == {"name", "description", "allowed-tools"}
    assert fields["name"] == source.stem
    assert isinstance(fields["description"], str)
    assert fields["description"]
    tools = fields["allowed-tools"]
    assert tools == _DEVIN[source.stem]
    assert isinstance(tools, list)
    assert set(tools) <= _DEVIN_TOOL_NAMES
    for banned in (*_BANNED, "tools", "disallowedTools"):
        assert banned not in fields, (source.stem, banned)


@pytest.mark.parametrize("source", _SOURCES, ids=lambda p: p.stem)
def test_devin_never_hands_a_read_only_agent_a_writing_tool(source: Path) -> None:
    source_fields, _ = _source_parts(source)
    denied = {t.strip() for t in str(source_fields["disallowedTools"]).split(",")}
    tools = devin_allowed_tools(source)
    assert tools is not None
    if "Write" in denied:
        assert "write" not in tools
    if "Edit" in denied:
        assert "edit" not in tools
    if "Bash" in denied:
        assert "exec" not in tools


@pytest.mark.parametrize("source", _SOURCES, ids=lambda p: p.stem)
def test_devin_body_is_the_source_body_and_the_file_has_no_bom_or_cr(
    source: Path,
) -> None:
    text = devin_agent_text(source)
    _, body = _split(text)
    assert body == "\n" + _source_parts(source)[1] + "\n"
    assert not text.startswith("﻿")
    assert "\r" not in text
    assert text.endswith("\n")
    assert not text.endswith("\n\n")


def test_a_short_devin_agent_renders_to_this_exact_text(tmp_path: Path) -> None:
    source = _agent(
        tmp_path,
        'name: "probe-agent"\nversion: "0.1.0"\nupdated: "2026-10-27"\n'
        "description: 'Probes the edge: colons, a hash # and commas.'\n"
        'tools: "Read, Bash(git status), mcp__x__*, MultiEdit, WebFetch, Write, '
        'Glob, Bash"\n'
        'disallowedTools: "Write, PowerShell"\n'
        'maxTurns: 7\nportability: "universal"\n',
    )
    # Write is denied, so it leaves the allowlist (Devin has no deny key); the
    # patterned Bash grant has no Devin form; the web and mcp__ entries have no
    # documented allowed-tools name.
    assert devin_agent_text(source) == (
        '---\nname: "probe-agent"\n'
        'description: "Probes the edge: colons, a hash # and commas."\n'
        'allowed-tools:\n  - "read"\n  - "glob"\n  - "exec"\n'
        "---\n\nBody line.\n"
    )


def test_a_patterned_devin_denial_denies_the_whole_tool(tmp_path: Path) -> None:
    source = _agent(
        tmp_path,
        'name: "probe-agent"\ndescription: "d"\ntools: "Read, Bash"\n'
        'disallowedTools: "Bash(rm *)"\n',
    )
    assert devin_allowed_tools(source) == ["read"]


def test_devin_names_match_case_and_separators(tmp_path: Path) -> None:
    source = _agent(
        tmp_path,
        'name: "probe-agent"\ndescription: "d"\ntools: "READ, Grep, Bash, g-lob, edit"\n',
    )
    assert devin_allowed_tools(source) == ["read", "grep", "exec", "glob", "edit"]


def test_a_devin_source_with_denials_and_no_grant_gets_the_allowlist_they_imply(
    tmp_path: Path,
) -> None:
    source = _agent(
        tmp_path,
        'name: "probe-agent"\ndescription: "d"\n'
        'disallowedTools: "Write, Bash, TodoWrite, Monitor"\n',
    )
    assert devin_allowed_tools(source) == ["read", "edit", "grep", "glob"]
    assert 'allowed-tools:\n  - "read"\n  - "edit"\n' in devin_agent_text(source)


def test_a_devin_denial_of_only_the_shell_keeps_every_other_documented_name(
    tmp_path: Path,
) -> None:
    """``write`` is a documented name (CLI changelog v3000.11.1), so it stays."""
    source = _agent(
        tmp_path, 'name: "probe-agent"\ndescription: "d"\ndisallowedTools: "Bash"\n'
    )
    assert devin_allowed_tools(source) == ["read", "edit", "grep", "glob", "write"]


def test_a_devin_source_that_restricts_nothing_leaves_allowed_tools_out(
    tmp_path: Path,
) -> None:
    source = _agent(tmp_path, 'name: "probe-agent"\ndescription: "d"\n')
    assert devin_allowed_tools(source) is None
    assert set(_fields(devin_agent_text(source))) == {"name", "description"}


def test_an_empty_devin_deny_list_alone_leaves_allowed_tools_out(
    tmp_path: Path,
) -> None:
    source = _agent(
        tmp_path, 'name: "probe-agent"\ndescription: "d"\ndisallowedTools: ""\n'
    )
    assert devin_allowed_tools(source) is None


def test_a_devin_grant_with_no_devin_name_becomes_an_empty_list(
    tmp_path: Path,
) -> None:
    """The grant is never dropped: the key stays so the agent is not given every tool."""
    source = _agent(
        tmp_path,
        'name: "probe-agent"\ndescription: "d"\ntools: "WebFetch, mcp__x__tool"\n',
    )
    assert "\nallowed-tools: []\n" in devin_agent_text(source)
    assert _fields(devin_agent_text(source))["allowed-tools"] == []


def test_a_devin_denial_that_removes_every_granted_tool_gives_an_empty_list(
    tmp_path: Path,
) -> None:
    source = _agent(
        tmp_path,
        'name: "probe-agent"\ndescription: "d"\ntools: "Write"\n'
        'disallowedTools: "Write"\n',
    )
    assert "\nallowed-tools: []\n" in devin_agent_text(source)


def test_the_devin_name_falls_back_to_the_file_stem(tmp_path: Path) -> None:
    source = _agent(tmp_path, 'description: "d"\ntools: "Read"\n')
    assert 'name: "probe-agent"\n' in devin_agent_text(source)


# --- Registry ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("mode", "render", "held_back"),
    [
        ("kimi_agents", kimi_agent_text, frozenset()),
        ("devin_agents", devin_agent_text, frozenset(_HELD_BACK)),
    ],
)
def test_the_registry_rows_pair_each_mode_with_its_renderer(
    mode: str, render: Callable[[Path], str], held_back: frozenset[str]
) -> None:
    row = AGENT_EMITTERS[mode]
    assert row.renderer is render
    assert row.target_extension is None
    assert row.exclude == held_back
    assert row.remove_stale_markdown is False
    assert row.target_name(Path("agents/code-reviewer.md")) == "code-reviewer.md"
