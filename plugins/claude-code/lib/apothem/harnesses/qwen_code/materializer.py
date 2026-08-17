# SPDX-License-Identifier: MIT

"""Materializer for the qwen-code harness — renders JSON settings config.

Qwen Code's canonical user configuration surface is ``~/.qwen/settings.json``.
Apothem also installs ``~/.qwen/QWEN.md`` as the user-scope context anchor and
places commands, skills, and subagents in Qwen Code's native discovery
directories. Non-native support cohorts stay under ``~/.qwen/.apothem/support/``. This
materializer renders only documented settings keys and lifecycle hook entries.

Each hook command leads with an absolute CPython >= 3.10 path resolved by
:func:`apothem.lib.python_resolver.resolve_python_bin` at materialize time,
never a bare ``python`` name: a bare ``python`` fails to spawn on a python3-only
POSIX host, which silently disables every installed guard.
"""

from __future__ import annotations

import json
from typing import Any

from apothem.lib.profile import coerce_profile
from apothem.lib.profile_projection import mcp_servers_for, render_mcp_standard
from apothem.lib.python_resolver import resolve_python_bin

# Per-event hook-timeout budgets (milliseconds), keyed to the hook-event classes
# in rules/performance-discipline.md §1: PreToolUse = 10s, SessionStart /
# PreCompact / PostCompact = 30s, Stop = 60s. Named here so the budgets are
# documented intent rather than repeated magic numbers (M13.10).
_PRETOOLUSE_TIMEOUT_MS = 10_000
_SESSION_TIMEOUT_MS = 30_000
_STOP_TIMEOUT_MS = 60_000


def _hook(command: str, timeout: int, description: str) -> dict[str, object]:
    """Return one qwen-native hook entry: a ``command``-type handler.

    Wraps *command* with its *timeout* budget (milliseconds) and a
    plain-language *description*, in the shape qwen's ``settings.json`` hook
    reader expects. Called once per handler by :func:`_qwen_hooks`.
    """
    return {
        "type": "command",
        "command": command,
        "timeout": timeout,
        "description": description,
    }


def _dispatch(python_bin: str, event_name: str, message_name: str | None = None) -> str:
    """Render a hook command that invokes the installed dispatcher by path.

    *python_bin* is the absolute path to a real CPython >= 3.10 resolved by
    :func:`resolve_python_bin`, emitted as the command's leading token instead
    of a bare ``python`` name. A bare ``python`` fails to spawn on a python3-only
    POSIX host (where only ``python3`` exists), silently disabling every installed
    guard; an absolute interpreter path resolves on such hosts and on
    py-launcher-less hosts alike. The ``${HARNESS_ROOT}`` token in the script
    path resolves at install time (the adapter's install step renders content
    tokens before writing), so the command points at the dispatcher materialized
    under ``~/.qwen/.apothem/support/hooks/`` without requiring an importable
    ``apothem`` package on the host.
    """
    parts = [
        python_bin,
        '"${HARNESS_ROOT}/.apothem/support/hooks/dispatch.py"',
        event_name,
    ]
    if message_name:
        parts.append(message_name)
    return " ".join(parts)


def _qwen_hooks(python_bin: str) -> dict[str, list[dict[str, object]]]:
    """Return qwen's native hook-event wiring — the static event → matcher →
    timeout table for the installed dispatcher. Each event's timeout uses its
    budget-class constant (``_SESSION_TIMEOUT_MS`` / ``_PRETOOLUSE_TIMEOUT_MS`` /
    ``_STOP_TIMEOUT_MS``) per ``rules/performance-discipline.md`` §1.
    """
    return {
        "SessionStart": [
            {
                "hooks": [
                    _hook(
                        _dispatch(python_bin, "SessionStart"),
                        _SESSION_TIMEOUT_MS,
                        "Initialize Apothem session posture.",
                    ),
                ],
            },
        ],
        "PreToolUse": [
            {
                "matcher": "^Bash$",
                "hooks": [
                    _hook(
                        _dispatch(python_bin, "PreToolUse", "pretooluse-bash"),
                        _PRETOOLUSE_TIMEOUT_MS,
                        "Validate shell command safety and isolation.",
                    ),
                    _hook(
                        _dispatch(
                            python_bin, "PreToolUse", "pretooluse-bash-plan-guard"
                        ),
                        _PRETOOLUSE_TIMEOUT_MS,
                        "Enforce plans locality on shell redirections.",
                    ),
                    _hook(
                        _dispatch(python_bin, "PreToolUse", "pretooluse-eval-guard"),
                        _PRETOOLUSE_TIMEOUT_MS,
                        "Flag unsafe dynamic evaluation or deserialization.",
                    ),
                ],
                "sequential": True,
            },
            {
                "matcher": "WriteFile|Edit",
                "hooks": [
                    _hook(
                        _dispatch(python_bin, "PreToolUse", "pretooluse-write"),
                        _PRETOOLUSE_TIMEOUT_MS,
                        "Validate write target and content.",
                    ),
                    _hook(
                        _dispatch(
                            python_bin, "PreToolUse", "pretooluse-write-header-guard"
                        ),
                        _PRETOOLUSE_TIMEOUT_MS,
                        "Inject the authorship header when required.",
                    ),
                    _hook(
                        _dispatch(
                            python_bin, "PreToolUse", "pretooluse-write-plan-guard"
                        ),
                        _PRETOOLUSE_TIMEOUT_MS,
                        "Enforce plans locality on the target path.",
                    ),
                    _hook(
                        _dispatch(
                            python_bin, "PreToolUse", "pretooluse-dependency-guard"
                        ),
                        _PRETOOLUSE_TIMEOUT_MS,
                        "Flag unpinned or untrusted dependency additions.",
                    ),
                    _hook(
                        _dispatch(python_bin, "PreToolUse", "pretooluse-eval-guard"),
                        _PRETOOLUSE_TIMEOUT_MS,
                        "Flag unsafe dynamic evaluation or deserialization.",
                    ),
                ],
                "sequential": True,
            },
        ],
        "PreCompact": [
            {
                "matcher": "*",
                "hooks": [
                    _hook(
                        _dispatch(python_bin, "PreCompact", "precompact"),
                        _SESSION_TIMEOUT_MS,
                        "Externalize state before context compression.",
                    ),
                ],
            },
        ],
        "PostCompact": [
            {
                "matcher": "*",
                "hooks": [
                    _hook(
                        _dispatch(python_bin, "PostCompact", "postcompact"),
                        _SESSION_TIMEOUT_MS,
                        "Restore state from durable files after compaction.",
                    ),
                ],
            },
        ],
        "Stop": [
            {
                "hooks": [
                    _hook(
                        _dispatch(python_bin, "Stop", "stop"),
                        _STOP_TIMEOUT_MS,
                        "Finalize the session and externalize state.",
                    ),
                ],
            },
        ],
    }


def materialize_native_config(profile: dict[str, Any]) -> str:
    """Render the qwen-code native configuration from *profile*.

    Renders the QWEN.md context pointer, the hook wiring, and the profile's MCP
    inventory into qwen's native ``mcpServers`` surface. Returns a JSON string
    ready to be written to ``output_path``.
    """
    for_harness = coerce_profile(profile).for_harness("qwen-code")
    python_bin = resolve_python_bin().as_posix()
    config: dict[str, Any] = {
        "context": {
            "fileName": "QWEN.md",
        },
        "hooks": _qwen_hooks(python_bin),
    }
    # Qwen Code's settings.json reader uses the gemini-family key set (httpUrl
    # for the streamable endpoint), so render with that variant to keep the
    # native surface intact.
    mcp = render_mcp_standard(mcp_servers_for(for_harness), variant="gemini")
    if mcp:
        config["mcpServers"] = mcp
    return json.dumps(config, indent=2, ensure_ascii=False) + "\n"
