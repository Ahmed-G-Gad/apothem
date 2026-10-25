# SPDX-License-Identifier: MIT

"""Gemini CLI subagents reach an MCP server only when the profile grants it.

A Gemini CLI subagent with a ``tools`` list reaches one MCP server's tools through
the wildcard ``mcp_<server>_*``; Gemini CLI names every MCP tool
``mcp_{serverName}_{toolName}`` and splits it at the first underscore after
``mcp_``, so a server name holding an underscore cannot be addressed
(https://geminicli.com/docs/core/subagents and
https://geminicli.com/docs/tools/mcp-server/, retrieved 2026-10-25). The profile's
``agent_mcp_servers`` key names, per agent, the servers whose entries the Gemini CLI
install appends. These tests pin that no setting changes nothing, that a grant
touches the listed agent only, that a re-install is stable, that bad names are
refused or skipped, and that no other harness's agents depend on the key.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from apothem.harnesses._shared import install_driver
from apothem.harnesses._shared import install_driver_converters as conv
from apothem.harnesses.gemini_cli import install as gemini_install
from apothem.lib import claude_agent_mcp as claude_mcp
from apothem.lib import gemini_agent_mcp as gmcp
from apothem.lib.frontmatter import field_value

_PKG = Path(__file__).resolve().parents[2] / "src" / "apothem"
_AGENTS = _PKG / "agents"
_MCP_AGENTS = ("citation-auditor", "research-scout")
_PLAIN = [
    "read_file",
    "read_many_files",
    "list_directory",
    "glob",
    "grep_search",
    "google_web_search",
    "web_fetch",
]


def _profile(**extra: object) -> dict[str, object]:
    return {"identity": {"name": "Test Operator"}, **extra}


def _install(root: Path, profile: dict[str, object]) -> list[str]:
    run = gemini_install.install(root / "settings.json", profile, project=root)
    return [r.message for r in run.results if r.outcome == "warning"]


def _agents(root: Path) -> dict[str, bytes]:
    base = root / ".gemini" / "agents"
    return {p.name: p.read_bytes() for p in sorted(base.glob("*.md"))}


def _tools(text: str) -> list[str]:
    """Return the entries of the ``tools`` list in a rendered Gemini agent."""
    lines = text.split("\n---\n", 1)[0].split("\n")
    if "tools:" not in lines:
        return []
    out: list[str] = []
    for line in lines[lines.index("tools:") + 1 :]:
        if not line.startswith("  - "):
            break
        out.append(line[4:].strip('"'))
    return out


def _sample(tmp_path: Path, name: str, tools: str | None, denied: str) -> Path:
    lines = ["---", f'name: "{name}"', 'description: "Sample."']
    if tools is not None:
        lines.append(f'tools: "{tools}"')
    lines += [f'disallowedTools: "{denied}"', "---", "", "Body.", ""]
    path = tmp_path / f"{name}.md"
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return path


@pytest.fixture(scope="module")
def plain_agents(tmp_path_factory: pytest.TempPathFactory) -> dict[str, bytes]:
    root = tmp_path_factory.mktemp("plain")
    _install(root, _profile())
    return _agents(root)


# ---- the converter ---------------------------------------------------------------


def test_no_setting_renders_the_plain_allowlist() -> None:
    for name in _MCP_AGENTS:
        source = _AGENTS / f"{name}.md"
        plain = conv._gemini_agent_text(source)
        assert _tools(plain) == _PLAIN
        with gmcp.gemini_agent_mcp_grants({}):
            assert conv._gemini_agent_text(source) == plain
        with gmcp.gemini_agent_mcp_grants({"some-other-agent": ["scholar"]}):
            assert conv._gemini_agent_text(source) == plain


def test_a_grant_adds_exactly_the_documented_entries_for_that_agent_only() -> None:
    scout = _AGENTS / "research-scout.md"
    auditor = _AGENTS / "citation-auditor.md"
    plain_scout = conv._gemini_agent_text(scout)
    plain_auditor = conv._gemini_agent_text(auditor)
    grants = {"research-scout": ["scholar", "a-index", "scholar"]}
    with gmcp.gemini_agent_mcp_grants(grants):
        granted = conv._gemini_agent_text(scout)
        untouched = conv._gemini_agent_text(auditor)
    assert untouched == plain_auditor
    assert _tools(granted) == [*_PLAIN, "mcp_a-index_*", "mcp_scholar_*"]
    # everything but the added tools entries is unchanged
    extra = '  - "mcp_a-index_*"\n  - "mcp_scholar_*"\n'
    assert granted.replace(extra, "") == plain_scout


def test_rendering_is_idempotent_and_does_not_leak_past_the_block() -> None:
    scout = _AGENTS / "research-scout.md"
    plain = conv._gemini_agent_text(scout)
    with gmcp.gemini_agent_mcp_grants({"research-scout": ["s"]}):
        once = conv._gemini_agent_text(scout)
        assert conv._gemini_agent_text(scout) == once
    assert once.count("mcp_s_*") == 1
    assert conv._gemini_agent_text(scout) == plain


def test_an_agent_that_inherits_every_tool_is_left_alone(tmp_path: Path) -> None:
    path = _sample(tmp_path, "open-agent", None, "")
    plain = conv._gemini_agent_text(path)
    assert "tools:" not in plain
    with gmcp.gemini_agent_mcp_grants({"open-agent": ["s"]}):
        assert conv._gemini_agent_text(path) == plain


def test_an_agent_with_the_all_servers_wildcard_gains_no_entry(tmp_path: Path) -> None:
    path = _sample(tmp_path, "wide-agent", None, "Write")
    plain = conv._gemini_agent_text(path)
    assert "mcp_*" in _tools(plain)
    with gmcp.gemini_agent_mcp_grants({"wide-agent": ["s"]}):
        assert conv._gemini_agent_text(path) == plain


def test_an_explicit_grant_gains_the_server_entry_without_the_wildcard(
    tmp_path: Path,
) -> None:
    path = _sample(tmp_path, "narrow-agent", "Read", "Write")
    with gmcp.gemini_agent_mcp_grants({"narrow-agent": ["s"]}):
        rendered = conv._gemini_agent_text(path)
    assert _tools(rendered)[-1] == "mcp_s_*"
    assert "mcp_*" not in _tools(rendered)


def test_entries_use_gemini_spelling_not_the_claude_prefix() -> None:
    assert gmcp.tool_entries(["b", "a-1", "b"]) == ["mcp_a-1_*", "mcp_b_*"]
    assert not any("__" in e for e in gmcp.tool_entries(["a", "b"]))


# ---- name validation -------------------------------------------------------------


@pytest.mark.parametrize(
    "bad",
    ["*", "a*", "", " ", "a b", "a\n", "-a", "a-", "a__b", "a..b", "a:b:", "/x", "a;b"],
)
def test_malformed_names_are_rejected_before_rendering(bad: str) -> None:
    with pytest.raises(ValueError, match="invalid MCP server name"):
        gmcp.gemini_agent_mcp_grants({"research-scout": [bad]}).__enter__()


@pytest.mark.parametrize("agent", ["Research-Scout", "x/y", "", "a b", "a_b", "a\n"])
def test_malformed_agent_names_are_rejected(agent: str) -> None:
    with pytest.raises(ValueError, match="invalid agent name"):
        gmcp.gemini_agent_mcp_grants({agent: ["s"]}).__enter__()


@pytest.mark.parametrize(
    "name", ["my_server", "plugin:a:b", "a.b", "a_b-c", "a:b", "snake_case_1"]
)
def test_a_name_gemini_cannot_address_is_never_rendered(name: str) -> None:
    assert not gmcp.is_addressable(name)
    assert gmcp.tool_entries([name]) == []
    assert gmcp.unaddressable_servers([name, "ok"]) == [name]
    scout = _AGENTS / "research-scout.md"
    plain = conv._gemini_agent_text(scout)
    with gmcp.gemini_agent_mcp_grants({"research-scout": [name]}):
        assert conv._gemini_agent_text(scout) == plain


@pytest.mark.parametrize("name", ["scholar", "a-b", "S2", "x-1-y", "my--server"])
def test_addressable_names(name: str) -> None:
    assert gmcp.is_addressable(name)


# ---- the Gemini CLI install ------------------------------------------------------


def test_install_with_no_setting_is_the_plain_conversion(
    tmp_path: Path, plain_agents: dict[str, bytes]
) -> None:
    warnings = _install(tmp_path, _profile(agent_mcp_servers={}))
    assert not any("agent_mcp_servers" in m for m in warnings)
    assert _agents(tmp_path) == plain_agents
    for name in _MCP_AGENTS:
        assert _tools(plain_agents[f"{name}.md"].decode("utf-8")) == _PLAIN


def test_install_with_a_setting_adds_entries_to_the_listed_agent_only(
    tmp_path: Path, plain_agents: dict[str, bytes]
) -> None:
    warnings = _install(
        tmp_path, _profile(agent_mcp_servers={"research-scout": ["scholar", "index"]})
    )
    assert not any("agent_mcp_servers" in m for m in warnings)
    after = _agents(tmp_path)
    assert after.keys() == plain_agents.keys()
    for name, data in after.items():
        if name == "research-scout.md":
            assert _tools(data.decode("utf-8")) == [
                *_PLAIN,
                "mcp_index_*",
                "mcp_scholar_*",
            ]
        else:
            assert data == plain_agents[name], name


def test_a_second_install_changes_nothing_and_removing_the_setting_reverts(
    tmp_path: Path, plain_agents: dict[str, bytes]
) -> None:
    granted = _profile(agent_mcp_servers={"citation-auditor": ["scholar"]})
    _install(tmp_path, granted)
    first = _agents(tmp_path)
    assert b"mcp_scholar_*" in first["citation-auditor.md"]
    run = gemini_install.install(tmp_path / "settings.json", granted, project=tmp_path)
    assert _agents(tmp_path) == first
    assert {
        r.outcome
        for r in run.results
        if r.operation == "gemini_agents" and r.path.endswith(".md")
    } == {"unchanged"}
    _install(tmp_path, _profile())
    assert _agents(tmp_path) == plain_agents


def test_the_gemini_override_reaches_the_install_and_the_claude_one_does_not(
    tmp_path: Path, plain_agents: dict[str, bytes]
) -> None:
    other = tmp_path / "claude-override"
    other.mkdir()
    claude_only = {"claude-code": {"agent_mcp_servers": {"research-scout": ["s"]}}}
    _install(other, _profile(harnesses=claude_only))
    assert _agents(other) == plain_agents
    mine = tmp_path / "gemini-override"
    mine.mkdir()
    gemini_only = {"gemini-cli": {"agent_mcp_servers": {"research-scout": ["s"]}}}
    _install(mine, _profile(harnesses=gemini_only))
    assert "mcp_s_*" in _tools(_agents(mine)["research-scout.md"].decode("utf-8"))


def test_install_reports_a_grant_it_cannot_apply(tmp_path: Path) -> None:
    warnings = _install(
        tmp_path,
        _profile(
            agent_mcp_servers={
                "ghost-agent": ["s"],
                "research-scout": ["good", "bad_name", "plugin:a:b"],
            }
        ),
    )
    assert any("ghost-agent" in m and "unknown agent" in m for m in warnings)
    assert any("bad_name" in m and "research-scout" in m for m in warnings)
    assert any("plugin:a:b" in m for m in warnings)
    tools = _tools(_agents(tmp_path)["research-scout.md"].decode("utf-8"))
    assert tools == [*_PLAIN, "mcp_good_*"]


def test_grant_problems_report_an_agent_that_already_reaches_every_server(
    tmp_path: Path,
) -> None:
    _sample(tmp_path, "open-agent", None, "")
    _sample(tmp_path, "wide-agent", None, "Write")
    _sample(tmp_path, "narrow-agent", "Read", "Write")
    problems = gemini_install.grant_problems(
        tmp_path, {"open-agent": ["s"], "wide-agent": ["s"], "narrow-agent": ["s"]}
    )
    assert len(problems) == 2
    assert any("open-agent" in m for m in problems)
    assert any("wide-agent" in m for m in problems)
    assert gemini_install.grant_problems(tmp_path, {}) == []


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    run = gemini_install.install(
        tmp_path / "settings.json",
        _profile(agent_mcp_servers={"research-scout": ["s"]}),
        project=tmp_path,
        dry_run=True,
    )
    assert run.results
    assert not (tmp_path / ".gemini" / "agents").exists()


def test_the_project_is_still_required(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="requires --project"):
        gemini_install.install(tmp_path / "settings.json", _profile())


# ---- no leakage between harnesses ------------------------------------------------


def _tree(root: Path) -> dict[str, bytes]:
    return {
        str(p.relative_to(root)).replace("\\", "/"): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


@pytest.mark.parametrize(
    ("harness", "kwargs_key", "agents_rel"),
    [
        ("qwen_code", "harness_root", "agents"),
        ("opencode", "harness_root", "agents"),
        ("codex", "harness_root", "agents"),
        ("antigravity", "harness_root", "antigravity-cli/plugins/apothem/agents"),
    ],
)
def test_other_harnesses_emit_the_same_agents_under_gemini_grants(
    harness: str, kwargs_key: str, agents_rel: str, tmp_path: Path
) -> None:
    plain, granted = tmp_path / "plain", tmp_path / "granted"
    plain.mkdir()
    granted.mkdir()
    install_driver.run_install(harness, **{kwargs_key: plain})  # type: ignore[arg-type]
    with gmcp.gemini_agent_mcp_grants({n: ["scholar"] for n in _MCP_AGENTS}):
        install_driver.run_install(harness, **{kwargs_key: granted})  # type: ignore[arg-type]
    before, after = _tree(plain / agents_rel), _tree(granted / agents_rel)
    assert before
    assert before == after
    assert not any(b"mcp_scholar_" in data for data in after.values())


def test_claude_grants_do_not_render_into_gemini_agents_and_the_reverse() -> None:
    scout = _AGENTS / "research-scout.md"
    plain_gemini = conv._gemini_agent_text(scout)
    plain_claude = claude_mcp.claude_agent_text(scout)
    with claude_mcp.agent_mcp_grants({"research-scout": ["s"]}):
        assert conv._gemini_agent_text(scout) == plain_gemini
    with gmcp.gemini_agent_mcp_grants({"research-scout": ["s"]}):
        assert claude_mcp.claude_agent_text(scout) == plain_claude


def test_the_source_agents_name_no_mcp_tool() -> None:
    for name in _MCP_AGENTS:
        source = _AGENTS / f"{name}.md"
        assert "mcp_" not in (field_value(source, "tools") or "")


# ---- a source denial wins over a grant ---------------------------------------


@pytest.mark.parametrize(
    ("denials", "expected"),
    [
        ([], frozenset()),
        (["Write", "Bash"], frozenset()),
        (["mcp__scholar__*"], frozenset({"scholar"})),
        (["mcp__scholar"], frozenset({"scholar"})),
        (["mcp__scholar__search_works"], frozenset({"scholar"})),
        (["mcp__a-b__*", "mcp__c__x"], frozenset({"a-b", "c"})),
        (["mcp"], None),
        (["mcp__*"], None),
    ],
)
def test_denied_servers_reads_claude_deny_entries(
    denials: list[str], expected: frozenset[str] | None
) -> None:
    assert gmcp.denied_servers(denials) == expected


def _agent_with_denials(tmp_path: Path, denials: str) -> Path:
    path = tmp_path / "research-scout.md"
    path.write_text(
        "---\nname: research-scout\ndescription: Finds sources.\n"
        'tools: "Read, WebFetch"\n'
        f'disallowedTools: "{denials}"\n---\n\nBody.\n',
        encoding="utf-8",
        newline="\n",
    )
    return path


def test_a_denied_server_gets_no_entry(tmp_path: Path) -> None:
    path = _agent_with_denials(tmp_path, "Write, mcp__scholar__*")
    with gmcp.gemini_agent_mcp_grants({"research-scout": ["scholar", "papers"]}):
        tools = _tools(conv._gemini_agent_text(path))
    assert "mcp_papers_*" in tools
    assert "mcp_scholar_*" not in tools


def test_a_source_denying_every_server_gets_no_entry(tmp_path: Path) -> None:
    path = _agent_with_denials(tmp_path, "mcp")
    plain = conv._gemini_agent_text(path)
    with gmcp.gemini_agent_mcp_grants({"research-scout": ["scholar"]}):
        assert conv._gemini_agent_text(path) == plain


def test_a_denied_grant_is_reported(tmp_path: Path) -> None:
    _agent_with_denials(tmp_path, "mcp__scholar__*")
    problems = gemini_install.grant_problems(
        tmp_path, {"research-scout": ["scholar", "papers"]}
    )
    assert any("denies MCP server 'scholar'" in p for p in problems)
    assert not any("'papers'" in p for p in problems)
