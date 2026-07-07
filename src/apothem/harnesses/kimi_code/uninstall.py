# SPDX-License-Identifier: MIT

"""Uninstall logic for the kimi-code harness adapter."""

from __future__ import annotations

from pathlib import Path

from apothem.harnesses._shared import install_driver

_HARNESS_NAME: str = "kimi_code"


def uninstall(output_path: Path, *, project: Path | None = None) -> None:
    """Remove Apothem-managed Kimi Code targets surgically.

    The ``AGENTS.md`` ``sentinel_merge`` anchor is cleaned by the shared
    driver, which strips only Apothem's managed block (operator prose
    survives), and the Apothem-owned support tree under
    ``<project>/.kimi-code/.apothem/support/`` (rules, commands, skills, agents,
    templates, hooks) is removed.
    The target is the
    project-root ``AGENTS.md``, so the project root is its immediate parent
    when ``project`` is not threaded through.
    """
    install_driver.run_uninstall(
        _HARNESS_NAME,
        project_root=project or output_path.parent,
    )
