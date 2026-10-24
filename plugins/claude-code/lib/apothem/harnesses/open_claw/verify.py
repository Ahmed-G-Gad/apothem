# SPDX-License-Identifier: MIT

"""Verify logic for the open-claw harness adapter."""

from __future__ import annotations

from pathlib import Path

from apothem.harnesses._shared.wrapper_factories import make_verify_native_config
from apothem.harnesses.open_claw.materializer import SKILLS_DIRECTORY
from apothem.lib import lenient_json

_HARNESS_NAME: str = "open_claw"

_verify_native_config = make_verify_native_config(_HARNESS_NAME)


def _lists_skills_directory(config: Path) -> bool:
    """Return True when *config* lists the Apothem skills directory.

    The list is ``skills.load.extraDirs``. The file is read as JSON5, the
    dialect OpenClaw reads, so an operator file with comments still verifies.
    """
    try:
        node: object = lenient_json.loads(config.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, lenient_json.LenientJSONError):
        return False
    for key in ("skills", "load", "extraDirs"):
        if not isinstance(node, dict):
            return False
        node = node.get(key)
    return isinstance(node, list) and SKILLS_DIRECTORY in node


def verify(output_path: Path) -> bool:
    """Return True when the install is intact and OpenClaw can load its skills.

    Runs the shared native-config check (the config and every managed target
    exist and parse), then requires ``skills.load.extraDirs`` to list the Apothem
    skills directory: without that entry OpenClaw does not load the installed
    skills, which is drift ``apothem update`` repairs.
    """
    return _verify_native_config(output_path) and _lists_skills_directory(output_path)
