# SPDX-License-Identifier: MIT

"""Verify logic for the hermes harness adapter."""

from __future__ import annotations

from pathlib import Path

import yaml

from apothem.harnesses._shared.wrapper_factories import make_verify_native_config
from apothem.harnesses.hermes.materializer import SKILLS_DIRECTORY

_HARNESS_NAME: str = "hermes"

_verify_native_config = make_verify_native_config(_HARNESS_NAME)


def _lists_skills_directory(config: Path) -> bool:
    """Return True when *config* lists the Apothem skills directory.

    The list is ``skills.external_dirs``.
    """
    try:
        node: object = yaml.safe_load(config.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError):
        return False
    for key in ("skills", "external_dirs"):
        if not isinstance(node, dict):
            return False
        node = node.get(key)
    return isinstance(node, list) and SKILLS_DIRECTORY in node


def verify(output_path: Path) -> bool:
    """Return True when the install is intact and Hermes can load its skills.

    Runs the shared native-config check (the config and every managed target
    exist and parse), then requires ``skills.external_dirs`` to list the Apothem
    skills directory: without that entry Hermes does not load the installed
    skills, which is drift ``apothem update`` repairs.
    """
    return _verify_native_config(output_path) and _lists_skills_directory(output_path)
