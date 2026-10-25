# SPDX-License-Identifier: MIT

"""Per-agent MCP grants for the Claude Code engine install.

A Claude Code subagent that declares an explicit ``tools`` list reaches an MCP
tool only when an entry names the server; the documented form is
``mcp__<server>__*``, which admits every tool of that one server
(https://code.claude.com/docs/en/sub-agents, retrieved 2026-10-25). The shared
profile's ``agent_mcp_servers`` key names, per agent, the servers that agent may
call. This module validates those names and renders them into the agent's
``tools`` line, and nothing else:

* An agent the profile does not list is rendered byte-identical to its source,
  so with no setting every agent keeps the plain list and gets no MCP tools.
* An agent with no explicit ``tools`` line inherits every tool already, so an
  appended entry would narrow it; such an agent is left unchanged and reported.
* A re-render over an already-granted line adds nothing, so the result is stable.

The grants reach the renderer through a context variable set by the adapter
for the length of one install pass (the same shape as the install driver's
content tokens), which keeps the renderer a plain ``Path -> str`` function that
the dry-run preview and the install both call. The static plugin tree is
assembled without a profile, so it never enters this context and keeps the
plain list.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Final

from apothem.lib.frontmatter import split_frontmatter

#: An MCP server name a grant may carry, spelled as ``/mcp`` shows it: letters,
#: digits, ``-``, ``_``, ``:`` and ``.``, starting and ending with a letter or
#: digit, at most 64 characters. Claude Code writes ``:`` and ``.`` as ``_`` in
#: tool names, so two adjacent characters from ``_.:`` are rejected: the
#: rendered ``mcp__<server>__*`` entry would otherwise hold a ``__`` that
#: makes the server ambiguous. ``*``, whitespace (a newline included) and every
#: other character are rejected, so a name can never widen the grant to more
#: than one server. The final lookahead is an end-of-string anchor that, unlike
#: ``$``, does not stop before a trailing newline, and reads the same in the
#: ECMA engines that consume the schema. The profile schema carries the same
#: expression; a test pins them equal.
SERVER_NAME_PATTERN: Final[str] = (
    r"^(?!.*[_.:]{2})[A-Za-z0-9](?:[A-Za-z0-9_.:-]{0,62}[A-Za-z0-9])?(?![\s\S])"
)
#: An agent name, as the stem of its file under ``agents/``.
AGENT_NAME_PATTERN: Final[str] = r"^[a-z0-9]+(-[a-z0-9]+)*(?![\s\S])"
#: Characters Claude Code keeps in a tool name's server segment; every other
#: character is written as ``_``.
_TOOL_NAME_UNSAFE: Final[re.Pattern[str]] = re.compile(r"[^A-Za-z0-9_-]")

_SERVER_NAME: Final[re.Pattern[str]] = re.compile(SERVER_NAME_PATTERN)
_AGENT_NAME: Final[re.Pattern[str]] = re.compile(AGENT_NAME_PATTERN)
_TOOLS_LINE: Final[re.Pattern[str]] = re.compile(
    r"^(?P<key>tools[ \t]*:[ \t]*)(?P<value>\S.*?)[ \t]*$", re.MULTILINE
)

_GRANTS: ContextVar[Mapping[str, tuple[str, ...]] | None] = ContextVar(
    "apothem_claude_agent_mcp_grants", default=None
)


def is_valid_server_name(value: object) -> bool:
    """Return True when *value* is a server name a grant may carry."""
    return isinstance(value, str) and _SERVER_NAME.fullmatch(value) is not None


def normalize_grants(raw: object) -> dict[str, tuple[str, ...]]:
    """Return *raw* as ``{agent: sorted unique servers}``, or raise ``ValueError``.

    Empty server lists are dropped. A malformed agent or server name raises, so a
    mapping that skipped schema validation still cannot widen a grant.
    """
    if raw is None:
        return {}
    if not isinstance(raw, Mapping):
        raise ValueError("agent_mcp_servers must map agent names to server lists")
    grants: dict[str, tuple[str, ...]] = {}
    for agent in sorted(raw, key=str):
        servers = raw[agent]
        if not isinstance(agent, str) or _AGENT_NAME.fullmatch(agent) is None:
            raise ValueError(f"invalid agent name in agent_mcp_servers: {agent!r}")
        if isinstance(servers, str) or not isinstance(servers, Iterable):
            raise ValueError(f"agent_mcp_servers[{agent}] must be a list of names")
        names = list(servers)
        for name in names:
            if not is_valid_server_name(name):
                raise ValueError(
                    f"invalid MCP server name for agent {agent}: {name!r} "
                    "(letters, digits, '-', '_', ':' and '.' only, starting and ending "
                    "with a letter or digit, no two of '_', ':', '.' in a row; no '*')"
                )
        if names:
            grants[agent] = tuple(sorted(set(names)))
    return grants


def tool_entries(servers: Iterable[str]) -> list[str]:
    """Return the ``mcp__<server>__*`` entries for *servers*, sorted and unique.

    Each name is rendered the way Claude Code spells it in tool names, with
    ``:`` and ``.`` written as ``_`` (``plugin:a:b`` becomes
    ``mcp__plugin_a_b__*``), so a name pasted from ``/mcp`` matches.
    """
    spelled = {_TOOL_NAME_UNSAFE.sub("_", name) for name in servers}
    return [f"mcp__{name}__*" for name in sorted(spelled)]


@contextmanager
def agent_mcp_grants(raw: object) -> Iterator[None]:
    """Render agents with the grants in *raw* for the length of the block."""
    token = _GRANTS.set(normalize_grants(raw))
    try:
        yield
    finally:
        _GRANTS.reset(token)


def claude_agent_text(source_path: Path) -> str:
    """Render an agent for ``~/.claude/agents/``, adding its granted MCP entries.

    Returns the source text unchanged unless the active grants list this agent
    and its frontmatter has an explicit single-line ``tools`` value. Then the
    ``mcp__<server>__*`` entries not already present are appended, sorted, in
    the quoting the line already uses. Nothing else in the file changes.
    """
    text = source_path.read_text(encoding="utf-8")
    servers = (_GRANTS.get() or {}).get(source_path.stem)
    if not servers:
        return text
    split = split_frontmatter(text)
    if split is None:
        return text
    block, rest = split
    match = _TOOLS_LINE.search(block)
    if match is None:
        return text
    value = match.group("value")
    quote = value[0] if value[0] in "\"'" and value[-1] == value[0] else ""
    inner = value[1:-1] if quote else value
    if inner.lstrip().startswith(("[", "|", ">", "&", "*", "!")):
        return text
    present = [item.strip() for item in inner.split(",") if item.strip()]
    added = [e for e in tool_entries(servers) if e not in present]
    if not added:
        return text
    rendered = quote + ", ".join([*present, *added]) + quote
    new_block = block[: match.start("value")] + rendered + block[match.end("value") :]
    return new_block + rest


def grant_problems(agents_dir: Path, raw: object) -> list[str]:
    """Return one message per grant that cannot take effect, for the install report.

    A grant names an agent that does not exist, or one whose source has no
    explicit ``tools`` line (which inherits every tool and so is not narrowed).
    """
    problems: list[str] = []
    for agent in normalize_grants(raw):
        path = agents_dir / f"{agent}.md"
        if not path.is_file():
            problems.append(f"agent_mcp_servers names unknown agent '{agent}'; ignored")
            continue
        split = split_frontmatter(path.read_text(encoding="utf-8"))
        if split is None or _TOOLS_LINE.search(split[0]) is None:
            problems.append(
                f"agent '{agent}' has no explicit tools list, so it already "
                "inherits every tool; its agent_mcp_servers entry is ignored"
            )
    return problems
