# SPDX-License-Identifier: MIT

"""Materializer for the open-claw harness — renders JSON config.

OpenClaw's user-global config file (``~/.openclaw/openclaw.json``) is JSON with
a vendor schema that rejects unknown top-level keys. Apothem authors one key
there: ``skills.load.extraDirs``, the documented list of extra skill
directories (https://docs.openclaw.ai/tools/skills-config, retrieved
2026-10-24, re-read 2026-11-03), pointed at the support skills directory the
install fills. It authors nothing else — it knows neither the operator's chosen
skill names nor the operator's MCP servers — and the rest of the shared cohorts land as individual files
under the ``~/.openclaw/.apothem/support/`` support subtree instead (see
``materialize_native_config``).
"""

from __future__ import annotations

import json
from typing import Any, Final

#: The harness root in the home-anchored form the vendor docs use (``~/``).
_HOME_ANCHORED_ROOT: Final[str] = "~/.openclaw"

#: The directory the install fills with Apothem's skills, listed under
#: ``skills.load.extraDirs``. It is the manifest's ``skills/`` target for this
#: harness in the home-anchored form; a test keeps the two in step.
SKILLS_DIRECTORY: Final[str] = f"{_HOME_ANCHORED_ROOT}/.apothem/support/skills"


def materialize_native_config(profile: dict[str, Any]) -> str:
    """Render the open-claw native configuration from *profile*.

    Renders ``skills.load.extraDirs`` with one entry, :data:`SKILLS_DIRECTORY`.
    OpenClaw reads that list after the agent's other skill sources, so
    a skill the operator keeps in a workspace, ``~/.agents/skills`` or
    ``~/.openclaw/skills`` wins over an Apothem skill of the same name. The
    entry goes after the operator's own ``extraDirs`` entries and is the only
    one an uninstall removes. The ``agents.defaults.skills`` allowlist and the
    ``agents.entries.<id>.skills`` lists are the operator's, and MCP servers
    live in the ``mcp.servers`` block the operator manages with the
    ``openclaw mcp`` CLI, so Apothem authors neither. The shared cohorts land as
    individual files under ``~/.openclaw/.apothem/support/`` (support subtree),
    and the profile's managed block goes to
    ``~/.openclaw/apothem/rules/00-apothem-profile.md``, which OpenClaw does not
    load. OpenClaw injects ``AGENTS.md`` and five other instruction files from
    each agent's workspace, but the adapter writes none of them (whether it
    should is an open operator decision in the pin), so the operator references
    the other cohorts through the vendor's own mechanisms. Returns a JSON string
    ready to be written to ``~/.openclaw/openclaw.json``.
    """
    _ = profile
    config: dict[str, Any] = {"skills": {"load": {"extraDirs": [SKILLS_DIRECTORY]}}}
    return json.dumps(config, indent=2, ensure_ascii=False) + "\n"
