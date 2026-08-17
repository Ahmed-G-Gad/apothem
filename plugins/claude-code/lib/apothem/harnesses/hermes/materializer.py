# SPDX-License-Identifier: MIT

"""Materializer for the hermes harness — renders YAML config."""

from __future__ import annotations

from typing import Any

import yaml

from apothem.lib.profile import coerce_profile
from apothem.lib.profile_projection import mcp_servers_for, render_mcp_standard


def materialize_native_config(profile: dict[str, Any]) -> str:
    """Render the hermes native configuration from *profile*.

    Renders the profile's MCP inventory under the native ``auxiliary.mcp`` block.
    Apothem does NOT author ``skills.config`` — per the convention pin that key
    is a list of installable registry *packages* (not a directory loader), so a
    directory path there would be misread as a non-existent package. Apothem's
    shared command/skill content lands under ``~/.hermes/.apothem/support/``
    (support subtree) and the profile reaches Hermes through the projected managed-block
    document. Returns a YAML string ready to be written to ``output_path``.
    """
    for_harness = coerce_profile(profile).for_harness("hermes")
    header = (
        "# hermes configuration — managed by Apothem\n"
        "# Do not edit manually; run `apothem update --harness hermes` to regenerate.\n"
    )
    config: dict[str, object] = {}
    mcp = render_mcp_standard(mcp_servers_for(for_harness))
    if mcp:
        config["auxiliary"] = {"mcp": mcp}
    return header + yaml.safe_dump(config, sort_keys=False, allow_unicode=True)
