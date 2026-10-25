# SPDX-License-Identifier: MIT

"""Read-only agents reach an MCP server only when the profile grants it.

Claude Code admits an MCP tool to a subagent's explicit ``tools`` list only when
an entry names the server; the documented form is ``mcp__<server>__*``
(https://code.claude.com/docs/en/sub-agents, retrieved 2026-10-25). The two
scholarly agents therefore keep an explicit read-only list, and the profile's
``agent_mcp_servers`` key names, per agent, the servers whose entries the Claude
Code engine install appends. These tests pin the source shape, the profile key's
validation, the rendering (no setting gives the plain list; a setting touches
the listed agent only; a re-render changes nothing), the plugin tree (plain
list), and that no other harness's agent output depends on the key.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator

from apothem.harnesses._shared import install_driver
from apothem.harnesses._shared import install_driver_converters as conv
from apothem.harnesses.claude_code import install as claude_install
from apothem.lib import claude_agent_mcp as mcp
from apothem.lib.frontmatter import field_value
from apothem.lib.plugin_tree import assemble_plugin_tree
from apothem.lib.profile import ProfileValidationError, coerce_profile, validate_profile
from apothem.lib.propagation import load_manifest

_PKG = Path(__file__).resolve().parents[2] / "src" / "apothem"
_AGENTS = _PKG / "agents"
_MCP_AGENTS = ("citation-auditor", "research-scout")
_PLAIN = "Read, Glob, Grep, WebSearch, WebFetch"
#: Every built-in the two agents must not reach: file writers, shells, helpers
#: that start other helpers, publishing, and task bookkeeping.
_MUST_DENY = frozenset(
    {
        "Write",
        "Edit",
        "MultiEdit",
        "NotebookEdit",
        "Bash",
        "PowerShell",
        "Monitor",
        "Agent",
        "Artifact",
        "TodoWrite",
        "TaskCreate",
        "TaskUpdate",
    }
)
_SCHEMA = json.loads(
    (_PKG / "schemas" / "profile.schema.json").read_text(encoding="utf-8")
)
_VALIDATOR = Draft202012Validator(_SCHEMA)


def _csv(path: Path, key: str) -> set[str]:
    raw = field_value(path, key) or ""
    return {item.strip() for item in raw.split(",") if item.strip()}


def _tools(path: Path) -> str:
    return field_value(path, "tools") or ""


def _profile(**extra: object) -> dict[str, object]:
    return {"identity": {"name": "Test Operator"}, **extra}


def _errors(profile: dict[str, object]) -> list[str]:
    return [e.message for e in _VALIDATOR.iter_errors(profile)]


def _agent(tmp_path: Path, name: str, tools_line: str | None) -> Path:
    lines = ["---", f'name: "{name}"', 'description: "Sample."']
    if tools_line is not None:
        lines.append(tools_line)
    lines += ['disallowedTools: "Write"', "---", "", "Body, tools: kept.", ""]
    path = tmp_path / f"{name}.md"
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return path


def _install(root: Path, profile: dict[str, object]) -> None:
    claude_install.install(root / "settings.json", profile)


def _root(tmp_path: Path) -> Path:
    root = tmp_path / ".claude"
    root.mkdir()
    return root


# ---- source shape --------------------------------------------------------------


@pytest.mark.parametrize("name", _MCP_AGENTS)
def test_source_keeps_an_explicit_read_only_list_and_denies_every_writer(
    name: str,
) -> None:
    source = _AGENTS / f"{name}.md"
    assert _tools(source) == _PLAIN
    assert "mcp__" not in _tools(source)
    assert _csv(source, "disallowedTools") >= _MUST_DENY
    assert (field_value(source, "description") or "").startswith("Read-only ")
    assert conv._agent_is_read_only(source) is True


@pytest.mark.parametrize("name", _MCP_AGENTS)
def test_source_prefers_a_granted_index_and_bounds_it_to_lookups(name: str) -> None:
    text = (_AGENTS / f"{name}.md").read_text(encoding="utf-8")
    frontmatter = text[: text.index("\n---\n", 4)]
    assert "omitted on purpose" not in frontmatter
    assert "creates, updates, deletes" in text
    assert "by capability" in text
    assert "agent_mcp_servers" in text
    assert "web" in text.lower()


# ---- profile key: schema and model ----------------------------------------------


@pytest.mark.parametrize(
    "servers",
    [
        ["scholar"],
        ["a-b", "a_b", "a:b", "a.b", "A1", "a"],
        ["plugin:bio-research:biorxiv"],
        ["x" * 64],
        [],
    ],
)
def test_schema_accepts_valid_server_names(servers: list[str]) -> None:
    assert _errors(_profile(agent_mcp_servers={"research-scout": servers})) == []


@pytest.mark.parametrize(
    "bad",
    [
        "*",
        "a*",
        "mcp__x__*",
        "a__b",
        "-a",
        ".a",
        "",
        "a b",
        "a/b",
        "a;b",
        "é",
        "x" * 65,
        "a\n",
        "a\r",
        "a\r\n",
        "\na",
        "a\nb",
        "foo_",
        "foo-_",
        "foo.",
        "foo:",
        "a_.b",
        "a._b",
        "a:_b",
        "a..b",
        "a::b",
    ],
)
def test_schema_rejects_names_that_could_widen_or_confuse_the_grant(bad: str) -> None:
    assert _errors(_profile(agent_mcp_servers={"research-scout": [bad]}))


@pytest.mark.parametrize(
    "grants",
    [
        {"Research_Scout": ["a"]},
        {"*": ["a"]},
        {"a b": ["a"]},
        {"research-scout\n": ["a"]},
        {"\nresearch-scout": ["a"]},
        {"research-scout": "scholar"},
        {"research-scout": ["a", "a"]},
        {"research-scout": [1]},
        ["research-scout"],
    ],
)
def test_schema_rejects_malformed_grant_shapes(grants: object) -> None:
    assert _errors(_profile(agent_mcp_servers=grants))


@pytest.mark.parametrize(
    "grants",
    [
        {"research-scout": ["good\n"]},
        {"research-scout": ["foo_"]},
        {"research-scout\n": ["good"]},
    ],
)
def test_validate_profile_rejects_a_name_that_would_split_or_blur_the_entry(
    grants: dict[str, list[str]],
) -> None:
    with pytest.raises(ProfileValidationError):
        validate_profile(_profile(agent_mcp_servers=grants))


def test_schema_accepts_the_key_in_a_harness_override() -> None:
    profile = _profile(
        harnesses={"claude-code": {"agent_mcp_servers": {"research-scout": ["a"]}}}
    )
    assert _errors(profile) == []
    bad = _profile(harnesses={"claude-code": {"agent_mcp_servers": {"x": ["*"]}}})
    assert _errors(bad)


def test_schema_and_code_share_one_name_pattern() -> None:
    defs = _SCHEMA["$defs"]["agentMcpServers"]
    assert defs["additionalProperties"]["items"]["pattern"] == mcp.SERVER_NAME_PATTERN
    assert defs["propertyNames"]["pattern"] == mcp.AGENT_NAME_PATTERN


def test_example_profile_validates() -> None:
    example = yaml.safe_load(
        (_PKG / "schemas" / "profile.example.yaml").read_text(encoding="utf-8")
    )
    assert _errors(example) == []


def test_model_defaults_to_no_grants_and_normalizes() -> None:
    assert coerce_profile(_profile()).to_dict()["agent_mcp_servers"] == {}
    grants = {"research-scout": ["b", "a", "a"], "citation-auditor": []}
    model = coerce_profile(_profile(agent_mcp_servers=grants))
    assert model.to_dict()["agent_mcp_servers"] == {"research-scout": ["a", "b"]}


def test_model_drops_a_malformed_entry_instead_of_widening() -> None:
    model = coerce_profile(_profile(agent_mcp_servers={"research-scout": ["*", "ok"]}))
    assert "research-scout" not in model.to_dict()["agent_mcp_servers"]


def test_override_unions_with_the_shared_lists() -> None:
    model = coerce_profile(
        _profile(
            agent_mcp_servers={"research-scout": ["a"]},
            harnesses={"claude-code": {"agent_mcp_servers": {"research-scout": ["b"]}}},
        )
    )
    merged = model.for_harness("claude-code")["agent_mcp_servers"]
    assert merged == {"research-scout": ["a", "b"]}
    assert model.for_harness("cursor")["agent_mcp_servers"] == {"research-scout": ["a"]}


@pytest.mark.parametrize(
    "bad",
    ["*", "a__b", "", "a b", "good\n", "good\r", "foo_", "a_.b", "a:.b", "\ngood"],
)
def test_normalize_grants_raises_on_a_bad_name(bad: str) -> None:
    assert not mcp.is_valid_server_name(bad)
    with pytest.raises(ValueError, match=r"invalid"):
        mcp.normalize_grants({"research-scout": [bad]})
    with pytest.raises(ValueError, match=r"invalid"):
        mcp.normalize_grants({"Bad Agent": ["a"]})


@pytest.mark.parametrize("agent", ["research-scout\n", "\nresearch-scout", "Research"])
def test_normalize_grants_raises_on_a_bad_agent_name(agent: str) -> None:
    with pytest.raises(ValueError, match=r"invalid agent name"):
        mcp.normalize_grants({agent: ["a"]})


def test_entries_use_the_spelling_claude_code_gives_tool_names() -> None:
    assert mcp.tool_entries(["plugin:bio-research:biorxiv", "a.b", "c-d_e"]) == [
        "mcp__a_b__*",
        "mcp__c-d_e__*",
        "mcp__plugin_bio-research_biorxiv__*",
    ]
    # two spellings of one server collapse to a single entry
    assert mcp.tool_entries(["a:b", "a_b", "a.b"]) == ["mcp__a_b__*"]
    for name in ("a:b", "a.b", "plugin:x:y", "a-b", "A1"):
        (entry,) = mcp.tool_entries([name])
        assert "__" not in entry[len("mcp__") : -len("__*")]


def test_a_rendered_tools_line_is_always_one_line(tmp_path: Path) -> None:
    path = _agent(tmp_path, "sample", f'tools: "{_PLAIN}"')
    with mcp.agent_mcp_grants({"sample": ["plugin:x:y", "a.b"]}):
        rendered = mcp.claude_agent_text(path)
    assert f'tools: "{_PLAIN}, mcp__a_b__*, mcp__plugin_x_y__*"\n' in rendered


# ---- the renderer ---------------------------------------------------------------


def test_no_setting_renders_the_source_byte_for_byte() -> None:
    for name in _MCP_AGENTS:
        source = _AGENTS / f"{name}.md"
        assert mcp.claude_agent_text(source) == source.read_text(encoding="utf-8")
    with mcp.agent_mcp_grants({}):
        source = _AGENTS / "research-scout.md"
        assert mcp.claude_agent_text(source) == source.read_text(encoding="utf-8")


def test_a_grant_adds_exactly_the_server_entries_for_that_agent_only() -> None:
    scout = _AGENTS / "research-scout.md"
    auditor = _AGENTS / "citation-auditor.md"
    with mcp.agent_mcp_grants({"research-scout": ["scholar", "a-index", "scholar"]}):
        rendered = mcp.claude_agent_text(scout)
        untouched = mcp.claude_agent_text(auditor)
    assert untouched == auditor.read_text(encoding="utf-8")
    source = scout.read_text(encoding="utf-8")
    expected = source.replace(
        f'tools: "{_PLAIN}"',
        f'tools: "{_PLAIN}, mcp__a-index__*, mcp__scholar__*"',
    )
    assert rendered == expected
    assert rendered != source
    assert "\r" not in rendered


def test_rendering_is_idempotent_and_does_not_leak_past_the_block(
    tmp_path: Path,
) -> None:
    path = _agent(tmp_path, "sample", f'tools: "{_PLAIN}"')
    with mcp.agent_mcp_grants({"sample": ["s"]}):
        once = mcp.claude_agent_text(path)
        path.write_text(once, encoding="utf-8", newline="\n")
        assert mcp.claude_agent_text(path) == once
    assert mcp.claude_agent_text(path) == once  # outside the block: written as is
    assert once.count("mcp__s__*") == 1


def test_an_agent_with_no_tools_line_is_never_narrowed(tmp_path: Path) -> None:
    path = _agent(tmp_path, "sample", None)
    with mcp.agent_mcp_grants({"sample": ["s"]}):
        assert mcp.claude_agent_text(path) == path.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("tools: Read, Grep", "tools: Read, Grep, mcp__s__*"),
        ("tools: 'Read, Grep'", "tools: 'Read, Grep, mcp__s__*'"),
        ('tools: "Read, mcp__s__*"', 'tools: "Read, mcp__s__*"'),
        ("tools: [Read, Grep]", "tools: [Read, Grep]"),
    ],
)
def test_other_scalar_forms(tmp_path: Path, line: str, expected: str) -> None:
    path = _agent(tmp_path, "sample", line)
    with mcp.agent_mcp_grants({"sample": ["s"]}):
        rendered = mcp.claude_agent_text(path)
    assert expected in rendered
    assert rendered.endswith("Body, tools: kept.\n")


def test_a_bad_name_never_reaches_the_renderer() -> None:
    with (
        pytest.raises(ValueError, match=r"invalid MCP server name"),
        mcp.agent_mcp_grants({"research-scout": ["*"]}),
    ):
        pass


def test_grant_problems_report_unknown_and_untoolled_agents(tmp_path: Path) -> None:
    _agent(tmp_path, "has-tools", f'tools: "{_PLAIN}"')
    _agent(tmp_path, "inherits", None)
    problems = mcp.grant_problems(
        tmp_path, {"has-tools": ["a"], "inherits": ["a"], "ghost": ["a"]}
    )
    assert len(problems) == 2
    assert any("ghost" in p for p in problems)
    assert any("inherits" in p and "no explicit tools" in p for p in problems)
    assert mcp.grant_problems(tmp_path, {}) == []


# ---- the Claude Code engine install ------------------------------------------------


def test_install_with_no_setting_copies_every_agent_as_written(
    tmp_path: Path,
) -> None:
    root = _root(tmp_path)
    _install(root, _profile())
    sources = sorted(p for p in _AGENTS.glob("*.md") if p.name != "README.md")
    assert sources
    for source in sources:
        installed = root / "agents" / source.name
        assert installed.read_bytes() == source.read_bytes(), source.name
    assert not (root / "agents" / "README.md").exists()
    for name in _MCP_AGENTS:
        assert _tools(root / "agents" / f"{name}.md") == _PLAIN


def test_install_with_a_setting_adds_entries_to_the_listed_agent_only(
    tmp_path: Path,
) -> None:
    root = _root(tmp_path)
    _install(root, _profile(agent_mcp_servers={"research-scout": ["scholar", "index"]}))
    strip = re.compile(r"^tools:.*\n", re.MULTILINE)
    for source in _AGENTS.glob("*.md"):
        if source.name == "README.md":
            continue
        installed = root / "agents" / source.name
        if source.stem == "research-scout":
            assert _tools(installed) == f"{_PLAIN}, mcp__index__*, mcp__scholar__*"
            # everything but the tools line is unchanged
            assert strip.sub("", installed.read_text("utf-8")) == strip.sub(
                "", source.read_text("utf-8")
            )
        else:
            assert installed.read_bytes() == source.read_bytes(), source.name
    assert _csv(root / "agents" / "research-scout.md", "disallowedTools") >= _MUST_DENY


def test_a_second_install_changes_nothing_and_removing_the_setting_reverts(
    tmp_path: Path,
) -> None:
    root = _root(tmp_path)
    granted = _profile(agent_mcp_servers={"citation-auditor": ["scholar"]})
    _install(root, granted)
    first = (root / "agents" / "citation-auditor.md").read_bytes()
    assert b"mcp__scholar__*" in first
    run = claude_install.install(root / "settings.json", granted)
    assert (root / "agents" / "citation-auditor.md").read_bytes() == first
    assert {
        r.outcome
        for r in run.results
        if r.operation == "claude_agents" and r.path.endswith(".md")
    } == {"unchanged"}
    _install(root, _profile())
    source = (_AGENTS / "citation-auditor.md").read_bytes()
    assert (root / "agents" / "citation-auditor.md").read_bytes() == source


def test_the_harness_override_reaches_the_install(tmp_path: Path) -> None:
    root = _root(tmp_path)
    _install(
        root,
        _profile(
            harnesses={"claude-code": {"agent_mcp_servers": {"research-scout": ["s"]}}}
        ),
    )
    assert "mcp__s__*" in _tools(root / "agents" / "research-scout.md")


def test_install_reports_a_grant_it_cannot_apply(tmp_path: Path) -> None:
    root = _root(tmp_path)
    run = claude_install.install(
        root / "settings.json",
        _profile(agent_mcp_servers={"ghost-agent": ["s"], "research-scout": ["s"]}),
    )
    warnings = [
        r.message
        for r in run.results
        if r.operation == "claude_agents" and r.outcome == "warning"
    ]
    assert any("ghost-agent" in m and "unknown agent" in m for m in warnings)
    assert not any("research-scout" in m for m in warnings)


def test_dry_run_writes_nothing_and_reports_the_agents_entry(tmp_path: Path) -> None:
    root = _root(tmp_path)
    run = claude_install.install(
        root / "settings.json",
        _profile(agent_mcp_servers={"research-scout": ["s"]}),
        dry_run=True,
    )
    assert not (root / "agents").exists()
    rows = [r for r in run.results if r.operation == "claude_agents"]
    assert [r.outcome for r in rows] == ["created"]


def test_manifest_uses_the_rendering_mode_for_claude_code_agents_only() -> None:
    seen = 0
    for harness, rules in load_manifest().items():
        for entry in rules.install:
            if entry.source == "agents/":
                seen += 1
                assert (entry.mode == "claude_agents") == (harness == "claude_code")
    assert seen > 1


# ---- plugin tree and other harnesses ------------------------------------------------


@pytest.mark.parametrize("name", _MCP_AGENTS)
def test_the_plugin_tree_keeps_the_plain_list(name: str, tmp_path: Path) -> None:
    dest = assemble_plugin_tree(_PKG, tmp_path / "plugin")
    assert _tools(dest / "agents" / f"{name}.md") == _PLAIN


def _tree(root: Path) -> dict[str, bytes]:
    return {
        str(p.relative_to(root)).replace("\\", "/"): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


@pytest.mark.parametrize(
    ("harness", "kwargs_key", "agents_rel"),
    [
        ("gemini_cli", "project_root", ".gemini/agents"),
        ("qwen_code", "harness_root", "agents"),
        ("opencode", "harness_root", "agents"),
        ("codex", "harness_root", "agents"),
        ("antigravity", "harness_root", "antigravity-cli/plugins/apothem/agents"),
    ],
)
def test_other_harnesses_emit_the_same_agents_with_or_without_the_key(
    harness: str, kwargs_key: str, agents_rel: str, tmp_path: Path
) -> None:
    plain, granted = tmp_path / "plain", tmp_path / "granted"
    plain.mkdir()
    granted.mkdir()
    install_driver.run_install(harness, **{kwargs_key: plain})  # type: ignore[arg-type]
    with mcp.agent_mcp_grants({n: ["scholar"] for n in _MCP_AGENTS}):
        install_driver.run_install(harness, **{kwargs_key: granted})  # type: ignore[arg-type]
    before, after = _tree(plain / agents_rel), _tree(granted / agents_rel)
    assert before
    assert before == after
    assert not any(b"mcp__scholar__" in data for data in after.values())


class TestGeminiToolNames:
    """The Gemini allowlist for each combination of grant and denial."""

    def _sample(self, tmp_path: Path, tools: str | None, denied: str) -> Path:
        lines = ["---", 'name: "sample"', 'description: "Read-only sample."']
        if tools is not None:
            lines.append(f'tools: "{tools}"')
        lines += [f'disallowedTools: "{denied}"', "---", "", "Body."]
        path = tmp_path / "sample.md"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
        return path

    def test_the_scholarly_agents_get_the_plain_allowlist_with_no_wildcard(
        self,
    ) -> None:
        for name in _MCP_AGENTS:
            names = conv._gemini_tool_names(_AGENTS / f"{name}.md")
            assert names == [
                "read_file",
                "read_many_files",
                "list_directory",
                "glob",
                "grep_search",
                "google_web_search",
                "web_fetch",
            ]

    def test_explicit_grant_never_gains_the_mcp_wildcard(self, tmp_path: Path) -> None:
        path = self._sample(tmp_path, "Read", "Write")
        assert "mcp_*" not in (conv._gemini_tool_names(path) or [])

    def test_no_grant_derives_the_allowlist_from_the_denials(
        self, tmp_path: Path
    ) -> None:
        path = self._sample(tmp_path, None, "Write, Edit, MultiEdit, Bash, TodoWrite")
        names = conv._gemini_tool_names(path) or []
        assert names[-1] == "mcp_*"
        assert not {"write_file", "replace", "run_shell_command"} & set(names)
