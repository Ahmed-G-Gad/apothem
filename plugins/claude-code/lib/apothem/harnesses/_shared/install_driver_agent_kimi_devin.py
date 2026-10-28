# SPDX-License-Identifier: MIT

"""Native subagent renderers for Kimi Code and Devin Local (the Windsurf agent).

Both vendors read a Markdown agent file with YAML frontmatter between ``---``
lines and the agent's prompt as the body, and both spell tools in their own
vocabulary, so a source ``tools`` entry has to be translated, not copied:

- Kimi Code (``<project>/.kimi-code/agents/<name>.md``) reads the keys ``name``
  (optional, kebab-case), ``description`` (required), ``whenToUse``, ``override``,
  ``tools``, ``disallowedTools`` and ``subagents``, and ignores every other key
  (https://moonshotai.github.io/kimi-code/en/customization/agents.md, retrieved
  2026-10-27). ``tools`` and ``disallowedTools`` take a YAML list; an omitted
  ``tools`` allows every tool, ``tools: []`` allows none, and
  ``disallowedTools`` applies after ``tools``. Tool names are exact and
  case-sensitive; the built-in names are in
  https://moonshotai.github.io/kimi-code/en/reference/tools.md. Of the source
  vocabulary Kimi shares Read, Write, Edit, Grep, Glob, Bash, WebSearch and Agent,
  names its fetch tool ``FetchURL`` (the source ``WebFetch``) and its todo tool
  ``TodoList`` (the source ``TodoWrite``), and has no MultiEdit, NotebookEdit,
  PowerShell, Monitor, Artifact, TaskCreate or TaskUpdate. A name outside that
  table is left out.
- Devin Local (``<project>/.devin/agents/<name>.md``) reads ``name``,
  ``description``, ``model``, ``allowed-tools`` (alias ``tools``, a list) and
  ``max-nesting`` (https://docs.devin.ai/cli/subagents.md, retrieved
  2026-10-27). ``allowed-tools`` restricts the subagent to the listed tools and
  defaults to all of them. The tool names are lowercase: ``read``, ``edit``,
  ``grep``, ``glob`` and ``exec``
  (https://docs.devin.ai/cli/extensibility/skills/creating-skills.md) and
  ``write`` (CLI changelog v3000.11.1). The page documents no deny key, so
  the source grant minus its denials is compiled into the allowlist. The names of
  the web tools are not documented for ``allowed-tools``, so the install holds
  back the agents that need them (``AGENT_EMITTERS["devin_agents"].exclude``).

Both renderers write a fresh frontmatter and copy the body unchanged. Neither
writes ``model`` (Kimi has no per-agent model key; Devin's default subagent model
is router-selected and is not the parent's), ``override`` (it would let a project
file replace a built-in agent), ``subagents``, ``max-nesting`` or Apothem's
``version``, ``updated``, ``maxTurns`` and ``portability`` metadata. The profile's
``agent_mcp_servers`` key is not applied here.

A restriction the source states is never relaxed. A source tool pattern such as
``Bash(git status)`` has no form in either vendor's list: in a grant it is left
out (a narrower agent), and in a denial it denies the whole tool. A Kimi grant
that had names but lost them all is written as ``tools: []`` because an omitted
``tools`` allows every tool. A Devin grant that loses every name is written as
``allowed-tools: []``; the page does not say how an empty list is read, which the
pin records as an open question (no agent in the corpus reaches that case).
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from .install_driver_agent_copilot_cursor import _head
from .install_driver_converters import (
    _agent_body,
    _agent_description,
    _agent_scalar_list,
    _agent_tool_names,
    _tool_key,
    _yaml_list,
)

#: Source tool lookup key (lower case, no ``-`` or ``_``) to the Kimi Code tool
#: name, spelled as https://moonshotai.github.io/kimi-code/en/reference/tools.md
#: spells it. A source name outside this table has no Kimi tool.
_KIMI_TOOLS: Final[dict[str, str]] = {
    "read": "Read",
    "write": "Write",
    "edit": "Edit",
    "grep": "Grep",
    "glob": "Glob",
    "bash": "Bash",
    "websearch": "WebSearch",
    "webfetch": "FetchURL",
    "todowrite": "TodoList",
    "agent": "Agent",
}

#: Source tool lookup key to the Devin Local ``allowed-tools`` name. ``Bash`` is
#: ``exec``. The web tools are absent on purpose: Devin documents no
#: ``allowed-tools`` name for them.
_DEVIN_TOOLS: Final[dict[str, str]] = {
    "read": "read",
    "edit": "edit",
    "grep": "grep",
    "glob": "glob",
    "bash": "exec",
    "write": "write",
}

#: The Devin names in the order the vendor lists them; the allowlist a source
#: with denials and no grant compiles to starts from all of them.
_DEVIN_VOCABULARY: Final[tuple[str, ...]] = (
    "read",
    "edit",
    "grep",
    "glob",
    "exec",
    "write",
)


def _denied_names(source_path: Path, mapping: dict[str, str]) -> list[str]:
    """Return the native names of the tools the source denies, in source order.

    A denial with a pattern (``Bash(rm *)``) denies the whole tool, because none
    of the vendors that use this (Kimi Code, Devin, CodeBuddy and Trae) can
    express the pattern.
    """
    names: list[str] = []
    for item in _agent_scalar_list(source_path, "disallowedTools"):
        mapped = mapping.get(_tool_key(item))
        if mapped and mapped not in names:
            names.append(mapped)
    return names


def kimi_agent_text(source_path: Path) -> str:
    """Render a source agent as a Kimi Code agent file.

    Emits ``name``, ``description`` and, when the source restricts tools, ``tools``
    and ``disallowedTools`` as YAML lists of Kimi tool names. A source grant
    becomes ``tools`` (``tools: []`` when none of its names exists in Kimi, since
    an omitted ``tools`` would allow every tool); a source without a grant leaves
    ``tools`` out, as the source does, and its denials stand in
    ``disallowedTools``, which Kimi applies after ``tools``.
    """
    frontmatter = _head(source_path, _agent_description(source_path))
    granted = _agent_tool_names(source_path, "tools", _KIMI_TOOLS)
    if granted:
        frontmatter += _yaml_list("tools", granted)
    elif _agent_scalar_list(source_path, "tools"):
        frontmatter += "tools: []\n"
    frontmatter += _yaml_list(
        "disallowedTools", _denied_names(source_path, _KIMI_TOOLS)
    )
    body = _agent_body(source_path).strip()
    return f"{frontmatter}---\n\n{body}\n"


def devin_allowed_tools(source_path: Path) -> list[str] | None:
    """Return the Devin Local ``allowed-tools`` list, or ``None`` to leave it out.

    With a source grant: the Devin names of the granted tools, in source order and
    without repeats, minus the tools the source denies. Without one the source
    inherits every tool except its denials, and Devin has no deny key, so the
    allowlist the denials imply is written instead: every documented Devin name
    the source does not deny. A source with neither a grant nor a denial inherits
    as written (``None``). A source tool with no Devin name (the web tools, an
    ``mcp__`` entry) is not listed.
    """
    has_grant = bool(_agent_scalar_list(source_path, "tools"))
    has_denial = bool(_agent_scalar_list(source_path, "disallowedTools"))
    if not has_grant and not has_denial:
        return None
    blocked = set(_denied_names(source_path, _DEVIN_TOOLS))
    candidates = (
        _agent_tool_names(source_path, "tools", _DEVIN_TOOLS)
        if has_grant
        else list(_DEVIN_VOCABULARY)
    )
    return [name for name in candidates if name not in blocked]


def devin_agent_text(source_path: Path) -> str:
    """Render a source agent as a Devin Local subagent profile.

    Emits ``name``, ``description`` and, unless the source restricts nothing,
    ``allowed-tools`` as a YAML list of lowercase Devin tool names (see
    :func:`devin_allowed_tools`).
    """
    frontmatter = _head(source_path, _agent_description(source_path))
    tools = devin_allowed_tools(source_path)
    if tools is not None:
        frontmatter += _yaml_list("allowed-tools", tools) or "allowed-tools: []\n"
    body = _agent_body(source_path).strip()
    return f"{frontmatter}---\n\n{body}\n"
