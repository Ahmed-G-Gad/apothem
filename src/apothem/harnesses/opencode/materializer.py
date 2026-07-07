# SPDX-License-Identifier: MIT

"""Materializer for the opencode harness — renders JSON config."""

from __future__ import annotations

import json
from typing import Any

from apothem.lib.profile import coerce_profile
from apothem.lib.profile_projection import mcp_servers_for, render_mcp_opencode


def materialize_native_config(profile: dict[str, Any]) -> str:
    """Render the opencode native configuration from *profile*.

    Renders the apothem instructions pointer plus the profile's MCP inventory
    into opencode's native ``mcp`` surface. Returns a JSON string ready to be
    written to ``output_path``.
    """
    for_harness = coerce_profile(profile).for_harness("opencode")
    config: dict[str, Any] = {
        "$schema": "https://opencode.ai/config.json",
        "instructions": [
            "~/.config/opencode/.apothem/support/rules/*.md",
        ],
    }
    mcp = render_mcp_opencode(mcp_servers_for(for_harness))
    if mcp:
        config["mcp"] = mcp
    return json.dumps(config, indent=2, ensure_ascii=False) + "\n"
