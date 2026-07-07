# SPDX-License-Identifier: MIT

"""Materializer for the open-claw harness — renders JSON config.

OpenClaw's user-global config file (``~/.openclaw/openclaw.json``) is JSON with
a vendor schema that rejects unknown top-level keys. Apothem authors no config
keys here — it knows neither the operator's chosen skill names nor a file MCP
surface — so the materializer emits an empty object; the projected managed-block
profile document lands under the ``~/.openclaw/.apothem/support/`` support subtree
instead (see ``materialize_native_config``).
"""

from __future__ import annotations

import json
from typing import Any


def materialize_native_config(profile: dict[str, Any]) -> str:
    """Render the open-claw native configuration from *profile*.

    OpenClaw exposes skills as an allowlist of NAMES under
    ``agents.defaults.skills`` (the earlier ``skills.load.extraDirs`` directory
    loader was refuted) and manages MCP through the ``openclaw mcp`` CLI, not a
    config-file block. Apothem knows neither the operator's chosen skill names
    nor a file MCP surface here, so it authors no config keys — a directory path
    in a name-allowlist would be misread as a (non-existent) skill name.
    Apothem's shared command/skill content lands under ``~/.openclaw/.apothem/support/``
    (support subtree); the projected managed-block profile document is written
    there as operator reference (OpenClaw has no auto-loaded instruction file,
    so the operator wires it via the vendor's own mechanisms). Returns a JSON
    string ready to be written to ``~/.openclaw/openclaw.json``.
    """
    _ = profile
    config: dict[str, Any] = {}
    return json.dumps(config, indent=2, ensure_ascii=False) + "\n"
