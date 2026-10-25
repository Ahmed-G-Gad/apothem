# SPDX-License-Identifier: MIT

"""Install logic for the gemini-cli harness adapter.

Materializes the apothem convention surface into the operator-supplied
project root. The gemini-cli adapter is project-scope only: user-scope
``~/.gemini/`` is reserved for the antigravity adapter, which owns
``~/.gemini/GEMINI.md``. The gemini-cli adapter avoids the shared
namespace by materialising under ``<project>/`` exclusively.

Vendor-canonical project-context surface is ``<project>/GEMINI.md``
(analogous to project CLAUDE.md per
https://github.com/google-gemini/gemini-cli/blob/main/docs/reference/configuration.md
commit 792654c). The apothem convention cohort propagates under
``<project>/.gemini/{commands,skills,agents}/`` plus
``<project>/.gemini/.apothem/support/rules/`` for Markdown rules and
``<project>/.gemini/.apothem/support/{templates,hooks}/`` for the template and
hook machinery — support material that Gemini CLI does not expose as a matching
native primitive.

The propagation contract is declared in the canonical manifest at
``src/apothem/lib/propagation-manifest.yaml`` under the ``gemini_cli``
key and applied by the shared driver at
``apothem.harnesses._shared.install_driver``. Drift between the
propagation contract and the on-disk install is impossible by
construction: the manifest IS the contract.

The one profile-dependent part of the agent cohort is the per-agent MCP grant:
for each agent the profile's ``agent_mcp_servers`` key lists, the agent's
explicit ``tools`` allowlist gains one ``mcp_<server>_*`` entry per named server.
With no such key every agent is written as the plain conversion.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from apothem.harnesses._shared.install_driver import MaterializationRun
from apothem.harnesses._shared.install_driver_converters import (
    _agent_scalar_list,
    _gemini_tool_names,
)
from apothem.harnesses._shared.install_driver_types import _result, resolve_source
from apothem.harnesses._shared.wrapper_factories import (
    make_project_scope_install,
    make_project_scope_plan,
)
from apothem.lib.claude_agent_mcp import normalize_grants
from apothem.lib.gemini_agent_mcp import (
    ALL_MCP_WILDCARD,
    denied_servers,
    gemini_agent_mcp_grants,
    unaddressable_servers,
)
from apothem.lib.profile import coerce_profile

# Manifest harness key for this adapter.
_HARNESS_NAME: str = "gemini_cli"
# Profile id for this adapter, as keyed under ``harnesses`` in the profile.
_HARNESS_ID: str = "gemini-cli"

_install = make_project_scope_install(
    _HARNESS_NAME,
    error_message="gemini_cli adapter requires --project <path>; CLI must thread it through",
)

plan = make_project_scope_plan(_HARNESS_NAME)


def grant_problems(agents_dir: Path, raw: object) -> list[str]:
    """Return one message per grant that cannot take effect, for the install report.

    A grant names an agent that does not exist, an agent that already reaches
    every MCP server (no ``tools`` list, or one carrying ``mcp_*``), a server the
    agent's own ``disallowedTools`` denies, or a server name Apothem does not
    write as ``mcp_<server>_*``.
    """
    problems: list[str] = []
    for agent, servers in normalize_grants(raw).items():
        path = agents_dir / f"{agent}.md"
        if not path.is_file():
            problems.append(f"agent_mcp_servers names unknown agent '{agent}'; ignored")
            continue
        tools = _gemini_tool_names(path)
        if tools is None or ALL_MCP_WILDCARD in tools:
            problems.append(
                f"agent '{agent}' already reaches every MCP server on Gemini CLI, "
                "so its agent_mcp_servers entry is ignored"
            )
        denied = denied_servers(_agent_scalar_list(path, "disallowedTools"))
        for name in sorted(set(servers) if denied is None else set(servers) & denied):
            problems.append(
                f"agent '{agent}' denies MCP server '{name}' in its own tool "
                "list, and the denial wins, so no grant is written on Gemini CLI"
            )
        for name in unaddressable_servers(servers):
            problems.append(
                f"agent '{agent}': MCP server '{name}' skipped on Gemini CLI: "
                "Apothem writes a grant there only for a name of letters, digits "
                "and '-' (Gemini CLI forbids '_' in server names)"
            )
    return problems


def install(
    output_path: Path,
    profile: dict[str, Any],
    *,
    project: Path | None = None,
    dry_run: bool = False,
) -> MaterializationRun:
    """Install the convention surface into *project*, with the profile's MCP grants.

    Delegates to the manifest-driven project-scope install with the profile's
    ``agent_mcp_servers`` grants active, then reports each grant that cannot take
    effect as a warning on the agents cohort.
    """
    if project is None:
        return _install(output_path, profile, project=project, dry_run=dry_run)
    grants = coerce_profile(profile).for_harness(_HARNESS_ID).get("agent_mcp_servers")
    with gemini_agent_mcp_grants(grants):
        run = _install(output_path, profile, project=project, dry_run=dry_run)
    agents_dir = project / ".gemini" / "agents"
    return run.extend(
        [
            _result("warning", "gemini_agents", agents_dir, message)
            for message in grant_problems(resolve_source("agents"), grants)
        ]
    )
