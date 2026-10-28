# SPDX-License-Identifier: MIT

"""GitHub Copilot and Cursor subagent renderers write the frontmatter the vendors read.

Copilot takes ``.agent.md`` files whose ``tools`` is an allowlist of tool aliases
(https://docs.github.com/en/copilot/reference/custom-agents-configuration,
retrieved 2026-10-27); Cursor takes ``.md`` files with no ``tools`` key and one
``readonly`` flag (https://cursor.com/docs/subagents, retrieved 2026-10-27). These
tests pin, for every agent in the corpus, the exact frontmatter each renderer
writes, and the rules behind it: Copilot folds the deny list into the allowlist
and never relaxes a denial, a grant that loses every alias becomes ``tools: []``,
and Cursor flags ``readonly`` only on an agent that is read-only and holds no
shell, dropping the read-only label from a description Cursor would not enforce.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path

import pytest
import yaml

from apothem.harnesses._shared.install_driver_agent_copilot_cursor import (
    copilot_agent_text,
    copilot_tool_aliases,
    cursor_agent_text,
    cursor_is_readonly,
)
from apothem.harnesses._shared.install_driver_agent_emitters import AGENT_EMITTERS

_AGENT_DIR = Path(__file__).resolve().parents[2] / "src" / "apothem" / "agents"
_SOURCES = sorted(p for p in _AGENT_DIR.glob("*.md") if p.name != "README.md")

#: stem -> the exact Copilot ``tools`` list, in source order without repeats.
_COPILOT_TOOLS: dict[str, list[str]] = {
    "citation-auditor": ["read", "search", "web"],
    "codebase-explorer": ["read", "search", "execute"],
    "convention-auditor": ["read", "search"],
    "dependency-auditor": ["read", "search", "execute"],
    "design-critic": ["read", "search", "execute"],
    "fact-checker": ["read", "search", "web"],
    "mcp-builder": ["read", "edit", "search", "execute"],
    "memory-auditor": ["read", "search"],
    "prompt-evaluator": ["read", "search", "execute"],
    "quality-gate": ["execute", "read", "search"],
    "refactor-surgeon": ["read", "edit", "search", "execute"],
    "research-scout": ["read", "search", "web"],
    "security-scanner": ["read", "search", "execute"],
    "test-runner": ["read", "search", "execute"],
}

#: The agents that get ``readonly: true`` on Cursor: read-only and no Bash.
_CURSOR_READONLY = {
    "citation-auditor",
    "convention-auditor",
    "fact-checker",
    "memory-auditor",
    "research-scout",
}

#: Read-only agents that keep Bash: no flag, and the label leaves the description.
_CURSOR_UNLABELLED = {
    "codebase-explorer",
    "dependency-auditor",
    "design-critic",
    "prompt-evaluator",
    "quality-gate",
    "security-scanner",
    "test-runner",
}

#: Agents that can author files: nothing changes in Cursor.
_CURSOR_WRITERS = {"mcp-builder", "refactor-surgeon"}


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


def _agent(tmp_path: Path, frontmatter: str) -> Path:
    path = tmp_path / "probe-agent.md"
    path.write_text(f"---\n{frontmatter}---\n\nBody line.\n", encoding="utf-8")
    return path


def test_the_tables_cover_exactly_the_agent_corpus() -> None:
    assert {p.stem for p in _SOURCES} == set(_COPILOT_TOOLS)
    assert len(_SOURCES) == 14
    assert (
        set(_COPILOT_TOOLS) == _CURSOR_READONLY | _CURSOR_UNLABELLED | _CURSOR_WRITERS
    )
    assert not _CURSOR_READONLY & _CURSOR_UNLABELLED


# --- GitHub Copilot ---------------------------------------------------------


@pytest.mark.parametrize("source", _SOURCES, ids=lambda p: p.stem)
def test_copilot_frontmatter_is_exact(source: Path) -> None:
    source_fields, _ = _source_parts(source)
    tools = json.dumps(_COPILOT_TOOLS[source.stem])
    head, _ = _split(copilot_agent_text(source))
    assert head == (
        "---\n"
        f"name: {_quote(str(source_fields['name']))}\n"
        f"description: {_quote(str(source_fields['description']))}\n"
        f"tools: {tools}\n"
        "---\n"
    )


@pytest.mark.parametrize("source", _SOURCES, ids=lambda p: p.stem)
def test_copilot_frontmatter_parses_with_a_list_of_known_aliases(source: Path) -> None:
    fields = _fields(copilot_agent_text(source))
    assert set(fields) == {"name", "description", "tools"}
    assert fields["name"] == source.stem
    assert isinstance(fields["description"], str)
    assert fields["description"]
    tools = fields["tools"]
    assert tools == _COPILOT_TOOLS[source.stem]
    assert isinstance(tools, list)
    assert set(tools) <= {
        "execute",
        "read",
        "edit",
        "search",
        "agent",
        "web",
        "todo",
    }


@pytest.mark.parametrize("source", _SOURCES, ids=lambda p: p.stem)
def test_copilot_never_hands_a_read_only_agent_the_edit_alias(source: Path) -> None:
    source_fields, _ = _source_parts(source)
    denied = {t.strip() for t in str(source_fields["disallowedTools"]).split(",")}
    edit_denied = bool({"Write", "Edit"} & denied)
    aliases = copilot_tool_aliases(source)
    assert aliases is not None
    assert ("edit" in aliases) is (not edit_denied)


@pytest.mark.parametrize("source", _SOURCES, ids=lambda p: p.stem)
def test_copilot_body_is_the_source_body_and_the_file_has_no_bom_or_cr(
    source: Path,
) -> None:
    text = copilot_agent_text(source)
    _, body = _split(text)
    assert body == "\n" + _source_parts(source)[1] + "\n"
    assert not text.startswith("﻿")
    assert "\r" not in text
    assert text.endswith("\n")
    assert not text.endswith("\n\n")


def test_copilot_writes_no_key_beyond_name_description_and_tools() -> None:
    """No model, deny key, turn limit or Apothem metadata reaches a Copilot file."""
    for source in _SOURCES:
        fields = _fields(copilot_agent_text(source))
        for banned in (
            "model",
            "disallowedTools",
            "maxTurns",
            "version",
            "updated",
            "portability",
            "target",
            "infer",
            "mcp-servers",
        ):
            assert banned not in fields, (source.stem, banned)


def test_a_short_copilot_agent_renders_to_this_exact_text(tmp_path: Path) -> None:
    source = _agent(
        tmp_path,
        'name: "probe-agent"\nversion: "0.1.0"\nupdated: "2026-10-27"\n'
        "description: 'Probes the edge: colons, a hash # and commas.'\n"
        'tools: "Read, Bash(git status), mcp__x__*, MultiEdit, TodoWrite, Agent, Glob"\n'
        'disallowedTools: "Write, PowerShell"\n'
        'maxTurns: 7\nportability: "universal"\n',
    )
    # Write is denied, so the edit alias (which also covers Write) is left out, and
    # PowerShell is denied, so the execute alias is. The mcp__ name has no alias.
    assert copilot_agent_text(source) == (
        '---\nname: "probe-agent"\n'
        'description: "Probes the edge: colons, a hash # and commas."\n'
        'tools: ["read", "todo", "agent", "search"]\n---\n\nBody line.\n'
    )


def test_aliases_match_case_and_separators(tmp_path: Path) -> None:
    source = _agent(
        tmp_path,
        'name: "probe-agent"\ndescription: "d"\n'
        'tools: "read, web-fetch, web_search, GREP, Task, NotebookRead, shell"\n',
    )
    assert 'tools: ["read", "web", "search", "agent", "execute"]\n' in (
        copilot_agent_text(source)
    )


def test_a_grant_with_no_alias_becomes_an_empty_list_not_a_missing_key(
    tmp_path: Path,
) -> None:
    """An omitted ``tools`` enables every Copilot tool; ``[]`` disables them all."""
    source = _agent(
        tmp_path,
        'name: "probe-agent"\ndescription: "d"\ntools: "Monitor, mcp__x__tool"\n',
    )
    assert "\ntools: []\n" in copilot_agent_text(source)


def test_a_denial_that_removes_every_granted_alias_gives_an_empty_list(
    tmp_path: Path,
) -> None:
    source = _agent(
        tmp_path,
        'name: "probe-agent"\ndescription: "d"\ntools: "Write"\n'
        'disallowedTools: "Edit"\n',
    )
    assert "\ntools: []\n" in copilot_agent_text(source)


def test_a_source_with_denials_and_no_grant_gets_the_allowlist_they_imply(
    tmp_path: Path,
) -> None:
    source = _agent(
        tmp_path,
        'name: "probe-agent"\ndescription: "d"\n'
        'disallowedTools: "Write, Edit, Bash, TodoWrite, Monitor"\n',
    )
    assert copilot_tool_aliases(source) == ["read", "search", "agent", "web"]
    assert '\ntools: ["read", "search", "agent", "web"]\n' in copilot_agent_text(source)


def test_a_source_that_restricts_nothing_leaves_tools_out(tmp_path: Path) -> None:
    source = _agent(tmp_path, 'name: "probe-agent"\ndescription: "d"\n')
    assert copilot_tool_aliases(source) is None
    assert "tools" not in _fields(copilot_agent_text(source))


def test_an_empty_deny_list_alone_leaves_tools_out(tmp_path: Path) -> None:
    source = _agent(
        tmp_path, 'name: "probe-agent"\ndescription: "d"\ndisallowedTools: ""\n'
    )
    assert "tools" not in _fields(copilot_agent_text(source))


def test_the_copilot_name_falls_back_to_the_file_stem(tmp_path: Path) -> None:
    source = _agent(tmp_path, 'description: "d"\ntools: "Read"\n')
    assert 'name: "probe-agent"\n' in copilot_agent_text(source)


def test_a_patterned_grant_is_left_out_not_widened_to_the_whole_shell(
    tmp_path: Path,
) -> None:
    """``Bash(git status)`` must not become ``execute``, which runs any command."""
    source = _agent(
        tmp_path,
        'name: "probe-agent"\ndescription: "d"\n'
        'tools: "Read, Bash(git status)"\ndisallowedTools: "Write, Edit"\n',
    )
    assert copilot_tool_aliases(source) == ["read"]
    assert '\ntools: ["read"]\n' in copilot_agent_text(source)


def test_a_grant_of_only_a_patterned_tool_gives_an_empty_list(tmp_path: Path) -> None:
    source = _agent(
        tmp_path,
        'name: "probe-agent"\ndescription: "d"\ntools: "Bash(git status)"\n',
    )
    assert copilot_tool_aliases(source) == []
    assert "\ntools: []\n" in copilot_agent_text(source)


def test_a_patterned_denial_removes_the_whole_tool_alias(tmp_path: Path) -> None:
    source = _agent(
        tmp_path,
        'name: "probe-agent"\ndescription: "d"\ntools: "Read, Bash"\n'
        'disallowedTools: "Bash(rm *)"\n',
    )
    assert copilot_tool_aliases(source) == ["read"]


def test_a_webfetch_grant_alone_is_the_web_alias(tmp_path: Path) -> None:
    source = _agent(
        tmp_path, 'name: "probe-agent"\ndescription: "d"\ntools: "WebFetch"\n'
    )
    assert copilot_tool_aliases(source) == ["web"]


@pytest.mark.parametrize("denied", ["MultiEdit", "NotebookEdit"])
def test_each_edit_tool_denial_alone_removes_the_edit_alias(
    tmp_path: Path, denied: str
) -> None:
    """The alias covers all four edit tools, so denying any one drops it."""
    source = _agent(
        tmp_path,
        'name: "probe-agent"\ndescription: "d"\ntools: "Read, Write"\n'
        f'disallowedTools: "{denied}"\n',
    )
    assert copilot_tool_aliases(source) == ["read"]


@pytest.mark.parametrize("granted", ["MultiEdit", "NotebookEdit"])
def test_each_edit_tool_grant_alone_is_the_edit_alias(
    tmp_path: Path, granted: str
) -> None:
    source = _agent(
        tmp_path, f'name: "probe-agent"\ndescription: "d"\ntools: "{granted}"\n'
    )
    assert copilot_tool_aliases(source) == ["edit"]


# --- Cursor -----------------------------------------------------------------


@pytest.mark.parametrize("source", _SOURCES, ids=lambda p: p.stem)
def test_cursor_frontmatter_is_exact(source: Path) -> None:
    source_fields, _ = _source_parts(source)
    description = str(source_fields["description"])
    if source.stem in _CURSOR_UNLABELLED:
        # The read-only label is the leading words; the first letter after it
        # is capitalised so the sentence still starts with a capital. A later
        # "read-only " in the text goes too (as on Antigravity).
        assert description.startswith("Read-only ")
        rest = description[len("Read-only ") :]
        description = re.sub(r"(?i)\bread-only\s+", "", rest[0].upper() + rest[1:])
    expected = (
        f"---\nname: {_quote(str(source_fields['name']))}\n"
        f"description: {_quote(description)}\n"
    )
    if source.stem in _CURSOR_READONLY:
        expected += "readonly: true\n"
    expected += "---\n"
    head, _ = _split(cursor_agent_text(source))
    assert head == expected


def test_readonly_goes_to_exactly_the_five_read_only_agents_without_bash() -> None:
    flagged = {p.stem for p in _SOURCES if cursor_is_readonly(p)}
    assert flagged == _CURSOR_READONLY
    assert len(flagged) == 5
    for source in _SOURCES:
        has_flag = "readonly: true" in cursor_agent_text(source)
        assert has_flag is (source.stem in _CURSOR_READONLY), source.stem


@pytest.mark.parametrize("source", _SOURCES, ids=lambda p: p.stem)
def test_cursor_frontmatter_parses_with_only_documented_keys(source: Path) -> None:
    fields = _fields(cursor_agent_text(source))
    assert set(fields) <= {"name", "description", "readonly"}
    assert {"name", "description"} <= set(fields)
    assert fields["name"] == source.stem
    assert re.fullmatch(r"[a-z]+(-[a-z]+)*", str(fields["name"]))
    if "readonly" in fields:
        assert fields["readonly"] is True
    for banned in (
        "tools",
        "disallowedTools",
        "model",
        "maxTurns",
        "is_background",
        "version",
        "updated",
        "portability",
    ):
        assert banned not in fields, (source.stem, banned)


def test_read_only_agents_that_keep_bash_lose_the_read_only_label() -> None:
    for source in _SOURCES:
        description = str(_fields(cursor_agent_text(source))["description"])
        has_label = "read-only" in description.lower()
        if source.stem in _CURSOR_UNLABELLED:
            assert not has_label, source.stem
            assert description[0].isupper(), source.stem
        else:
            original = str(_source_parts(source)[0]["description"])
            assert description == original, source.stem
    for stem in _CURSOR_READONLY:
        source = _AGENT_DIR / f"{stem}.md"
        text = str(_fields(cursor_agent_text(source))["description"])
        assert "read-only" in text.lower(), stem


@pytest.mark.parametrize("source", _SOURCES, ids=lambda p: p.stem)
def test_cursor_body_is_the_source_body_and_the_file_has_no_bom_or_cr(
    source: Path,
) -> None:
    text = cursor_agent_text(source)
    _, body = _split(text)
    assert body == "\n" + _source_parts(source)[1] + "\n"
    assert not text.startswith("﻿")
    assert "\r" not in text
    assert text.endswith("\n")
    assert not text.endswith("\n\n")


def test_a_short_cursor_agent_renders_to_this_exact_text(tmp_path: Path) -> None:
    source = _agent(
        tmp_path,
        'name: "probe-agent"\nversion: "0.1.0"\nupdated: "2026-10-27"\n'
        "description: 'Read-only probe: colons, a hash # and commas.'\n"
        'tools: "Read, Glob"\ndisallowedTools: "Write, Edit"\n'
        'maxTurns: 7\nportability: "universal"\n',
    )
    assert cursor_agent_text(source) == (
        '---\nname: "probe-agent"\n'
        'description: "Read-only probe: colons, a hash # and commas."\n'
        "readonly: true\n---\n\nBody line.\n"
    )


def test_a_grant_with_a_shell_is_not_flagged_even_when_it_cannot_write(
    tmp_path: Path,
) -> None:
    source = _agent(
        tmp_path,
        'name: "probe-agent"\ndescription: "Read-only runner of tests."\n'
        'tools: "Read, Bash"\ndisallowedTools: "Write, Edit"\n',
    )
    text = cursor_agent_text(source)
    assert "readonly" not in text
    assert 'description: "Runner of tests."\n' in text


def test_powershell_counts_as_a_shell(tmp_path: Path) -> None:
    source = _agent(
        tmp_path,
        'name: "probe-agent"\ndescription: "d"\ntools: "Read, PowerShell"\n',
    )
    assert cursor_is_readonly(source) is False


def test_a_source_with_no_grant_is_flagged_only_when_every_shell_is_denied(
    tmp_path: Path,
) -> None:
    inherits_shell = _agent(
        tmp_path,
        'name: "probe-agent"\ndescription: "d"\ndisallowedTools: "Write, Edit"\n',
    )
    assert cursor_is_readonly(inherits_shell) is False
    only_bash_denied = _agent(
        tmp_path,
        'name: "probe-agent"\ndescription: "d"\ndisallowedTools: "Write, Edit, Bash"\n',
    )
    assert cursor_is_readonly(only_bash_denied) is False
    no_shell = _agent(
        tmp_path,
        'name: "probe-agent"\ndescription: "d"\n'
        'disallowedTools: "Write, Edit, Bash, PowerShell"\n',
    )
    assert cursor_is_readonly(no_shell) is True


def test_an_agent_that_can_write_is_never_flagged(tmp_path: Path) -> None:
    source = _agent(
        tmp_path, 'name: "probe-agent"\ndescription: "d"\ntools: "Read, Write"\n'
    )
    assert cursor_is_readonly(source) is False
    assert 'description: "d"\n---' in cursor_agent_text(source)


def test_the_cursor_name_falls_back_to_the_file_stem(tmp_path: Path) -> None:
    source = _agent(tmp_path, 'description: "d"\ntools: "Read"\n')
    assert 'name: "probe-agent"\n' in cursor_agent_text(source)


@pytest.mark.parametrize("render", [copilot_agent_text, cursor_agent_text])
def test_an_upper_case_source_name_is_written_in_lower_case(
    tmp_path: Path, render: Callable[[Path], str]
) -> None:
    """The shared head lower-cases the source name, as every native renderer does."""
    source = _agent(tmp_path, 'name: "Probe-Agent"\ndescription: "d"\ntools: "Read"\n')
    assert 'name: "probe-agent"\n' in render(source)


# --- Registry ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("mode", "render", "extension"),
    [
        ("copilot_agents", copilot_agent_text, "agent.md"),
        ("cursor_agents", cursor_agent_text, None),
    ],
)
def test_the_registry_rows_pair_each_mode_with_its_renderer(
    mode: str, render: Callable[[Path], str], extension: str | None
) -> None:
    row = AGENT_EMITTERS[mode]
    assert row.renderer is render
    assert row.target_extension == extension
    assert row.exclude == frozenset()
    assert row.remove_stale_markdown is False
    source = Path("agents/code-reviewer.md")
    expected = "code-reviewer.agent.md" if extension else "code-reviewer.md"
    assert row.target_name(source) == expected
