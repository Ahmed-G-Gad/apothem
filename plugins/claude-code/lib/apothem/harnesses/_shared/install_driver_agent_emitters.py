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
to the appliers or the enumeration. The renderers for the modes below stay in
:mod:`install_driver_converters`; renderers and tool maps for later modes are
added to this module so that file stays under the module size ceiling.

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

from .install_driver_converters import (
    _antigravity_agent_text,
    _codex_agent_text,
    _gemini_agent_text,
    _opencode_agent_text,
    _qwen_agent_text,
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
)

#: Agent emission modes by name. Adding an agent emission is one row above.
AGENT_EMITTERS: Final[dict[str, AgentEmitter]] = {
    emitter.mode: emitter for emitter in _EMITTERS
}
