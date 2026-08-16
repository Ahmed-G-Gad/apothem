# SPDX-License-Identifier: MIT

"""Shared profile→harness projection seam.

The single place that turns a per-harness-resolved canonical profile into the
two surfaces a harness adapter materializes:

- a Markdown *managed-block body* (identity / preferences / rules / seriousness
  / opted-in behaviors) folded into an instruction anchor via the sentinel
  merge primitives, and
- a *native-config fragment* (MCP server inventory + preferences) for the
  adapters that render their own config file and own a file MCP surface.

Every adapter install path routes through :func:`project` so the shared profile
genuinely reaches harness output — the fix for the core-thesis gap where the
profile was validated and then discarded.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apothem.lib.harness_materializer import (
    MarkdownProfileFields,
    extract_markdown_fields,
)

# Human-readable label per enforcement flag, mirroring the schema descriptions.
# Default-off flags emit no prose, so a clean install renders no behaviors block.
_ENFORCEMENT_LABELS: dict[str, str] = {
    "sprints": "Sprint apparatus for non-trivial multi-step work",
    "agent_teams": "Parallel agent-team dispatch for parallelizable work",
    "multitasking": "Parallel multi-task execution",
    "continuous_execution": "Continuous multi-step advancement across natural boundaries",
    "learning_loop": "Continuous-learning capture and pattern promotion",
}

_MANAGED_BLOCK_NOTE = (
    "Managed by Apothem from the shared profile. Edits inside the sentinels are "
    "overwritten on the next `apothem install`; change the shared profile instead."
)


@dataclass(frozen=True)
class ProjectedSurfaces:
    """The surfaces a harness adapter materializes from the shared profile.

    ``managed_block_body`` is the Markdown folded into an instruction anchor
    (identity / preferences / rules / opted-in behaviors / an MCP-server
    reference list). The MCP inventory is *materialized* into native config only
    by the adapters that render their own config file (opencode, qwen_code,
    hermes), via the ``mcp_servers_for`` / ``render_mcp_*`` helpers; for every
    other adapter it appears as instruction-context reference in this block.
    """

    managed_block_body: str


def project(profile_for_harness: dict[str, Any], harness_id: str) -> ProjectedSurfaces:
    """Project a per-harness-resolved profile into the managed-block surface.

    *profile_for_harness* is the output of ``CanonicalProfile.for_harness(...)``:
    a merged dict carrying identity / preferences / rules / seriousness /
    enforcement / mcp_servers. *harness_id* is the public adapter id, reserved
    for harness-specific shaping; the body shape is currently uniform.
    """
    del harness_id  # reserved for per-harness shaping; body is uniform today
    fields = extract_markdown_fields(profile_for_harness)
    mcp_names = sorted((profile_for_harness.get("mcp_servers") or {}).keys())
    return ProjectedSurfaces(
        managed_block_body=_render_managed_block_body(fields, mcp_names),
    )


def _render_managed_block_body(
    fields: MarkdownProfileFields, mcp_names: list[str]
) -> str:
    """Render the managed-block Markdown, omitting fields with no value."""
    lines: list[str] = [
        "# Apothem Shared Profile",
        "",
        _MANAGED_BLOCK_NOTE,
        "",
        "## Operator",
        "",
        f"- **Name:** {fields.name}" if fields.name else "- **Name:** (unset)",
        f"- **Role:** {fields.role}",
    ]
    if fields.email:
        lines.append(f"- **Email:** {fields.email}")
    if fields.website:
        lines.append(f"- **Website:** {fields.website}")
    if fields.github:
        lines.append(f"- **GitHub:** @{fields.github}")
    lines += [
        "",
        "## Preferences",
        "",
        f"- **Primary language:** {fields.language}",
        f"- **Response style:** {fields.style}",
        f"- **Governance seriousness:** {fields.seriousness}",
    ]
    if fields.rules:
        lines += ["", "## Custom Rules", ""]
        lines += [f"- {rule}" for rule in fields.rules]
    opted_in = [
        label
        for key, label in _ENFORCEMENT_LABELS.items()
        if fields.enforcement.get(key)
    ]
    if opted_in:
        lines += ["", "## Opted-in Behaviors", ""]
        lines += [f"- {label}" for label in opted_in]
    if mcp_names:
        lines += [
            "",
            "## MCP Servers",
            "",
            "Configured MCP servers (materialized into the harnesses with a native"
            " MCP config surface; named here as reference for the rest):",
        ]
        lines += [f"- {name}" for name in mcp_names]
    return "\n".join(lines)


def mcp_servers_for(profile_for_harness: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Return the profile's MCP inventory keyed by name (canonical shape).

    The canonical per-server dict carries ``transport`` plus the
    transport-relevant keys (``command``/``args``/``env`` for stdio, ``url`` for
    http-family). Per-harness materializers translate this into their vendor MCP
    shape via the ``render_mcp_*`` helpers below.
    """
    servers = profile_for_harness.get("mcp_servers") or {}
    return {name: dict(spec) for name, spec in servers.items()}


def render_mcp_standard(
    servers: dict[str, dict[str, Any]],
    *,
    variant: str = "standard",
) -> dict[str, dict[str, Any]]:
    """Render MCP servers in the ``mcpServers`` shape (qwen-code, hermes).

    stdio → ``command``/``args``/``env``. The http-family shape depends on
    *variant*:

    - ``"standard"`` (default, e.g. hermes) — emits the spec-standard ``type``
      discriminator plus ``url`` for every http-family transport. ``http`` and
      ``streamable-http`` both render ``type: "http"`` (the current MCP shape);
      a back-compat ``sse`` server renders ``type: "sse"`` but is never the
      default a new server should use — prefer ``streamable-http``.
    - ``"gemini"`` (e.g. qwen-code / gemini-family ``settings.json``) — keeps the
      harness-specific keys: ``streamable-http`` → ``httpUrl`` (the streamable
      endpoint key that surface expects), ``http``/``sse`` → ``url``. No ``type``
      discriminator, matching that surface's native reader.

    ``env`` and ``headers`` (remote auth) pass through verbatim; a ``${VAR}``
    reference in a value is emitted as-is and never resolved here, so no raw
    secret literal is materialized into the native config.
    """
    rendered: dict[str, dict[str, Any]] = {}
    for name, spec in servers.items():
        transport = spec.get("transport", "stdio")
        entry: dict[str, Any] = {}
        if transport == "stdio":
            if spec.get("command"):
                entry["command"] = spec["command"]
            if spec.get("args"):
                entry["args"] = spec["args"]
            if spec.get("env"):
                entry["env"] = spec["env"]
        elif variant == "gemini":
            # Gemini-family native reader: streamable endpoints use httpUrl; the
            # rest use url. No spec ``type`` discriminator on this surface.
            if transport == "streamable-http":
                entry["httpUrl"] = spec.get("url", "")
            else:
                entry["url"] = spec.get("url", "")
            if spec.get("headers"):
                entry["headers"] = spec["headers"]
        else:
            # Spec-standard remote shape: a ``type`` discriminator + ``url``.
            # streamable-http is the modern default and renders type "http";
            # bare sse is back-compat only and never a rendered default.
            entry["type"] = "sse" if transport == "sse" else "http"
            entry["url"] = spec.get("url", "")
            if spec.get("headers"):
                entry["headers"] = spec["headers"]
        rendered[name] = entry
    return rendered


def render_mcp_opencode(
    servers: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Render MCP servers in opencode's ``mcp`` shape.

    stdio → ``{type: local, command: [cmd, *args], environment, enabled}``;
    http-family → ``{type: remote, url, headers, enabled}``. A bare ``sse``
    server is accepted for back-compat and maps to the same ``remote`` shape,
    but ``streamable-http`` is the preferred remote transport.

    ``environment`` and ``headers`` (remote auth) pass through verbatim; a
    ``${VAR}`` reference in a value is emitted as-is and never resolved here, so
    no raw secret literal is materialized into the native config.
    """
    rendered: dict[str, dict[str, Any]] = {}
    for name, spec in servers.items():
        if spec.get("transport", "stdio") == "stdio":
            command = [spec["command"]] if spec.get("command") else []
            command += list(spec.get("args", []))
            entry: dict[str, Any] = {
                "type": "local",
                "command": command,
                "enabled": True,
            }
            if spec.get("env"):
                entry["environment"] = spec["env"]
        else:
            entry = {"type": "remote", "url": spec.get("url", ""), "enabled": True}
            if spec.get("headers"):
                entry["headers"] = spec["headers"]
        rendered[name] = entry
    return rendered


__all__ = [
    "ProjectedSurfaces",
    "mcp_servers_for",
    "project",
    "render_mcp_opencode",
    "render_mcp_standard",
]
