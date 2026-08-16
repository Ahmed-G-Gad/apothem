# SPDX-License-Identifier: MIT

"""Uninstall logic for the kimi-code harness adapter."""

from __future__ import annotations

from pathlib import Path

from apothem.harnesses._shared.wrapper_factories import make_project_scope_uninstall

_HARNESS_NAME: str = "kimi_code"

# Sentinel relative path the adapter resolves under ``--project``; the uninstall
# factory derives the project-root ascent depth from its component count so a
# direct module call (no ``project``) recovers the correct root under any
# manifest-depth change instead of a hardcoded ``parents[N]`` index. This is the
# single source of truth for the target path — ``__init__`` imports it here.
RELATIVE_TARGET: Path = Path("AGENTS.md")

# The ``AGENTS.md`` ``sentinel_merge`` anchor is cleaned by the shared driver,
# which strips only Apothem's managed block (operator prose survives), and the
# Apothem-owned support tree under ``<project>/.kimi-code/.apothem/support/``
# (rules, commands, skills, agents, templates, hooks) is removed.
uninstall = make_project_scope_uninstall(_HARNESS_NAME, relative_target=RELATIVE_TARGET)
