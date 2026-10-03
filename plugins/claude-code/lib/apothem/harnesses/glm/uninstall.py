# SPDX-License-Identifier: MIT

"""Uninstall logic for the glm harness adapter."""

from __future__ import annotations

from pathlib import Path

from apothem.harnesses._shared.wrapper_factories import make_project_scope_uninstall

_HARNESS_NAME: str = "glm"

# Sentinel relative path the adapter resolves under ``--project``; the uninstall
# factory derives the project-root ascent depth from its component count so a
# direct module call (no ``project``) recovers the correct root under any
# manifest-depth change instead of a hardcoded ``parents[N]`` index. This is the
# single source of truth for the target path — ``__init__`` imports it here.
RELATIVE_TARGET: Path = Path(".apothem") / "providers" / "glm.toml"

# The shared driver removes the ``glm.toml`` provider file only when Apothem
# created it and it is still the unedited template; an operator's own or edited
# file is left in place. The file is backed up under the Apothem backup root
# first — no whole-file ``.bak`` sibling is left beside the operator's files.
uninstall = make_project_scope_uninstall(_HARNESS_NAME, relative_target=RELATIVE_TARGET)
