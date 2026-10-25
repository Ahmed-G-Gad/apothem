# SPDX-License-Identifier: MIT

"""Per-agent MCP grants for Gemini CLI subagents.

A Gemini CLI subagent that declares a ``tools`` list reaches the tools of one MCP
server through the wildcard ``mcp_<server>_*``; a subagent with no ``tools`` field
inherits every tool of the parent session
(https://geminicli.com/docs/core/subagents, retrieved 2026-10-25). Every MCP tool
is named ``mcp_{serverName}_{toolName}``, and Gemini CLI splits that name at the
first underscore after ``mcp_``, so a server name holding an underscore cannot be
addressed by a wildcard (https://geminicli.com/docs/tools/mcp-server/, retrieved
2026-10-25). The shared profile's ``agent_mcp_servers`` key names, per agent, the
servers that agent may call; this module renders them into the Gemini ``tools``
allowlist and nothing else:

* An agent the profile does not list is rendered byte-identical to the plain
  conversion, so with no setting no agent gains an MCP tool.
* A server name Gemini CLI cannot address (anything but letters, digits and
  ``-``) is skipped and reported, never rewritten into a different server's name.
* An agent whose Gemini list is absent or already carries ``mcp_*`` reaches every
  MCP server already; such a grant is left out and reported.
* The entries come from the source's own tool grant, never from a rendered file,
  so a re-install adds nothing and the result is stable.

The grants reach the converter through a context variable of their own, set by
the Gemini CLI adapter for the length of one install pass. It is separate from the
Claude Code variable so that one harness's grants never render into another's
output. The name checks are shared with the Claude Code path.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Final

from apothem.lib.claude_agent_mcp import normalize_grants

#: A server name Gemini CLI can address with ``mcp_<server>_*``: letters, digits
#: and ``-``. An underscore would move the point where the policy parser splits
#: ``mcp_<server>_<tool>``; the docs name no other character as safe, so no other
#: character is written.
GEMINI_SERVER_NAME: Final[re.Pattern[str]] = re.compile(
    r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*"
)

#: Gemini's wildcard for every tool of every connected MCP server.
ALL_MCP_WILDCARD: Final[str] = "mcp_*"

_GRANTS: ContextVar[Mapping[str, tuple[str, ...]] | None] = ContextVar(
    "apothem_gemini_agent_mcp_grants", default=None
)


def is_addressable(server: str) -> bool:
    """Return True when Gemini CLI can address *server* with ``mcp_<server>_*``."""
    return GEMINI_SERVER_NAME.fullmatch(server) is not None


def tool_entries(servers: Iterable[str]) -> list[str]:
    """Return the ``mcp_<server>_*`` entries for the addressable *servers*.

    Sorted and unique; a name Gemini CLI cannot address is left out.
    """
    return [
        f"mcp_{name}_*" for name in sorted({s for s in servers if is_addressable(s)})
    ]


@contextmanager
def gemini_agent_mcp_grants(raw: object) -> Iterator[None]:
    """Render Gemini subagents with the grants in *raw* for the length of the block.

    Raises ``ValueError`` for a malformed agent or server name, the same check
    the Claude Code path applies.
    """
    token = _GRANTS.set(normalize_grants(raw))
    try:
        yield
    finally:
        _GRANTS.reset(token)


def with_mcp_entries(agent: str, tools: list[str]) -> list[str]:
    """Return *tools* with *agent*'s granted ``mcp_<server>_*`` entries appended.

    *tools* is the agent's explicit Gemini allowlist. It comes back unchanged
    when the active grants do not list *agent* or it already carries ``mcp_*``.
    """
    servers = (_GRANTS.get() or {}).get(agent)
    if not servers or ALL_MCP_WILDCARD in tools:
        return tools
    return [*tools, *(e for e in tool_entries(servers) if e not in tools)]


def unaddressable_servers(servers: Iterable[str]) -> list[str]:
    """Return the names in *servers* Gemini CLI cannot address, sorted."""
    return sorted({s for s in servers if not is_addressable(s)})
