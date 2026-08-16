# SPDX-License-Identifier: MIT

"""Uninstall logic for the zed harness adapter."""

from __future__ import annotations

from pathlib import Path

from apothem.harnesses._shared.wrapper_factories import make_project_scope_uninstall

_HARNESS_NAME: str = "zed"

# Sentinel relative path the adapter resolves under ``--project``; the uninstall
# factory derives the project-root ascent depth from its component count so a
# direct module call (no ``project``) recovers the correct root under any
# manifest-depth change instead of a hardcoded ``parents[N]`` index. This is the
# single source of truth for the target path — ``__init__`` imports it here.
# Zed's flat-file divergence: the target is the bare ``.rules`` dotfile at the
# project root (one component), so the project root is the file's direct parent
# — unlike the cohort's nested rules-directory targets.
RELATIVE_TARGET: Path = Path(".rules")

# The ``.rules`` ``sentinel_merge`` anchor is cleaned by the shared driver, which
# strips only Apothem's managed block (operator prose survives), deletes an
# Apothem-only file, and backs the file up under the Apothem backup root — no
# whole-file ``.bak`` sibling is left beside the operator's file.
uninstall = make_project_scope_uninstall(_HARNESS_NAME, relative_target=RELATIVE_TARGET)
