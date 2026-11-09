# SPDX-License-Identifier: MIT

"""Materializer for the open-claw harness — renders JSON config.

OpenClaw's user-global config file (``~/.openclaw/openclaw.json``) is JSON with
a vendor schema that rejects unknown top-level keys. Apothem authors two
entries there:

- ``skills.load.extraDirs``, the documented list of extra skill directories
  (https://docs.openclaw.ai/tools/skills-config, retrieved 2026-10-24, re-read
  2026-11-03), pointed at the support skills directory the install fills.
- One path in the bundled ``bootstrap-extra-files`` hook's entry under
  ``hooks.internal.entries`` (https://docs.openclaw.ai/automation/hooks/bundled-hooks,
  read 2026-11-08), naming the Apothem rules file each agent workspace gets
  (:data:`RULES_FILE_RELATIVE`). OpenClaw resolves the path in the workspace of
  the session it builds a prompt for, so one entry serves every workspace.

It authors nothing else: it knows neither the operator's chosen skill names
nor the operator's MCP servers, and it never writes ``hooks.internal.enabled``.
The rest of the shared cohorts land as individual files under the
``~/.openclaw/.apothem/support/`` support subtree instead.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Final

#: The harness root in the home-anchored form the vendor docs use (``~/``).
_HOME_ANCHORED_ROOT: Final[str] = "~/.openclaw"

#: The directory the install fills with Apothem's skills, listed under
#: ``skills.load.extraDirs``. It is the manifest's ``skills/`` target for this
#: harness in the home-anchored form; a test keeps the two in step.
SKILLS_DIRECTORY: Final[str] = f"{_HOME_ANCHORED_ROOT}/.apothem/support/skills"

#: Where the Apothem rules file sits in each agent workspace. The hook loads
#: only the six bootstrap file names, and the name it is loaded under decides
#: which sessions see it: a file named ``AGENTS.md`` reaches main, cron and
#: sub-agent sessions alike. It is never the workspace's own ``AGENTS.md``,
#: which OpenClaw seeds and the agent edits.
RULES_FILE_RELATIVE: Final[str] = "apothem/AGENTS.md"

#: The bundled OpenClaw hook that loads extra bootstrap files.
HOOK_NAME: Final[str] = "bootstrap-extra-files"

#: The hook's list keys, in the order it reads them: the first non-empty one
#: wins and the others are ignored, so they are alternatives, not one list.
PATTERN_KEYS: Final[tuple[str, ...]] = ("paths", "patterns", "files")

#: Where the hook entry sits in ``openclaw.json``.
ENTRY_PATH: Final[tuple[str, ...]] = ("hooks", "internal", "entries", HOOK_NAME)


@dataclass(frozen=True)
class Registration:
    """What the install writes under the hook's entry, or why it writes nothing.

    ``entry`` is the mapping rendered at :data:`ENTRY_PATH`; ``None`` means the
    install leaves the hook alone and ``reason`` says why (shown to the
    operator as a warning).
    """

    entry: dict[str, Any] | None
    reason: str | None = None


#: The registration an install renders into a config with no hook settings.
FRESH_REGISTRATION: Final[Registration] = Registration(
    {"enabled": True, "paths": [RULES_FILE_RELATIVE]}
)


def _mapping(value: object, key: str) -> dict[str, Any]:
    """Return ``value[key]`` when both are mappings, else an empty mapping."""
    if isinstance(value, dict):
        child = value.get(key)
        if isinstance(child, dict):
            return child
    return {}


def _operator_items(entry: dict[str, Any], key: str) -> list[object]:
    """Return the operator's items under *key* in the hook entry."""
    items = entry.get(key)
    if not isinstance(items, list):
        return []
    return [item for item in items if item != RULES_FILE_RELATIVE]


#: The entry an operator adds by hand to a config Apothem cannot rewrite.
MANUAL_ENTRY: Final[str] = (
    '"hooks": { "internal": { "entries": { "bootstrap-extra-files": '
    f'{{ "enabled": true, "paths": ["{RULES_FILE_RELATIVE}"] }} }} }} }}'
)


def plan_registration(
    existing: object,
    *,
    apothem_entry: bool,
    fits: bool = True,
    editable: bool = True,
) -> Registration:
    """Return how to register the rules file in the operator's *existing* config.

    See :func:`_plan_editable` for the rules. When *editable* is False (the
    file holds comments or other JSON5 syntax, which a rewrite would lose),
    nothing Apothem would add or take out may change, so an entry that already
    names the path is rendered exactly as the file holds it, whatever else
    applies, and any change the rules call for is left to the operator in the
    warning; a missing entry is not added and the warning says what to add.
    """
    planned = _plan_editable(existing, apothem_entry=apothem_entry, fits=fits)
    if editable:
        return planned
    current = _mapping(
        _mapping(_mapping(existing, "hooks"), "internal"), "entries"
    ).get(HOOK_NAME)
    current_key = _listing_key(current)
    if current_key is not None and isinstance(current, dict):
        held = (
            Registration(dict(current))
            if apothem_entry
            else Registration({current_key: [RULES_FILE_RELATIVE]})
        )
        if planned.entry is None:
            return Registration(
                held.entry,
                f"{planned.reason} openclaw.json holds comments or other JSON5 "
                "syntax, which Apothem cannot keep when it rewrites the file, so "
                f'it leaves "{RULES_FILE_RELATIVE}" in the `{current_key}` list of '
                f"hooks.internal.entries.{HOOK_NAME}; remove it there by hand.",
            )
        return held
    if planned.entry is None:
        return planned
    existing_entry = current if isinstance(current, dict) else None
    key = next(iter(planned.entry.keys() - {"enabled"}), "paths")
    if existing_entry is not None and _operator_items(existing_entry, key):
        how = (
            f'add "{RULES_FILE_RELATIVE}" to the `{key}` list of '
            f"hooks.internal.entries.{HOOK_NAME}"
        )
    elif existing_entry is not None:
        how = (
            f'add `paths: ["{RULES_FILE_RELATIVE}"]` to '
            f"hooks.internal.entries.{HOOK_NAME}"
        )
    else:
        how = (
            f"add this entry, merging it into the hooks block if the file has one "
            f"(a second hooks key would replace the first): {MANUAL_ENTRY}"
        )
    return Registration(
        None,
        "openclaw.json holds comments, a byte-order mark or other JSON5 syntax, which Apothem cannot "
        "keep when it rewrites the file, so the Apothem rules file is written but "
        f"not registered. In openclaw.json, {how}.",
    )


def _plan_editable(
    existing: object, *, apothem_entry: bool, fits: bool
) -> Registration:
    """Return how to register the rules file in a config Apothem may rewrite.

    *existing* is the parsed ``openclaw.json`` (anything else reads as an empty
    config). *apothem_entry* is True when the install record says Apothem
    created the hook entry, so it counts as absent here. *fits* is False when
    the rules file fits no workspace within OpenClaw's limits, so no file is
    written and nothing is registered. The rules, from
    OpenClaw's hooks configuration page and ``src/hooks/configured.ts``:

    - ``hooks.internal.enabled: false`` turns every internal hook off. That is
      the operator's choice, so the install leaves it and registers nothing.
    - An entry set to ``enabled: false`` is also left alone, even one Apothem
      created: Apothem never writes ``false``, so the operator set it. An
      update then removes only Apothem's path, and the operator's setting
      stays (the install record keeps an edited key).
    - With ``hooks.internal.enabled: true`` and no named entry or extra hook
      directory, OpenClaw loads every eligible hook. A first named entry turns
      that into an allowlist of the named hooks, which would switch the
      operator's other hooks off, so the install registers nothing.
    - The hook reads the first non-empty list of ``paths``, ``patterns`` and
      ``files``. The path joins the list the operator already uses, so it never
      hides theirs; with none, it goes under ``paths``.
    - ``enabled: true`` is written only in an entry Apothem creates: an entry
      without ``enabled: false`` is already on.
    """
    if not fits:
        return Registration(
            None,
            "the Apothem rules file fits no workspace within OpenClaw's limits "
            "(bootstrapMaxChars per file, bootstrapTotalMaxChars in total), so it "
            "is not written or registered; the warning for each workspace says "
            "which limit. Shorten the profile's custom rules or those files, or "
            "raise the limit, then run `apothem update --harness open-claw`.",
        )
    internal = _mapping(_mapping(existing, "hooks"), "internal")
    if internal.get("enabled") is False:
        return Registration(
            None,
            "hooks.internal.enabled is false in openclaw.json, so OpenClaw runs no "
            "internal hook; the Apothem rules file is written but not loaded. Remove "
            "that setting and run `apothem update --harness open-claw` to load it.",
        )
    entries = _mapping(internal, "entries")
    current = entries.get(HOOK_NAME)
    operator_entry = (
        current if isinstance(current, dict) and not apothem_entry else None
    )
    if isinstance(current, dict) and current.get("enabled") is False:
        return Registration(
            None,
            f"hooks.internal.entries.{HOOK_NAME}.enabled is false in openclaw.json, "
            "so the Apothem rules file is written but not loaded. Turn the hook on "
            "and run `apothem update --harness open-claw` to load it.",
        )
    named = [
        name for name in entries if name != HOOK_NAME or operator_entry is not None
    ]
    extra_dirs = (
        internal.get("load", {}) if isinstance(internal.get("load"), dict) else {}
    )
    dirs = extra_dirs.get("extraDirs")
    open_discovery = (
        internal.get("enabled") is True
        and not named
        and not (isinstance(dirs, list) and any(str(item).strip() for item in dirs))
    )
    if open_discovery:
        return Registration(
            None,
            "openclaw.json sets hooks.internal.enabled to true and names no hook, so "
            "OpenClaw loads every eligible hook (unless hook packs installed with "
            "OpenClaw name theirs; that list is in OpenClaw's state database, which "
            "Apothem does not read). Registering the Apothem rules file would name "
            "the first hook and could switch the others off, so the file is "
            "written but not loaded. Name your hooks under hooks.internal.entries, "
            "then run `apothem update --harness open-claw`.",
        )
    if operator_entry is None:
        registration = FRESH_REGISTRATION
        key = "paths"
    else:
        key = next(
            (name for name in PATTERN_KEYS if _operator_items(operator_entry, name)),
            "paths",
        )
        registration = Registration({key: [RULES_FILE_RELATIVE]})
    return registration


def _listing_key(entry: object) -> str | None:
    """Return the list key under which *entry* already names the rules file.

    Only the list the hook reads counts (the first non-empty one).
    """
    if not isinstance(entry, dict):
        return None
    for key in PATTERN_KEYS:
        items = entry.get(key)
        if isinstance(items, list) and items:
            return key if RULES_FILE_RELATIVE in items else None
    return None


def materialize_native_config(
    profile: dict[str, Any], *, registration: Registration = FRESH_REGISTRATION
) -> str:
    """Render the open-claw native configuration from *profile*.

    Renders ``skills.load.extraDirs`` with one entry, :data:`SKILLS_DIRECTORY`.
    OpenClaw reads that list after the agent's other skill sources, so
    a skill the operator keeps in a workspace, ``~/.agents/skills`` or
    ``~/.openclaw/skills`` wins over an Apothem skill of the same name. The
    entry goes after the operator's own ``extraDirs`` entries and is the only
    one an uninstall removes.

    It also renders the ``bootstrap-extra-files`` hook entry *registration*
    holds (see :func:`plan_registration`); without an operator config to read,
    that is :data:`FRESH_REGISTRATION`. The ``agents.defaults.skills``
    allowlist, the ``agents.entries.<id>.skills`` lists, the ``mcp.servers``
    block and ``hooks.internal.enabled`` are the operator's, so Apothem authors
    none of them. Returns a JSON string ready to be written to
    ``~/.openclaw/openclaw.json``.
    """
    _ = profile
    config: dict[str, Any] = {"skills": {"load": {"extraDirs": [SKILLS_DIRECTORY]}}}
    if registration.entry is not None:
        config["hooks"] = {"internal": {"entries": {HOOK_NAME: registration.entry}}}
    return json.dumps(config, indent=2, ensure_ascii=False) + "\n"
