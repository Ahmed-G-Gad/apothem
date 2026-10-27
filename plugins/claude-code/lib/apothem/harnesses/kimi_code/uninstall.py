# SPDX-License-Identifier: MIT

"""Uninstall logic for the kimi-code harness adapter."""

from __future__ import annotations

from pathlib import Path

from apothem.harnesses._shared import install_driver

_HARNESS_NAME: str = "kimi_code"

# Sentinel relative path the adapter resolves under ``--project``; the project
# root of a direct module call (no ``project``) is recovered by ascending as
# many parents as the path has components, so a manifest-depth change cannot
# leave a hardcoded ``parents[N]`` index pointing at the wrong root. This is the
# single source of truth for the target path — ``__init__`` imports it here.
RELATIVE_TARGET: Path = Path("AGENTS.md")

_PROJECT_DEPTH: int = len(RELATIVE_TARGET.parts) - 1


@install_driver.backup_session()
def uninstall(output_path: Path, *, project: Path | None = None) -> None:
    """Remove the Apothem install from the project root.

    The ``AGENTS.md`` ``sentinel_merge`` anchor is cleaned by the shared driver,
    which strips only Apothem's managed block (operator prose survives). The
    native skills under ``<project>/.kimi-code/skills/`` are reversed
    child-by-child against the Apothem source enumeration, so operator-authored
    skills with other names survive; one named like an Apothem skill is removed
    with it, after a backup. The native agents under
    ``<project>/.kimi-code/agents/`` are reversed the same way: Apothem's files
    go and an agent file of the operator's with another name stays. The
    Apothem-owned support tree under ``<project>/.kimi-code/.apothem/support/``
    (rules, templates, hooks) is removed.

    The shared uninstall reverses only the layout the current manifest declares.
    An install from before skills and agents moved to the native directories
    holds them in the support tree, paths no install entry targets any longer.
    The manifest's ``stale-sweep`` list names them, so they are swept first and
    their backups are passed on as ``prior_results``: the uninstall record then
    references them and retention keeps them.
    """
    project_root = (
        project if project is not None else output_path.parents[_PROJECT_DEPTH]
    )
    legacy = install_driver.sweep_stale(
        install_driver.load_rules(_HARNESS_NAME).stale_sweep,
        project_root,
        harness_name=_HARNESS_NAME,
        allowed_root=install_driver._allowed_write_root(None, project_root),
    )
    install_driver.run_uninstall(
        _HARNESS_NAME, project_root=project_root, prior_results=tuple(legacy)
    )
