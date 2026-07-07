# SPDX-License-Identifier: MIT

"""Apothem harness adapter for claude-code — full-surface install.

Writes the canonical ``settings.json`` template and flattens the convention
dirs (agents/, rules/, skills/ — command prompts are rendered in as skills,
statuslines/, output-styles/) at
the harness root; a top-level ``commands/`` directory is swept per the
propagation manifest's stale-sweep list. The install is self-contained: the hook dispatcher and the
conformity gate are materialized under the harness root's shared ``.apothem/``
working directory (``.apothem/support/hooks/`` and ``.apothem/support/conformity/``
with the sibling ``.apothem/support/schemas/`` fixtures)
and invoked by absolute path from ``settings.json``; no pip-installed
package is required. No ``src/apothem/`` mirror is produced; flat-copied
source trees found at the harness root are swept on every install per the
propagation manifest's stale-sweep list. The shared profile is projected into
``~/.claude/CLAUDE.md`` as a sentinel-delimited Apothem managed block — operator
prose outside the sentinels is preserved verbatim — so the apothem governance
surface reaches Claude Code through that managed block, the propagated ``rules/``
tree, and the SessionStart hook. Delegates install logic to
:mod:`apothem.harnesses.claude_code.install`.

Plugin-alone capability
-----------------------

The Claude Code plugin can be installed alone via the marketplace, with no
separate ``python -m apothem install`` engine install. In that posture the
plugin's ``.claude-plugin/plugin.json`` ``hooks`` field points at a generated
``hooks.json`` (see :func:`apothem.lib.plugin_tree.build_plugin_hooks_json`)
whose every command drives the shell bootstrap stub under
``${CLAUDE_PLUGIN_ROOT}``. The stub self-locates a CPython interpreter and
execs the bundled dispatcher, so hooks fire without the engine install's
``${PYTHON_BIN}`` / ``${HARNESS_ROOT}`` substitution. The honest capability
split:

* **Persists plugin-alone.** The SessionStart bootstrap (which now emits a
  lean pointer to the bundled ``rules/`` plus a note that the mechanical hooks
  are active), the PreToolUse write / edit / notebook / bash context guards
  (authorship-header, plans-locality, base context nudges), and the
  PreCompact / PostCompact / Stop handlers — every dispatch-routable hook event.
* **Degrades plugin-alone.** The behavioral ``rules/`` are bundled under the
  plugin root but cannot load as always-on context; they degrade to the
  SessionStart pointer plus the still-active mechanical hooks. The conformity
  gate's ``gate.py --hook`` entry is NOT wired plugin-alone — the bootstrap
  stub drives only the dispatcher, and the gate's scope default targets a
  harness root (``~/.claude`` / ``~/.codex``) rather than a plugin-alone
  project write; full conformity-gate enforcement needs the engine install.
* **Needs the engine install.** The materialized ``settings.json``
  (permissions allow / deny floor), the ``output-styles/`` and
  ``statuslines/`` cohorts, and the ``CLAUDE.md`` managed-block projection are
  engine-install surfaces with no plugin manifest field.
* **Not shipped today.** No MCP server is bundled, so no MCP tools surface
  from the plugin alone.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from apothem.harnesses._shared.install_driver import MaterializationRun
from apothem.harnesses.claude_code.install import install as _install
from apothem.harnesses.claude_code.install import plan as _plan
from apothem.harnesses.claude_code.uninstall import uninstall as _uninstall
from apothem.harnesses.claude_code.update import update as _update
from apothem.harnesses.claude_code.verify import verify as _verify


class ClaudeCodeAdapter:
    """ClaudeCodeAdapter — implements :class:`~apothem.harnesses.HarnessAdapter`."""

    @property
    def name(self) -> str:
        """Return the canonical kebab-case harness identifier."""
        return "claude-code"

    @property
    def output_path(self) -> Path:
        """Return the always-propagated singleton config file path.

        The adapter resolves the harness root as ``output_path.parent``;
        ``is_installed()`` / ``verify()`` resolve against this file. The
        always-written ``settings.json`` is the singleton presence anchor; the
        profile-projected ``CLAUDE.md`` managed block is written alongside it.
        """
        return Path.home() / ".claude/settings.json"

    def install(self, profile: dict[str, Any]) -> MaterializationRun:
        """Materialize the harness configuration from the shared profile."""
        return _install(self.output_path, profile)

    def update(self, profile: dict[str, Any]) -> MaterializationRun:
        """Re-materialize the harness configuration from the updated profile."""
        return _update(self.output_path, profile)

    def plan(self, output_path: Path | None = None) -> list[dict[str, str]]:
        """Return the manifest-driven propagation plan without writing."""
        return _plan(output_path or self.output_path)

    def uninstall(self) -> None:
        """Remove the harness configuration file if present."""
        _uninstall(self.output_path)

    def is_installed(self) -> bool:
        """Return True if the configuration file exists on disk."""
        return self.output_path.exists()

    def verify(self) -> bool:
        """Return True if the installed configuration is valid."""
        return _verify(self.output_path)
