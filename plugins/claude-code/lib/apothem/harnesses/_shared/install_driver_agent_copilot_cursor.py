# SPDX-License-Identifier: MIT

"""Native subagent renderers for GitHub Copilot and Cursor.

Both vendors read a Markdown agent file with YAML frontmatter between ``---``
lines and the agent's prompt as the body, and both restrict tools far more
coarsely than the source ``tools`` / ``disallowedTools`` pair does:

- GitHub Copilot (``<project>/.github/agents/<name>.agent.md``) takes ``name``,
  ``description`` (the one required key) and ``tools`` among its keys
  (https://docs.github.com/en/copilot/reference/custom-agents-configuration,
  retrieved 2026-10-27). ``tools`` is an allowlist of tool *aliases*: an omitted
  ``tools`` enables every tool, ``[]`` disables them all, and an unrecognized
  name is ignored. There is no deny key, so the source grant minus its denials is
  compiled into the allowlist. The aliases are case-insensitive and each stands
  for a group of tools: ``execute`` (Bash, shell, powershell), ``read`` (Read,
  NotebookRead), ``edit`` (Edit, MultiEdit, Write, NotebookEdit), ``search``
  (Grep, Glob), ``agent`` (custom-agent, Task), ``web`` (WebSearch, WebFetch) and
  ``todo`` (TodoWrite).
- Cursor (``<project>/.cursor/agents/<name>.md``) documents ``name``,
  ``description``, ``model``, ``readonly`` and ``is_background``, all optional,
  and no ``tools`` key: a subagent inherits every tool of the parent, MCP tools
  included (https://cursor.com/docs/subagents, retrieved 2026-10-27). The one
  restriction is ``readonly: true``, "no file edits, no state-changing shell
  commands".

Both renderers write a fresh frontmatter and copy the body unchanged. Neither
writes ``model`` (the agent then runs on the model the harness selects),
``maxTurns`` (neither vendor documents a turn limit) or Apothem's ``version``,
``updated`` and ``portability`` metadata. The profile's ``agent_mcp_servers`` key
is not applied here, and a source tool name outside the alias table, an
``mcp__`` entry included, is left out.

A restriction the source states is never relaxed. Copilot leaves an alias out of
the allowlist when the source denies any tool the alias covers, so a grant of
``Write`` with ``Edit`` denied loses ``edit`` altogether instead of keeping a
tool the source forbids. A grant that loses every alias is written as
``tools: []`` because an omitted ``tools`` would enable every tool. Cursor marks
an agent ``readonly: true`` only when it is read-only by the source rule and
holds no shell: ``readonly`` also bars a test or lint run, so a read-only agent
that keeps ``Bash`` (a test runner, a quality gate) gets no flag, and its
description drops the read-only label that nothing in Cursor would enforce.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final

from apothem.lib.frontmatter import field_value

from .install_driver_converters import (
    _agent_body,
    _agent_description,
    _agent_is_read_only,
    _agent_scalar_list,
    _drop_read_only_claim,
    _tool_key,
    _yaml_scalar,
)

#: Copilot tool aliases in the order its docs list them.
_COPILOT_ALIASES: Final[tuple[str, ...]] = (
    "execute",
    "read",
    "edit",
    "search",
    "agent",
    "web",
    "todo",
)

#: Case- and separator-insensitive tool key to the Copilot alias that covers it.
#: The keys are the primary aliases and the compatible aliases the Copilot docs
#: list for each; a source tool outside this table has no Copilot equivalent.
_COPILOT_ALIAS_OF: Final[dict[str, str]] = {
    "execute": "execute",
    "shell": "execute",
    "bash": "execute",
    "powershell": "execute",
    "read": "read",
    "notebookread": "read",
    "edit": "edit",
    "multiedit": "edit",
    "write": "edit",
    "notebookedit": "edit",
    "search": "search",
    "grep": "search",
    "glob": "search",
    "agent": "agent",
    "customagent": "agent",
    "task": "agent",
    "web": "web",
    "websearch": "web",
    "webfetch": "web",
    "todo": "todo",
    "todowrite": "todo",
}

#: Source tools that run commands. ``readonly`` on Cursor would bar them.
_SHELL_TOOLS: Final[frozenset[str]] = frozenset({"bash", "powershell"})


def _head(source_path: Path, description: str) -> str:
    """Return the opening ``---``, ``name`` and ``description`` lines."""
    name = (field_value(source_path, "name") or source_path.stem).strip().lower()
    return (
        f"---\nname: {_yaml_scalar(name)}\ndescription: {_yaml_scalar(description)}\n"
    )


def _tool_keys(source_path: Path, field_name: str) -> list[str]:
    """Return the normalized tool keys of a comma-separated source tool field."""
    return [_tool_key(item) for item in _agent_scalar_list(source_path, field_name)]


def copilot_tool_aliases(source_path: Path) -> list[str] | None:
    """Return the Copilot ``tools`` allowlist, or ``None`` to leave ``tools`` out.

    With a source grant: the aliases of the granted tools, in source order and
    without repeats. Without one the source inherits every tool except its
    denials, and an omitted Copilot ``tools`` would enable everything, so the
    allowlist the denials imply is written instead: every alias the source does
    not deny. A source with neither a grant nor a denial inherits as written
    (``None``). An alias is dropped when the source denies any tool it covers,
    because the alias would admit that tool.
    """
    granted = _tool_keys(source_path, "tools")
    denied = set(_tool_keys(source_path, "disallowedTools"))
    if not granted and not denied:
        return None
    blocked = {_COPILOT_ALIAS_OF[key] for key in denied if key in _COPILOT_ALIAS_OF}
    candidates = (
        [_COPILOT_ALIAS_OF[key] for key in granted if key in _COPILOT_ALIAS_OF]
        if granted
        else list(_COPILOT_ALIASES)
    )
    aliases: list[str] = []
    for alias in candidates:
        if alias not in blocked and alias not in aliases:
            aliases.append(alias)
    return aliases


def copilot_agent_text(source_path: Path) -> str:
    """Render a source agent as a GitHub Copilot custom agent profile.

    Emits ``name``, ``description`` and, unless the source restricts nothing,
    ``tools`` as a flow list of Copilot aliases (see
    :func:`copilot_tool_aliases`).
    """
    frontmatter = _head(source_path, _agent_description(source_path))
    aliases = copilot_tool_aliases(source_path)
    if aliases is not None:
        frontmatter += f"tools: {json.dumps(aliases)}\n"
    body = _agent_body(source_path).strip()
    return f"{frontmatter}---\n\n{body}\n"


def _holds_shell(source_path: Path) -> bool:
    """Return True when the agent can run commands.

    With a grant: a shell tool must be in it and not denied. Without one the
    agent inherits every tool, so it holds a shell unless every shell tool is
    denied.
    """
    granted = set(_tool_keys(source_path, "tools"))
    denied = set(_tool_keys(source_path, "disallowedTools"))
    if granted:
        return bool((granted - denied) & _SHELL_TOOLS)
    return not denied >= _SHELL_TOOLS


def cursor_is_readonly(source_path: Path) -> bool:
    """Return True when the agent gets ``readonly: true`` on Cursor.

    It must be read-only by the source rule (no file-writing tool after its
    denials) and hold no shell, since Cursor's ``readonly`` also bars commands
    that change state, which would stop a test or lint run.
    """
    return _agent_is_read_only(source_path) and not _holds_shell(source_path)


def cursor_agent_text(source_path: Path) -> str:
    """Render a source agent as a Cursor subagent definition.

    Emits ``name``, ``description`` and ``readonly: true`` for the agents
    :func:`cursor_is_readonly` selects. A read-only agent that keeps a shell is
    left without the flag and its description drops the read-only label, since
    Cursor would not enforce it.
    """
    description = _agent_description(source_path)
    readonly = cursor_is_readonly(source_path)
    if _agent_is_read_only(source_path) and not readonly:
        description = _drop_read_only_claim(description)
    frontmatter = _head(source_path, description)
    if readonly:
        frontmatter += "readonly: true\n"
    body = _agent_body(source_path).strip()
    return f"{frontmatter}---\n\n{body}\n"
