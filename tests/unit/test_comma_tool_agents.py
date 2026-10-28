# SPDX-License-Identifier: MIT

"""CodeBuddy and Trae subagent renderers write the frontmatter the vendors read.

Both vendors take a Markdown agent file whose ``tools`` and ``disallowedTools``
are comma-separated strings (CodeBuddy: https://www.codebuddy.ai/docs/cli/sub-agents;
Trae: https://docs.trae.ai/ide/subagents; both retrieved 2026-10-27). These tests
pin, for every agent in the corpus, the exact frontmatter each renderer writes,
and the rules behind it: a tool name outside the vendor's vocabulary is left out,
a grant is never widened, only CodeBuddy keeps ``maxTurns``, and neither writes
``model`` or Apothem's own metadata keys.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path

import pytest
import yaml

from apothem.harnesses._shared.install_driver_agent_comma_tools import (
    codebuddy_agent_text,
    trae_agent_text,
)
from apothem.harnesses._shared.install_driver_agent_emitters import AGENT_EMITTERS

_AGENT_DIR = Path(__file__).resolve().parents[2] / "src" / "apothem" / "agents"
_SOURCES = sorted(p for p in _AGENT_DIR.glob("*.md") if p.name != "README.md")

_TOOLS_READ = "Read, Glob, Grep"
_TOOLS_SEARCH = "Read, Glob, Grep, WebSearch, WebFetch"
_TOOLS_SHELL = "Read, Glob, Grep, Bash"
_TOOLS_EDIT = "Read, Write, Edit, Glob, Grep, Bash"

#: CodeBuddy names the task tools and MultiEdit / NotebookEdit on its Settings
#: page (https://www.codebuddy.ai/docs/cli/settings, retrieved 2026-10-28), so a
#: source denial of one of them is carried; Trae names none of them.
_CB_DENY_READ_ONLY = "Write, Edit, TaskCreate, TaskUpdate"
_CB_DENY_NO_SHELL = "Write, Edit, Bash, TaskCreate, TaskUpdate"
_CB_DENY_WEB_ONLY = (
    "Write, Edit, MultiEdit, NotebookEdit, Bash, Agent, TaskCreate, TaskUpdate"
)

#: stem -> (CodeBuddy tools, CodeBuddy disallowedTools, Trae tools, Trae
#: disallowedTools, maxTurns). The source denies Write and Edit on every agent
#: that cannot author files, plus the tools the vendor names or not.
_EXPECTED: dict[str, tuple[str, str | None, str, str | None, int]] = {
    "citation-auditor": (
        _TOOLS_SEARCH,
        _CB_DENY_WEB_ONLY,
        _TOOLS_SEARCH,
        "Write, Edit, Bash, TodoWrite",
        20,
    ),
    "codebase-explorer": (
        _TOOLS_SHELL,
        _CB_DENY_READ_ONLY,
        _TOOLS_SHELL,
        "Write, Edit, TodoWrite",
        20,
    ),
    "convention-auditor": (
        _TOOLS_READ,
        _CB_DENY_NO_SHELL,
        _TOOLS_READ,
        "Write, Edit, Bash, TodoWrite",
        15,
    ),
    "dependency-auditor": (
        _TOOLS_SHELL,
        _CB_DENY_READ_ONLY,
        _TOOLS_SHELL,
        "Write, Edit, TodoWrite",
        15,
    ),
    "design-critic": (
        _TOOLS_SHELL,
        _CB_DENY_READ_ONLY,
        _TOOLS_SHELL,
        "Write, Edit, TodoWrite",
        15,
    ),
    "fact-checker": (
        _TOOLS_SEARCH,
        _CB_DENY_READ_ONLY,
        _TOOLS_SEARCH,
        "Write, Edit, TodoWrite",
        15,
    ),
    "mcp-builder": (_TOOLS_EDIT, None, _TOOLS_EDIT, None, 20),
    "memory-auditor": (
        _TOOLS_READ,
        _CB_DENY_READ_ONLY,
        _TOOLS_READ,
        "Write, Edit, TodoWrite",
        15,
    ),
    "prompt-evaluator": (
        _TOOLS_SHELL,
        _CB_DENY_READ_ONLY,
        _TOOLS_SHELL,
        "Write, Edit, TodoWrite",
        15,
    ),
    "quality-gate": (
        "Bash, Read, Glob, Grep",
        _CB_DENY_READ_ONLY,
        "Bash, Read, Glob, Grep",
        "Write, Edit, TodoWrite",
        15,
    ),
    "refactor-surgeon": (_TOOLS_EDIT, None, _TOOLS_EDIT, None, 20),
    "research-scout": (
        _TOOLS_SEARCH,
        _CB_DENY_WEB_ONLY,
        _TOOLS_SEARCH,
        "Write, Edit, Bash, TodoWrite",
        15,
    ),
    "security-scanner": (
        _TOOLS_SHELL,
        _CB_DENY_READ_ONLY,
        _TOOLS_SHELL,
        "Write, Edit, TodoWrite",
        20,
    ),
    "test-runner": (
        _TOOLS_SHELL,
        _CB_DENY_READ_ONLY,
        _TOOLS_SHELL,
        "Write, Edit, TodoWrite",
        15,
    ),
}


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


def _quote(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _expected_frontmatter(
    path: Path, *, tools: str, denied: str | None, max_turns: int | None
) -> str:
    fields, _ = _source_parts(path)
    lines = [
        "---",
        f"name: {_quote(str(fields['name']))}",
        f"description: {_quote(str(fields['description']))}",
        f"tools: {_quote(tools)}",
    ]
    if denied is not None:
        lines.append(f"disallowedTools: {_quote(denied)}")
    if max_turns is not None:
        lines.append(f"maxTurns: {max_turns}")
    lines.append("---\n")
    return "\n".join(lines)


def test_the_table_covers_exactly_the_agent_corpus() -> None:
    assert {p.stem for p in _SOURCES} == set(_EXPECTED)
    assert len(_SOURCES) == 14


@pytest.mark.parametrize("source", _SOURCES, ids=lambda p: p.stem)
def test_codebuddy_frontmatter_is_exact(source: Path) -> None:
    tools, denied, _, _, turns = _EXPECTED[source.stem]
    head, _ = _split(codebuddy_agent_text(source))
    assert head == _expected_frontmatter(
        source, tools=tools, denied=denied, max_turns=turns
    )


@pytest.mark.parametrize("source", _SOURCES, ids=lambda p: p.stem)
def test_trae_frontmatter_is_exact(source: Path) -> None:
    _, _, tools, denied, _ = _EXPECTED[source.stem]
    head, _ = _split(trae_agent_text(source))
    assert head == _expected_frontmatter(
        source, tools=tools, denied=denied, max_turns=None
    )


@pytest.mark.parametrize("render", [codebuddy_agent_text, trae_agent_text])
@pytest.mark.parametrize("source", _SOURCES, ids=lambda p: p.stem)
def test_body_is_the_source_body_and_the_file_has_no_bom_or_cr(
    source: Path, render: Callable[[Path], str]
) -> None:
    text = render(source)
    _, body = _split(text)
    assert body == "\n" + _source_parts(source)[1] + "\n"
    assert not text.startswith("﻿")
    assert "\r" not in text
    assert text.endswith("\n")
    assert not text.endswith("\n\n")


@pytest.mark.parametrize("render", [codebuddy_agent_text, trae_agent_text])
@pytest.mark.parametrize("source", _SOURCES, ids=lambda p: p.stem)
def test_frontmatter_parses_as_yaml_with_string_tool_fields(
    source: Path, render: Callable[[Path], str]
) -> None:
    head, _ = _split(render(source))
    fields = yaml.safe_load(head[4 : head.index("\n---\n", 4)])
    assert fields["name"] == source.stem
    assert isinstance(fields["description"], str)
    assert fields["description"]
    for key in ("tools", "disallowedTools"):
        if key in fields:
            assert isinstance(fields[key], str), f"{key} must be a comma string"
    for banned in ("model", "version", "updated", "portability", "mcpServers", "hooks"):
        assert banned not in fields, banned


def test_only_codebuddy_keeps_the_turn_limit() -> None:
    for source in _SOURCES:
        cb, _ = _split(codebuddy_agent_text(source))
        trae, _ = _split(trae_agent_text(source))
        assert re.search(r"^maxTurns: \d+$", cb, re.MULTILINE), source.stem
        assert "maxTurns" not in trae, source.stem


def test_codebuddy_names_follow_its_lowercase_hyphen_rule() -> None:
    for source in _SOURCES:
        head, _ = _split(codebuddy_agent_text(source))
        name = yaml.safe_load(head[4 : head.index("\n---\n", 4)])["name"]
        assert re.fullmatch(r"[a-z]+(-[a-z]+)*", name), name


def test_trae_names_follow_its_documented_rule() -> None:
    """Letter first, letters, digits and hyphens, ends alphanumeric, at most 50."""
    for source in _SOURCES:
        head, _ = _split(trae_agent_text(source))
        name = yaml.safe_load(head[4 : head.index("\n---\n", 4)])["name"]
        assert re.fullmatch(r"[A-Za-z]([A-Za-z0-9-]*[A-Za-z0-9])?", name), name
        assert len(name) <= 50, name


def _tool_set(head: str, key: str) -> set[str]:
    fields = yaml.safe_load(head[4 : head.index("\n---\n", 4)])
    return {t.strip() for t in str(fields.get(key, "")).split(",") if t.strip()}


@pytest.mark.parametrize("render", [codebuddy_agent_text, trae_agent_text])
@pytest.mark.parametrize("source", _SOURCES, ids=lambda p: p.stem)
def test_an_agent_that_cannot_author_files_still_cannot(
    source: Path, render: Callable[[Path], str]
) -> None:
    """Native enforcement matches the source: no Write or Edit left to the agent."""
    fields, _ = _source_parts(source)
    granted = {t.strip() for t in str(fields["tools"]).split(",")}
    denied = {t.strip() for t in str(fields.get("disallowedTools", "")).split(",")}
    source_can_write = bool((granted - denied) & {"Write", "Edit"})
    head, _ = _split(render(source))
    effective = _tool_set(head, "tools") - _tool_set(head, "disallowedTools")
    assert bool(effective & {"Write", "Edit"}) is source_can_write


def _agent(tmp_path: Path, frontmatter: str) -> Path:
    path = tmp_path / "probe-agent.md"
    path.write_text(f"---\n{frontmatter}---\n\nBody line.\n", encoding="utf-8")
    return path


def test_a_short_agent_renders_to_this_exact_text(tmp_path: Path) -> None:
    source = _agent(
        tmp_path,
        'name: "probe-agent"\nversion: "0.1.0"\nupdated: "2026-10-27"\n'
        "description: 'Probes the edge: colons, a hash # and commas.'\n"
        'tools: "Read, Bash(git status), mcp__x__*, MultiEdit, TodoWrite, Agent"\n'
        'disallowedTools: "Write, NotebookEdit, PowerShell"\n'
        'maxTurns: 7\nportability: "universal"\n',
    )
    assert codebuddy_agent_text(source) == (
        '---\nname: "probe-agent"\n'
        'description: "Probes the edge: colons, a hash # and commas."\n'
        'tools: "Read, MultiEdit, Agent"\n'
        'disallowedTools: "Write, NotebookEdit"\nmaxTurns: 7\n---\n\n'
        "Body line.\n"
    )
    assert trae_agent_text(source) == (
        '---\nname: "probe-agent"\n'
        'description: "Probes the edge: colons, a hash # and commas."\n'
        'tools: "Read, TodoWrite"\ndisallowedTools: "Write"\n---\n\nBody line.\n'
    )


def test_tool_names_match_case_and_separators_but_keep_the_vendor_spelling(
    tmp_path: Path,
) -> None:
    source = _agent(
        tmp_path,
        'name: "probe-agent"\ndescription: "d"\n'
        'tools: "read, web-fetch, web_search, GREP"\n',
    )
    assert 'tools: "Read, WebFetch, WebSearch, Grep"\n' in codebuddy_agent_text(source)
    assert 'tools: "Read, WebFetch, WebSearch, Grep"\n' in trae_agent_text(source)


def test_a_source_without_a_grant_writes_no_tools_line(tmp_path: Path) -> None:
    source = _agent(
        tmp_path, 'name: "probe-agent"\ndescription: "d"\ndisallowedTools: "Write"\n'
    )
    for render in (codebuddy_agent_text, trae_agent_text):
        head, _ = _split(render(source))
        assert "tools:" not in head.replace("disallowedTools:", "")
        assert 'disallowedTools: "Write"' in head


def test_a_grant_with_no_usable_name_is_never_widened(tmp_path: Path) -> None:
    """Dropping the key would let the agent inherit every tool; an empty string does not."""
    source = _agent(
        tmp_path,
        'name: "probe-agent"\ndescription: "d"\ntools: "PowerShell, Monitor"\n',
    )
    for render in (codebuddy_agent_text, trae_agent_text):
        head, _ = _split(render(source))
        assert '\ntools: ""\n' in head


def test_an_empty_deny_list_and_a_missing_turn_limit_write_nothing(
    tmp_path: Path,
) -> None:
    source = _agent(
        tmp_path,
        'name: "probe-agent"\ndescription: "d"\ntools: "Read"\ndisallowedTools: ""\n'
        'maxTurns: "many"\n',
    )
    for render in (codebuddy_agent_text, trae_agent_text):
        head, _ = _split(render(source))
        assert "disallowedTools" not in head
        assert "maxTurns" not in head


def test_the_name_falls_back_to_the_file_stem(tmp_path: Path) -> None:
    source = _agent(tmp_path, 'description: "d"\ntools: "Read"\n')
    assert 'name: "probe-agent"\n' in codebuddy_agent_text(source)
    assert 'name: "probe-agent"\n' in trae_agent_text(source)


def test_the_registry_rows_pair_each_mode_with_its_renderer() -> None:
    assert AGENT_EMITTERS["codebuddy_agents"].renderer is codebuddy_agent_text
    assert AGENT_EMITTERS["trae_agents"].renderer is trae_agent_text
    for mode in ("codebuddy_agents", "trae_agents"):
        row = AGENT_EMITTERS[mode]
        assert row.target_extension is None
        assert row.exclude == frozenset()
        assert row.remove_stale_markdown is False


def test_a_patterned_denial_denies_the_whole_tool(tmp_path: Path) -> None:
    """``Bash(rm *)`` has no form in a comma list, so it must not vanish."""
    source = _agent(
        tmp_path,
        'name: "probe-agent"\ndescription: "d"\ntools: "Read, Glob, Grep, Bash"\n'
        'disallowedTools: "Bash(rm *), Write, Edit"\n',
    )
    for render in (codebuddy_agent_text, trae_agent_text):
        head, _ = _split(render(source))
        assert _tool_set(head, "disallowedTools") == {"Bash", "Write", "Edit"}
        effective = _tool_set(head, "tools") - _tool_set(head, "disallowedTools")
        assert "Bash" not in effective


def test_a_patterned_grant_is_left_out_not_widened(tmp_path: Path) -> None:
    source = _agent(
        tmp_path,
        'name: "probe-agent"\ndescription: "d"\ntools: "Read, Bash(git status)"\n',
    )
    for render in (codebuddy_agent_text, trae_agent_text):
        head, _ = _split(render(source))
        assert 'tools: "Read"\n' in head


def test_a_grant_of_only_a_patterned_tool_is_an_empty_string(tmp_path: Path) -> None:
    source = _agent(
        tmp_path,
        'name: "probe-agent"\ndescription: "d"\ntools: "Bash(git status)"\n',
    )
    for render in (codebuddy_agent_text, trae_agent_text):
        head, _ = _split(render(source))
        assert '\ntools: ""\n' in head


@pytest.mark.parametrize(
    "tool", ["MultiEdit", "NotebookEdit", "Task", "TaskCreate", "TaskUpdate"]
)
def test_codebuddy_carries_the_denials_its_settings_page_names(
    tmp_path: Path, tool: str
) -> None:
    """Each is in CodeBuddy's "Tools Available to CodeBuddy" table: it stays denied."""
    source = _agent(
        tmp_path,
        f'name: "probe-agent"\ndescription: "d"\ndisallowedTools: "{tool}"\n',
    )
    assert f'disallowedTools: "{tool}"\n' in codebuddy_agent_text(source)
    assert "disallowedTools" not in trae_agent_text(source)


@pytest.mark.parametrize("tool", ["Skill", "LSP"])
def test_trae_keeps_a_grant_of_each_tool_its_page_lists(
    tmp_path: Path, tool: str
) -> None:
    """Skill and LSP are in Trae's subagent vocabulary but in no corpus agent."""
    source = _agent(
        tmp_path,
        f'name: "probe-agent"\ndescription: "d"\ntools: "Read, {tool}"\n',
    )
    assert f'tools: "Read, {tool}"\n' in trae_agent_text(source)
