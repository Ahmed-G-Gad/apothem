# SPDX-License-Identifier: MIT

"""Materializer for the hermes harness — renders YAML config."""

from __future__ import annotations

from typing import Any, Final

import yaml

from apothem.lib.install_ledger import OwnedEntry
from apothem.lib.profile import coerce_profile
from apothem.lib.profile_projection import mcp_servers_for, render_mcp_standard

#: The harness root in the home-anchored form the vendor docs use (``~/``).
_HOME_ANCHORED_ROOT: Final[str] = "~/.hermes"

#: The directory the install fills with Apothem's skills, listed under
#: ``skills.external_dirs``. It is the manifest's ``skills/`` target for this
#: harness in the home-anchored form; a test keeps the two in step.
SKILLS_DIRECTORY: Final[str] = f"{_HOME_ANCHORED_ROOT}/.apothem/support/skills"


def materialize_native_config(profile: dict[str, Any]) -> str:
    """Render the hermes native configuration from *profile*.

    Renders ``skills.external_dirs`` with one entry, :data:`SKILLS_DIRECTORY`:
    the documented list of extra skill directories. Hermes lists it last in its
    precedence order (project skills, ``~/.hermes/skills/``,
    ``skills.create_dir``, then ``external_dirs``). The docs reviewed do not
    state which copy loads when two locations hold a skill of the same name; the
    adapter reads the order as earlier wins and writes into no earlier location.
    The entry goes after the operator's own ``external_dirs`` entries and is the
    only one an uninstall removes.

    Also renders the profile's MCP inventory under the top-level ``mcp_servers``
    map Hermes reads its MCP servers from. (``auxiliary.mcp`` is a different
    setting: the auxiliary model Hermes uses for MCP tool dispatch.)
    Apothem does NOT author ``skills.config`` — per the convention pin that key
    stores per-skill settings the operator owns. Apothem's other shared cohorts
    land under ``~/.hermes/.apothem/support/`` (support subtree) and the profile
    reaches Hermes through the projected managed-block document. Returns a YAML
    string ready to be written to ``output_path``.
    """
    for_harness = coerce_profile(profile).for_harness("hermes")
    header = (
        "# hermes configuration — managed by Apothem\n"
        "# Do not edit manually; run `apothem update --harness hermes` to regenerate.\n"
    )
    config: dict[str, object] = {"skills": {"external_dirs": [SKILLS_DIRECTORY]}}
    mcp = render_mcp_standard(mcp_servers_for(for_harness))
    if mcp:
        config["mcp_servers"] = mcp
    return header + yaml.safe_dump(config, sort_keys=False, allow_unicode=True)


def retired_entries(profile: dict[str, Any]) -> tuple[OwnedEntry, ...]:
    """Return what earlier releases wrote under ``auxiliary.mcp`` for *profile*.

    Those releases rendered the MCP inventory into the ``auxiliary.mcp`` model
    slot. An update over such an install removes that value (only while it is
    still exactly what was written) and the ``auxiliary`` mapping if nothing of
    the operator's is left in it.
    """
    for_harness = coerce_profile(profile).for_harness("hermes")
    mcp = render_mcp_standard(mcp_servers_for(for_harness))
    if not mcp:
        return ()
    return (
        OwnedEntry(("auxiliary", "mcp"), "key", mcp),
        OwnedEntry(("auxiliary",), "container"),
    )
