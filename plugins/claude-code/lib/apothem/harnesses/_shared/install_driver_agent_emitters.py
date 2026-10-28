# SPDX-License-Identifier: MIT

"""Registry of the agent-definition emissions the install driver makes.

Each agent install mode renders the source ``agents/*.md`` cohort into one
harness's native subagent files. What differs between the modes is small and
declarative: the renderer that turns one source file into native text, the
extension of the file it is written to, whether an earlier ``.md`` copy is
retired first, and which source agents the harness cannot take. One
:class:`AgentEmitter` row in :data:`AGENT_EMITTERS` carries all four, and the
four places that act on a mode read the same row:

- the install dispatcher (:func:`install_driver_materialize._dispatch_install_entry`)
  applies it through :func:`install_driver_agent_apply.apply_agent_emitter`;
- the plan builder and uninstall enumerate its targets
  (:func:`install_driver_planvalidation._generated_targets_for_entry`);
- the dry-run preview classifies each member against the rendered text;
- a test pins that a row names a mode with a label.

A new agent emission is therefore one row here plus its renderer, with no edit
to the appliers or the enumeration. The renderers for the first six modes stay in
:mod:`install_driver_converters`; the CodeBuddy and Trae renderers, which share
a comma-string tool shape, are in :mod:`install_driver_agent_comma_tools`, and
the GitHub Copilot and Cursor renderers, whose tool restriction is an alias
allowlist and a single ``readonly`` flag, are in
:mod:`install_driver_agent_copilot_cursor`, and the Kimi Code and Devin Local
renderers, which translate the tool names into each vendor's own list, are in
:mod:`install_driver_agent_kimi_devin`, and the Kiro renderer, which folds the
tool grant and denials into a list of category tags, is in
:mod:`install_driver_agent_kiro`. Renderers for later modes are added
outside that file so it stays under the module size ceiling.

``_INSTALL_ENTRY_MODES`` and ``OPERATION_LABELS`` in
:mod:`install_driver_types` remain literal tables, because that module is a
leaf the converters' import chain must not be pulled into. A row here without
an entry in both fails ``test_install_driver_agent_emitters.py``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from apothem.lib.claude_agent_mcp import claude_agent_text

from .install_driver_agent_comma_tools import codebuddy_agent_text, trae_agent_text
from .install_driver_agent_copilot_cursor import copilot_agent_text, cursor_agent_text
from .install_driver_agent_kimi_devin import devin_agent_text, kimi_agent_text
from .install_driver_agent_kiro import kiro_agent_text
from .install_driver_converters import (
    _antigravity_agent_text,
    _codex_agent_text,
    _gemini_agent_text,
    _opencode_agent_text,
    _qwen_agent_text,
)

#: Source agents Devin Local is not given: they need web tools, and the tool names
#: Devin accepts in ``allowed-tools`` for them are undocumented
#: (https://docs.devin.ai/cli/subagents.md, retrieved 2026-10-27). Installing them
#: with the web grant dropped would hand a research agent no way to research, and
#: with no ``allowed-tools`` it would hand it every tool. No release shipped a
#: Windsurf agents entry (v1.0.1 to v1.4.0), so there is nothing to retire.
_DEVIN_HELD_BACK: Final[frozenset[str]] = frozenset(
    {"citation-auditor", "fact-checker", "research-scout"}
)

#: A per-harness agent renderer: ``source_path`` -> the native definition text
#: (encoded UTF-8 before it is written).
AgentRenderer = Callable[[Path], str]


@dataclass(frozen=True)
class AgentEmitter:
    """How one harness takes the source agents cohort.

    Attributes:
        mode: The install-entry mode this row serves; also the operation name
            recorded on every result the emission produces.
        renderer: Turns one source agent file into the harness's native text.
        target_extension: The extension each target file gets after the source
            stem, spelled without the leading dot (``"toml"``, or ``"agent.md"``
            for a double extension). ``None`` keeps the source file name.
        remove_stale_markdown: When True, a same-named ``.md`` left by an
            earlier install is backed up and removed before the renamed target
            is written (Codex, which changed its extension to ``.toml``).
        exclude: Stems of source agents this harness is not given. They are
            skipped by the install, the plan, the dry-run preview and the
            uninstall alike, so the four never disagree on what is installed.
    """

    mode: str
    renderer: AgentRenderer
    target_extension: str | None = None
    remove_stale_markdown: bool = False
    exclude: frozenset[str] = frozenset()

    def target_name(self, source_path: Path) -> str:
        """Return the file name the emission writes for *source_path*."""
        if self.target_extension is None:
            return source_path.name
        return f"{source_path.stem}.{self.target_extension}"


_EMITTERS: Final[tuple[AgentEmitter, ...]] = (
    AgentEmitter(
        "codex_agents",
        _codex_agent_text,
        target_extension="toml",
        remove_stale_markdown=True,
    ),
    AgentEmitter("gemini_agents", _gemini_agent_text),
    AgentEmitter("opencode_agents", _opencode_agent_text),
    AgentEmitter("qwen_agents", _qwen_agent_text),
    AgentEmitter("antigravity_agents", _antigravity_agent_text),
    AgentEmitter("claude_agents", claude_agent_text),
    AgentEmitter("codebuddy_agents", codebuddy_agent_text),
    AgentEmitter("trae_agents", trae_agent_text),
    AgentEmitter("copilot_agents", copilot_agent_text, target_extension="agent.md"),
    AgentEmitter("cursor_agents", cursor_agent_text),
    AgentEmitter("kimi_agents", kimi_agent_text),
    AgentEmitter("devin_agents", devin_agent_text, exclude=_DEVIN_HELD_BACK),
    AgentEmitter("kiro_agents", kiro_agent_text),
)

#: Agent emission modes by name. Adding an agent emission is one row above.
AGENT_EMITTERS: Final[dict[str, AgentEmitter]] = {
    emitter.mode: emitter for emitter in _EMITTERS
}
