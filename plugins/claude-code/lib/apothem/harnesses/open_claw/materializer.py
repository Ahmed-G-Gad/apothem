# SPDX-License-Identifier: MIT

"""Materializer for the open-claw harness — renders JSON config.

OpenClaw's user-global config file (``~/.openclaw/openclaw.json``) is JSON with
a vendor schema that rejects unknown top-level keys. Apothem authors one key
there: ``skills.load.extraDirs``, the documented list of extra skill
directories (https://docs.openclaw.ai/tools/skills-config, retrieved
2026-10-24), pointed at the support skills directory the install fills. It
authors nothing else — it knows neither the operator's chosen skill names nor a
file MCP surface — and the rest of the shared cohorts land as individual files
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
    OpenClaw reads that list at the lowest precedence of its skill sources, so
    a skill the operator keeps in a workspace, ``~/.agents/skills`` or
    ``~/.openclaw/skills`` wins over an Apothem skill of the same name. The
    entry goes after the operator's own ``extraDirs`` entries and is the only
    one an uninstall removes. ``agents.defaults.skills`` is a name allowlist the
    operator owns and MCP is managed through the ``openclaw mcp`` CLI rather
    than a config-file block, so Apothem authors neither. The shared cohorts
    land as individual files under ``~/.openclaw/.apothem/support/`` (support
    subtree). No managed-block profile document is projected: OpenClaw
    auto-loads no instruction file, so there is nothing for a single document to
    be wired into — the operator references the other cohorts through the
    vendor's own mechanisms. Returns a JSON string ready to be written to
    ``~/.openclaw/openclaw.json``.
    """
    _ = profile
    config: dict[str, Any] = {"skills": {"load": {"extraDirs": [SKILLS_DIRECTORY]}}}
    return json.dumps(config, indent=2, ensure_ascii=False) + "\n"
