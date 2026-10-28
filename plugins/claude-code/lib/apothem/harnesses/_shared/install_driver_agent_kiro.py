# SPDX-License-Identifier: MIT

"""Native subagent renderer for Kiro (IDE 1.0 and CLI V3 Markdown agents).

Kiro reads a custom agent from ``<project>/.kiro/agents/<name>.md``: a Markdown
file whose YAML frontmatter carries the configuration and whose body is the
agent's system prompt. The same fields are available in a ``.json`` file, and
the Markdown format is new in IDE 1.0 and CLI V3 (``kiro-cli --v3``), which this
renderer targets (https://kiro.dev/docs/custom-agents/ and
https://kiro.dev/docs/custom-agents/configuration-reference/, retrieved
2026-10-27). The agent name is optional and defaults to the file name.

Kiro restricts tools with ``tools``, a list of *selectors* that decide which
tools the agent sees: the category tags ``read``, ``write``, ``shell``, ``web``
and ``subagent``, plus ``@builtin``, ``@mcp``, ``@<server>`` and ``*``. A second
key, ``excludedTools``, removes tools ``tools`` would allow, and authorization is
a separate ``permissions`` block. The vendor example writes the list in flow style,
``tools: ["read", "write", "shell"]``, which is how this renderer writes it.

The source ``tools`` / ``disallowedTools`` pair becomes one ``tools`` allowlist of
category tags: ``Read``, ``Glob`` and ``Grep`` are ``read``; ``Write``, ``Edit``,
``MultiEdit`` and ``NotebookEdit`` are ``write``; ``Bash`` and ``PowerShell`` are
``shell``; ``WebSearch`` and ``WebFetch`` are ``web``; ``Agent`` and ``Task`` are
``subagent``. A source tool outside that table has no Kiro tag (``TodoWrite``,
``Monitor``, ``Artifact``, ``TaskCreate``, ``TaskUpdate``, an ``mcp__`` entry) and
is left out. The tags keep the order of first appearance in the source grant.
A source tool pattern such as ``Bash(git status)`` has no form in a tag list: in a
grant it is left out (a narrower agent), and in a denial it denies the whole tool.

A restriction the source states is never relaxed. A tag is left out of the
allowlist when the source denies any tool the tag covers, so a grant of ``Write``
with ``Edit`` denied loses ``write`` altogether instead of keeping a tool the
source forbids. A grant that loses every tag is written as ``tools: []`` rather
than dropped. A source that denies tools without granting any is compiled the
same way from the five category tags, and a source with neither field leaves
``tools`` out, as the source does.

The renderer writes a fresh frontmatter and copies the body unchanged. It writes
no ``model`` (the agent then runs on the model Kiro selects, and an id Kiro's
model service does not know can fail the first prompt), no ``permissions``,
``excludedTools``, ``resources``, ``mcpServers``, ``hooks``, ``prompt``,
``includeMcpJson``, ``includePowers`` or ``welcomeMessage``, no CLI 2.x
``allowedTools`` or ``toolsSettings`` (V3 skips a JSON profile that has
``allowedTools`` and no ``permissions`` block),
and none of Apothem's ``maxTurns``, ``version``, ``updated`` and ``portability``
metadata. The profile's ``agent_mcp_servers`` key is not applied here.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final

from .install_driver_agent_copilot_cursor import _head
from .install_driver_converters import (
    _agent_body,
    _agent_description,
    _agent_scalar_list,
    _agent_tool_names,
    _tool_key,
)

#: Kiro category tags in the order the vendor lists them; a source with denials and
#: no grant starts its allowlist from all of them.
_KIRO_TAGS: Final[tuple[str, ...]] = ("read", "write", "shell", "web", "subagent")

#: Source tool lookup key (lower case, no ``-`` or ``_``) to the Kiro category tag
#: that covers it. MultiEdit, NotebookEdit, PowerShell and Task are listed so that
#: a source denial of one of them still blocks the tag it belongs to. A source name
#: outside this table has no Kiro tag.
_KIRO_TAG_OF: Final[dict[str, str]] = {
    "read": "read",
    "glob": "read",
    "grep": "read",
    "write": "write",
    "edit": "write",
    "multiedit": "write",
    "notebookedit": "write",
    "bash": "shell",
    "powershell": "shell",
    "websearch": "web",
    "webfetch": "web",
    "agent": "subagent",
    "task": "subagent",
}


def kiro_tool_tags(source_path: Path) -> list[str] | None:
    """Return the Kiro ``tools`` allowlist, or ``None`` to leave ``tools`` out.

    With a source grant: the tags of the granted tools, in source order and
    without repeats. Without one the source inherits every tool except its
    denials, so the allowlist the denials imply is written instead: every
    category tag the source does not deny. A source with neither a grant nor a
    denial inherits as written (``None``). A tag is dropped when the source denies
    any tool it covers, because the tag would admit that tool.
    """
    has_grant = bool(_agent_scalar_list(source_path, "tools"))
    denied = _agent_scalar_list(source_path, "disallowedTools")
    if not has_grant and not denied:
        return None
    blocked = {
        _KIRO_TAG_OF[key] for key in map(_tool_key, denied) if key in _KIRO_TAG_OF
    }
    candidates = (
        _agent_tool_names(source_path, "tools", _KIRO_TAG_OF)
        if has_grant
        else list(_KIRO_TAGS)
    )
    return [tag for tag in candidates if tag not in blocked]


def kiro_agent_text(source_path: Path) -> str:
    """Render a source agent as a Kiro custom agent file (Markdown, V3).

    Emits ``name``, ``description`` and, unless the source restricts nothing,
    ``tools`` as a flow list of Kiro category tags (see :func:`kiro_tool_tags`).
    """
    frontmatter = _head(source_path, _agent_description(source_path))
    tags = kiro_tool_tags(source_path)
    if tags is not None:
        frontmatter += f"tools: {json.dumps(tags)}\n"
    body = _agent_body(source_path).strip()
    return f"{frontmatter}---\n\n{body}\n"
