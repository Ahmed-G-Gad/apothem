# SPDX-License-Identifier: MIT

"""Native subagent renderers for harnesses that take comma-string tool fields.

CodeBuddy and Trae read an agent file much like the source one: Markdown, YAML
frontmatter between ``---`` lines, the body as the system prompt, ``name`` and
``description`` required, and ``tools`` and ``disallowedTools`` as comma-separated
strings (not YAML lists). What differs is the tool vocabulary each accepts and
the one extra key CodeBuddy documents:

- CodeBuddy (``<project>/.codebuddy/agents/<name>.md``) documents ``name``,
  ``description``, ``tools``, ``disallowedTools`` and ``maxTurns`` among its
  keys, so the source turn limit carries over natively
  (https://www.codebuddy.ai/docs/cli/sub-agents, retrieved 2026-10-27). Its
  sub-agents page points to the Settings page for the complete tool list, and
  that page's "Tools Available to CodeBuddy" table names AskUserQuestion, Bash,
  Edit, ExitPlanMode, Glob, Grep, LSP, MultiEdit, NotebookEdit, Read, Skill,
  SlashCommand, Task, TaskCreate, TaskGet, TaskList, TaskOutput, TaskStop,
  TaskUpdate, WebFetch, WebSearch and Write
  (https://www.codebuddy.ai/docs/cli/settings, retrieved 2026-10-28). The
  sub-agents page also names an ``Agent`` tool.
- Trae (``<project>/.trae/agents/<name>.md``) documents ``name``,
  ``description``, ``model``, ``tools``, ``disallowedTools`` and ``mcpServers``,
  with a ``disallowedTools`` that wins over ``tools``, and no turn limit
  (https://docs.trae.ai/ide/subagents, retrieved 2026-10-27). Its tool
  vocabulary is Bash, Edit, Glob, Grep, Read, Skill, TodoWrite, WebFetch,
  WebSearch, Write and LSP.

Both renderers write a fresh frontmatter from the source rather than copying it:
``version``, ``updated`` and ``portability`` are Apothem metadata neither vendor
lists, and a source ``maxTurns`` rationale comment has no place in a vendor
file. The body is copied unchanged. No ``model`` key is written, so each agent
runs on the model the harness selects. The profile's ``agent_mcp_servers`` key
is not applied here (a follow-up); a source tool name outside the vocabulary,
an ``mcp__`` entry included, is left out.

A tool the source denies stays denied: the harness has a native deny list, so no
read-only claim is rewritten. A denial with a pattern, such as ``Bash(rm *)``,
has no form in either list, so it denies the whole tool. A grant is never
widened: a granted tool with a pattern, such as ``Bash(git status)``, is left
out instead of being widened to the whole tool. When the source grants tools but
none is in the vocabulary, the file carries an empty ``tools`` string instead of
omitting the key, because an omitted ``tools`` inherits every tool.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from apothem.lib.frontmatter import field_value

from .install_driver_agent_kimi_devin import _denied_names
from .install_driver_converters import (
    _agent_body,
    _agent_description,
    _agent_scalar_list,
    _agent_tool_names,
    _yaml_scalar,
)

#: CodeBuddy tool names as its Settings page spells them (the "Tools Available
#: to CodeBuddy" table), plus ``Agent``, which its sub-agents page names. A source
#: name outside this set (PowerShell, Monitor, Artifact, TodoWrite) is left out.
_CODEBUDDY_TOOLS: Final[tuple[str, ...]] = (
    "Read",
    "Grep",
    "Glob",
    "Bash",
    "Edit",
    "Write",
    "WebFetch",
    "WebSearch",
    "Agent",
    "AskUserQuestion",
    "ExitPlanMode",
    "LSP",
    "MultiEdit",
    "NotebookEdit",
    "Skill",
    "SlashCommand",
    "Task",
    "TaskCreate",
    "TaskGet",
    "TaskList",
    "TaskOutput",
    "TaskStop",
    "TaskUpdate",
)

#: Trae subagent tool names as its Subagents page spells them (a different
#: vocabulary from the hook matcher names, where Bash is RunCommand). A source
#: name outside this set (MultiEdit, NotebookEdit, PowerShell, Monitor, Agent,
#: Artifact, TaskCreate, TaskUpdate) is left out.
_TRAE_TOOLS: Final[tuple[str, ...]] = (
    "Bash",
    "Edit",
    "Glob",
    "Grep",
    "Read",
    "Skill",
    "TodoWrite",
    "WebFetch",
    "WebSearch",
    "Write",
    "LSP",
)


def _vocabulary_map(names: tuple[str, ...]) -> dict[str, str]:
    """Return the lookup key (lower case) to native spelling of *names*."""
    return {name.lower(): name for name in names}


_CODEBUDDY_TOOL_MAP: Final[dict[str, str]] = _vocabulary_map(_CODEBUDDY_TOOLS)
_TRAE_TOOL_MAP: Final[dict[str, str]] = _vocabulary_map(_TRAE_TOOLS)


def _tool_lines(source_path: Path, vocabulary: dict[str, str]) -> str:
    """Return the ``tools`` and ``disallowedTools`` lines for one agent.

    Each is a double-quoted comma-separated string in the source order, holding
    only names in *vocabulary*. A granted name must match the vocabulary exactly,
    so a patterned grant (``Bash(git status)``) is left out, while a patterned
    denial (``Bash(rm *)``) denies the whole tool. A field with nothing left is
    omitted, except a grant that had names but lost them all, which stays as an
    empty string so the agent is not handed every tool.
    """
    lines = ""
    granted = _agent_tool_names(source_path, "tools", vocabulary)
    if granted:
        lines += f"tools: {_yaml_scalar(', '.join(granted))}\n"
    elif _agent_scalar_list(source_path, "tools"):
        lines += 'tools: ""\n'
    denied = _denied_names(source_path, vocabulary)
    if denied:
        lines += f"disallowedTools: {_yaml_scalar(', '.join(denied))}\n"
    return lines


def _head(source_path: Path) -> str:
    """Return the opening ``---``, ``name`` and ``description`` lines."""
    name = (field_value(source_path, "name") or source_path.stem).strip().lower()
    description = _agent_description(source_path)
    return (
        f"---\nname: {_yaml_scalar(name)}\ndescription: {_yaml_scalar(description)}\n"
    )


def codebuddy_agent_text(source_path: Path) -> str:
    """Render a source agent as a CodeBuddy subagent definition.

    Emits ``name``, ``description``, ``tools``, ``disallowedTools`` and
    ``maxTurns``. The turn limit is written only when the source holds a whole
    number.
    """
    frontmatter = _head(source_path) + _tool_lines(source_path, _CODEBUDDY_TOOL_MAP)
    max_turns = (field_value(source_path, "maxTurns") or "").strip()
    if max_turns.isdigit():
        frontmatter += f"maxTurns: {int(max_turns)}\n"
    body = _agent_body(source_path).strip()
    return f"{frontmatter}---\n\n{body}\n"


def trae_agent_text(source_path: Path) -> str:
    """Render a source agent as a Trae subagent definition.

    Emits ``name``, ``description``, ``tools`` and ``disallowedTools``; Trae
    documents no turn limit, so ``maxTurns`` is left out.
    """
    frontmatter = _head(source_path) + _tool_lines(source_path, _TRAE_TOOL_MAP)
    body = _agent_body(source_path).strip()
    return f"{frontmatter}---\n\n{body}\n"
