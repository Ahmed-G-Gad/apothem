# SPDX-License-Identifier: MIT

"""Verify logic for the open-claw harness adapter."""

from __future__ import annotations

from pathlib import Path

from apothem.harnesses._shared.wrapper_factories import make_verify_native_config
from apothem.harnesses.open_claw import rules_file
from apothem.harnesses.open_claw.materializer import (
    HOOK_NAME,
    PATTERN_KEYS,
    RULES_FILE_RELATIVE,
    SKILLS_DIRECTORY,
    plan_registration,
)
from apothem.lib.harness_materializer import extract_managed_block

_HARNESS_NAME: str = "open_claw"

_verify_native_config = make_verify_native_config(_HARNESS_NAME)


def _at(node: object, *keys: str) -> object:
    """Return the value at *keys* below *node*, or ``None``."""
    for key in keys:
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    return node


def _lists_skills_directory(config: object) -> bool:
    """Return True when *config* lists the Apothem skills directory.

    The list is ``skills.load.extraDirs``.
    """
    dirs = _at(config, "skills", "load", "extraDirs")
    return isinstance(dirs, list) and SKILLS_DIRECTORY in dirs


def registers_rules_file(config: object, home: Path | None = None) -> bool:
    """Return True when OpenClaw would load the rules file *config* names.

    The hook entry is on and the first non-empty of its ``paths``,
    ``patterns`` and ``files`` lists (the one the hook reads) names the file.
    A config whose own settings keep the install from registering (internal
    hooks off, the entry turned off, or open hook discovery) also passes: the
    install reported that at the time, and an update cannot change it. So
    does one with no workspace the install could ever write into (each is
    behind a link, outside *home*, or not a folder): there is nothing to load.
    """
    if _names_file(config):
        return True
    if plan_registration(config, apothem_entry=False).entry is None:
        return True
    if home is None:
        return False
    found = rules_file.find_workspaces(config, home)
    return not found.found and not found.missing


def _names_file(config: object) -> bool:
    """Return True when the hook entry's active list names the rules file."""
    entry = _at(config, "hooks", "internal", "entries", HOOK_NAME)
    if not isinstance(entry, dict) or entry.get("enabled") is False:
        return False
    if _at(config, "hooks", "internal", "enabled") is False:
        return False
    for key in PATTERN_KEYS:
        items = entry.get(key)
        if isinstance(items, list) and items:
            return RULES_FILE_RELATIVE in items
    return False


def workspaces_hold_rules_file(config_path: Path, config: object) -> bool:
    """Return True when every workspace found holds the Apothem rules file.

    A workspace reached through a link, outside the home directory, or not
    yet created is not one the install writes, so it is not checked.
    """
    found = rules_file.find_workspaces(config, config_path.parent.parent)
    for workspace in found.found:
        try:
            text = workspace.rules_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return False
        if extract_managed_block(text) is None:
            return False
    return True


def verify(output_path: Path) -> bool:
    """Return True when the install is intact and OpenClaw loads what it wrote.

    Runs the shared native-config check (the config and every managed target
    exist and parse), then requires ``skills.load.extraDirs`` to list the
    Apothem skills directory, the ``bootstrap-extra-files`` hook to name the
    rules file, and every workspace found to hold it. A missing entry or file
    fails the check:

    - after a workspace appears or an entry is removed, ``apothem update``
      writes it back;
    - when the install reported the file over OpenClaw's size limits, it stays
      missing until the profile's custom rules are shortened or the limit is
      raised, and then an update writes it;
    - when ``openclaw.json`` holds JSON5 syntax, the operator adds the hook
      entry by hand (the install warning gives it).

    ``apothem status`` reports an edited rules file.
    """
    if not _verify_native_config(output_path):
        return False
    config = rules_file.read_config(output_path)
    return (
        _lists_skills_directory(config)
        and registers_rules_file(config, output_path.parent.parent)
        and workspaces_hold_rules_file(output_path, config)
    )
