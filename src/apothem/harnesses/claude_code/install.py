# SPDX-License-Identifier: MIT

"""Install logic for the claude-code harness adapter.

Installs the Apothem convention surface — not the Python library
implementation — into the Claude Code harness target (``~/.claude/`` by
default). The convention surface is the set of artifacts that match
Claude Code's native discovery patterns (agents, commands, skills,
rules, output-styles, statusline). Command prompts are also wrapped as
skills so reusable workflows are visible through the current skill surface.
The hook dispatcher, conformity gate, and
their schema fixtures are materialized under the shared ``.apothem/`` working
directory's ``support/`` child at the harness root
(``.apothem/support/hooks/``, ``.apothem/support/conformity/``,
``.apothem/support/schemas/``)
so the settings.json hook entries invoke them by absolute script path
— no importable ``apothem`` package is required on the host. Each hook
entry's ``command`` carries a ``${PYTHON_BIN}`` placeholder the install
resolves to the absolute path of a real CPython >= 3.10 (per
``apothem.lib.python_resolver``) so no entry invokes a bare ``python``
that a host PATH could resolve to a Microsoft Store WindowsApps launcher
stub.

The shared profile is projected into the user-scope ``CLAUDE.md`` instruction
anchor as a sentinel-delimited Apothem managed block (identity / preferences /
rules / seriousness / opted-in behaviors); operator prose outside the sentinels
is preserved verbatim. Per the ratified transport map, Claude Code MCP is
registered via ``claude mcp add`` into ``~/.claude.json`` / project ``.mcp.json``
— not a file Apothem authors — so this adapter projects no MCP entries and the
``settings.json`` permissions/hooks template is left unchanged.

The adapter is user-scope: it propagates under the harness root resolved
as ``output_path.parent`` (``~/.claude/``). Its propagation contract —
the install list, exclude globs, stale-sweep entries, and per-directory
filename filter — is declared in the canonical manifest at
``src/apothem/lib/propagation-manifest.yaml`` under the ``claude_code``
key and applied by the shared driver at
``apothem.harnesses._shared.install_driver``. Drift between the
propagation contract and the on-disk install is impossible by
construction: the manifest IS the contract.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from apothem.harnesses._shared import install_driver
from apothem.harnesses._shared.install_driver import MaterializationRun
from apothem.harnesses._shared.install_driver_layout import with_support_announcement
from apothem.lib.profile import coerce_profile
from apothem.lib.profile_projection import project
from apothem.lib.python_resolver import resolve_python_bin

# Manifest harness key for this adapter.
_HARNESS_NAME: str = "claude_code"
# Public adapter id used to resolve per-harness profile overrides.
_HARNESS_ID: str = "claude-code"


@install_driver.backup_session()
def install(
    output_path: Path, profile: dict[str, Any], *, dry_run: bool = False
) -> MaterializationRun:
    """Install the apothem convention surface into the Claude Code harness.

    The harness root is derived as ``output_path.parent`` — the
    ``ClaudeCodeAdapter`` resolves this to ``~/.claude/``. The hook interpreter
    is resolved FIRST, before any tree is written: a resolution failure
    (:func:`resolve_python_bin` raising when no real CPython >= 3.10 is found)
    aborts the install with nothing on disk. The resolved path is substituted
    for the template's ``${PYTHON_BIN}`` token while settings.json is rendered,
    so the file is written once in its final form (a re-install and ``diff``
    then see no pending change). The manifest-driven convention surface
    (settings.json, agents/, commands→skills/, rules/, skills/, support trees)
    is materialized, then the shared *profile* is projected into the
    user-scope ``CLAUDE.md`` instruction anchor as a sentinel-delimited managed
    block (identity / preferences / rules / seriousness / opted-in behaviors).
    Operator prose outside the sentinels is preserved verbatim. All operations
    are idempotent — re-running with the same profile yields byte-identical
    output and preserves unrelated operator-authored discovery entries.

    With ``dry_run=True`` nothing is written: the returned run previews every
    write, the ``CLAUDE.md`` anchor included.
    """
    harness_root = output_path.parent
    # Resolve the hook interpreter before writing anything: a resolution failure
    # must abort with no half-written tree carrying literal ``${PYTHON_BIN}``.
    python_bin = resolve_python_bin().as_posix()
    for_harness = coerce_profile(profile).for_harness(_HARNESS_ID)
    # CLAUDE.md is the instruction file this install writes, so it also names
    # where the install placed the support files the corpus cites.
    body = with_support_announcement(
        project(for_harness, _HARNESS_ID).managed_block_body,
        _HARNESS_NAME,
        harness_root,
    )
    missing = install_driver.capture_missing_dirs(
        _HARNESS_NAME,
        harness_root=harness_root,
        profile=profile,
        extra=(harness_root / "CLAUDE.md",),
    )
    with install_driver.content_tokens(PYTHON_BIN=python_bin):
        run = install_driver.run_install(
            _HARNESS_NAME, harness_root=harness_root, dry_run=dry_run
        )
    anchor_result = install_driver.apply_managed_block_anchor(
        harness_root / "CLAUDE.md",
        body,
        install_root=harness_root,
        harness_name=_HARNESS_NAME,
        allowed_root=harness_root.parent,
        dry_run=dry_run,
    )
    if dry_run:
        return run.extend([anchor_result])
    return install_driver.finalize_install(
        run.extend([anchor_result]),
        root=harness_root,
        missing_before=missing,
    )


def plan(output_path: Path) -> list[dict[str, str]]:
    """Return the propagation plan for the configured harness without writing.

    Each entry carries ``source`` (resolved on-disk path), ``target``
    (resolved absolute path under ``output_path.parent``), and ``mode``
    (``write_text``, a tree mode, or a conversion mode). The plan is the manifest's
    install list materialized against the active harness root — the same
    sequence ``install`` would apply, in declaration order.
    """
    return install_driver.build_plan(_HARNESS_NAME, harness_root=output_path.parent)
