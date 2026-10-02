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
from apothem.harnesses._shared.install_driver import (
    MaterializationResult,
    MaterializationRun,
)
from apothem.lib import atomic_io
from apothem.lib.profile import coerce_profile
from apothem.lib.profile_projection import project
from apothem.lib.python_resolver import resolve_python_bin

# Manifest harness key for this adapter.
_HARNESS_NAME: str = "claude_code"
# Public adapter id used to resolve per-harness profile overrides.
_HARNESS_ID: str = "claude-code"
# Placeholder the settings.json template carries on every hook ``command``
# field; resolved to an absolute CPython path at install time so no hook
# entry invokes a bare ``python`` (which a host PATH can resolve to a
# Microsoft Store WindowsApps launcher stub).
_PYTHON_BIN_TOKEN: str = "${PYTHON_BIN}"  # noqa: S105 — template placeholder token, not a secret


def _substitute_hook_interpreter(
    harness_root: Path, python_bin: str
) -> list[MaterializationResult]:
    """Substitute ``${PYTHON_BIN}`` in the installed settings.json.

    Reads the settings.json the manifest install just wrote, replaces every
    ``${PYTHON_BIN}`` placeholder with *python_bin* (the absolute path to a real
    CPython >= 3.10 resolved by :func:`resolve_python_bin` *before* the tree was
    written), and rewrites the file in place. Resolution is pre-committed by the
    caller so a resolution failure aborts the install before any tree is
    written, never leaving settings.json with literal ``${PYTHON_BIN}`` in every
    hook command. The rewrite is a pure token substitution on the file the same
    install just produced, so it is written atomically *without* a
    backup-before-replace and *without* the JSON key-merge — both would corrupt
    the substitution (the merge re-prefers the existing ``${PYTHON_BIN}`` token,
    and the backup would capture the un-resolved intermediate state as a stray
    sibling). Idempotent: *python_bin* is stable across installs on the same
    host, so re-running yields byte-identical output. A settings.json with no
    placeholder (already resolved, or an operator-stripped hooks block) is left
    untouched.
    """
    settings_path = harness_root / "settings.json"
    if not settings_path.is_file():
        return []
    content = settings_path.read_text(encoding="utf-8")
    if _PYTHON_BIN_TOKEN not in content:
        return []
    rendered = content.replace(_PYTHON_BIN_TOKEN, python_bin)
    atomic_io.write_bytes_atomically(settings_path, rendered.encode("utf-8"))
    return [
        MaterializationResult(
            outcome="updated",
            operation="resolve-python-bin",
            path=str(settings_path),
            message=f"resolved hook interpreter to {python_bin}",
            source=None,
            backup_path=None,
            detail={"python_bin": python_bin},
        )
    ]


def install(output_path: Path, profile: dict[str, Any]) -> MaterializationRun:
    """Install the apothem convention surface into the Claude Code harness.

    The harness root is derived as ``output_path.parent`` — the
    ``ClaudeCodeAdapter`` resolves this to ``~/.claude/``. The hook interpreter
    is resolved FIRST, before any tree is written: a resolution failure
    (:func:`resolve_python_bin` raising when no real CPython >= 3.10 is found)
    aborts the install with nothing on disk, so it can never leave settings.json
    with a literal ``${PYTHON_BIN}`` in every hook command (which would then
    invoke a nonexistent binary). The manifest-driven convention surface
    (settings.json, agents/, commands→skills/, rules/, skills/, support trees)
    is materialized next, then the shared *profile* is projected into the
    user-scope ``CLAUDE.md`` instruction anchor as a sentinel-delimited managed
    block (identity / preferences / rules / seriousness / opted-in behaviors),
    and finally the pre-resolved interpreter path is substituted into the
    written settings.json. Operator prose outside the sentinels is preserved
    verbatim. All operations are idempotent — re-running with the same profile
    yields byte-identical output and preserves unrelated operator-authored
    discovery entries.
    """
    harness_root = output_path.parent
    # Resolve the hook interpreter before writing anything: a resolution failure
    # must abort with no half-written tree carrying literal ``${PYTHON_BIN}``.
    python_bin = resolve_python_bin().as_posix()
    missing = install_driver.capture_missing_dirs(
        _HARNESS_NAME,
        harness_root=harness_root,
        profile=profile,
        extra=(harness_root / "CLAUDE.md",),
    )
    run = install_driver.run_install(_HARNESS_NAME, harness_root=harness_root)
    for_harness = coerce_profile(profile).for_harness(_HARNESS_ID)
    surfaces = project(for_harness, _HARNESS_ID)
    anchor_result = install_driver.apply_managed_block_anchor(
        harness_root / "CLAUDE.md",
        surfaces.managed_block_body,
        install_root=harness_root,
        harness_name=_HARNESS_NAME,
        allowed_root=harness_root.parent,
    )
    interpreter_results = _substitute_hook_interpreter(harness_root, python_bin)
    return install_driver.finalize_install(
        run.extend([anchor_result, *interpreter_results]),
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
