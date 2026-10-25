# SPDX-License-Identifier: MIT

"""Materializer for the opencode harness — renders JSON config.

OpenCode combines every file its ``instructions`` list resolves to into every
session (https://opencode.ai/docs/rules/, retrieved 2026-10-03). The list
therefore names the profile document (the operator's identity and
preferences, and where Apothem's support files are installed) and only the
rules whose source frontmatter sets ``alwaysApply: true``: the core rules and
the rule index. OpenCode scopes no rule by path, so every other rule stays
installed under the support tree and is read on demand: the index names each
rule and when to read it, and a skill or command that needs one cites it.

An entry starting with ``~/`` is expanded against the home directory, and an
absolute entry is matched as a glob on its final segment, so an explicit file
path names exactly that file. A relative entry is resolved against the project
directory, not the config file, which is why every entry is home-anchored.
These semantics were observed at opencode-ai 1.19.0 on 2026-10-14. The
upstream source moved, and the vendor docs do not describe them.
"""

from __future__ import annotations

import json
from string import Template
from typing import Any, Final

from apothem.harnesses._shared import install_driver
from apothem.lib.frontmatter import field_value
from apothem.lib.install_ledger import OwnedEntry
from apothem.lib.profile import coerce_profile
from apothem.lib.profile_projection import mcp_servers_for, render_mcp_opencode
from apothem.lib.propagation import load_manifest

#: The OpenCode configuration directory, relative to the home directory.
CONFIG_DIR: Final[str] = ".config/opencode"

#: The harness root in the home-anchored form OpenCode expands (``~/``).
_HOME_ANCHORED_ROOT: Final[str] = f"~/{CONFIG_DIR}"

#: The single ``instructions`` entry earlier releases wrote: a glob that made
#: OpenCode load every installed rule, path-scoped ones included, at launch.
LEGACY_RULES_GLOB: Final[str] = "~/.config/opencode/.apothem/support/rules/*.md"

#: Rules that earlier releases listed in ``instructions`` by explicit path
#: because their source set ``alwaysApply: true``, and that now load on demand
#: through the rule index. The name list is fixed: the frontmatter no longer
#: says which rules these were.
_DEMOTED_RULES: Final[tuple[str, ...]] = (
    "agent-orchestration",
    "agile-sprints",
    "authoritative-referencing",
    "auto-memory",
    "canonical-layout",
    "clean-room-generation",
    "cognitive-identity",
    "definitiveness",
    "disclosure-ledger",
    "etc-extension",
    "expertise-posture",
    "freshness-facade",
    "host-discovery",
    "interactive-questions",
    "multi-agent-workflow",
    "operational-mandates",
    "option-annotation",
    "persistent-conventions-vigilance",
    "pre-emission-gate",
    "production-ready-prs",
    "source-accessibility",
    "systemic-participation",
    "ten-dimension-check",
    "tool-use-discipline",
)

#: The ``instructions`` entries those releases wrote for :data:`_DEMOTED_RULES`.
RETIRED_ALWAYS_ON_RULES: Final[tuple[str, ...]] = tuple(
    f"{LEGACY_RULES_GLOB.removesuffix('*.md')}{name}.md" for name in _DEMOTED_RULES
)


def always_on_rule_instructions() -> list[str]:
    """Return the ``instructions`` entries for the always-on rules.

    Read at materialize time from the opencode ``rules/`` install entry of the
    canonical propagation manifest (not an install plan a caller may have
    trimmed): its source directory supplies the rules (minus the manifest's
    excluded files), and its target directory, home-anchored, supplies the
    installed location. A rule is listed when its frontmatter sets
    ``alwaysApply: true``. Entries are sorted by file name.

    Raises:
        RuntimeError: When the manifest has no opencode ``rules/`` entry.
    """
    rules = load_manifest()["opencode"]
    entry = next(
        (item for item in rules.install if item.source.rstrip("/") == "rules"), None
    )
    if entry is None:
        raise RuntimeError(
            "propagation manifest has no opencode 'rules/' install entry"
        )
    source_dir = install_driver.resolve_source(entry.source)
    target_dir = Template(entry.target).substitute(HARNESS_ROOT=_HOME_ANCHORED_ROOT)
    names = sorted(
        path.name
        for path in source_dir.glob("*.md")
        if not install_driver._is_excluded_path(path, rules.exclude)
        and (field_value(path, "alwaysApply") or "").strip().lower() == "true"
    )
    return [f"{target_dir.rstrip('/')}/{name}" for name in names]


def profile_document_instruction() -> str:
    """Return the ``instructions`` entry for the projected profile document.

    The install projects the shared profile into
    ``<harness root>/apothem/rules/00-apothem-profile.md``; OpenCode reads no
    other file Apothem writes for it, so without this entry the operator's
    identity, preferences and the support-file locations never reach it.
    """
    return f"{_HOME_ANCHORED_ROOT}/{install_driver.PROFILE_DOCUMENT_RELATIVE}"


def instruction_entries() -> list[str]:
    """Return every ``instructions`` entry: the profile document, then the rules."""
    return [profile_document_instruction(), *always_on_rule_instructions()]


def materialize_native_config(profile: dict[str, Any]) -> str:
    """Render the opencode native configuration from *profile*.

    Renders the ``instructions`` list (see :func:`instruction_entries`) plus
    the profile's MCP inventory into opencode's native ``mcp`` surface.
    Returns a JSON string ready to be written to ``output_path``.
    """
    for_harness = coerce_profile(profile).for_harness("opencode")
    config: dict[str, Any] = {
        "$schema": "https://opencode.ai/config.json",
        "instructions": instruction_entries(),
    }
    mcp = render_mcp_opencode(mcp_servers_for(for_harness))
    if mcp:
        config["mcp"] = mcp
    return json.dumps(config, indent=2, ensure_ascii=False) + "\n"


def retired_entries(profile: dict[str, Any]) -> tuple[OwnedEntry, ...]:
    """Return what earlier releases wrote that this release no longer writes.

    Earlier releases listed :data:`LEGACY_RULES_GLOB` in ``instructions``, and
    later ones listed every ``alwaysApply`` rule by path, among them the
    :data:`RETIRED_ALWAYS_ON_RULES` this release leaves to the rule index. An
    install, update or uninstall over such a config removes those entries; the
    operator's own ``instructions`` entries are kept. A config whose install
    record predates ownership recording cannot tell the retired paths from an
    operator's own, so this list is what removes them.
    """
    del profile  # the retired entries do not depend on the profile
    return tuple(
        OwnedEntry(("instructions",), "item", entry)
        for entry in (LEGACY_RULES_GLOB, *RETIRED_ALWAYS_ON_RULES)
    )
