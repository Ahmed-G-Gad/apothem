# SPDX-License-Identifier: MIT

"""Appliers for the agent emissions registered in ``install_driver_agent_emitters``."""

from __future__ import annotations

from pathlib import Path

from apothem.lib.propagation import InstallEntry

from .install_driver_agent_emitters import AGENT_EMITTERS, AgentEmitter
from .install_driver_apply import _apply_rendered_cohort
from .install_driver_types import MaterializationResult


def apply_agent_emitter(
    emitter: AgentEmitter,
    entry: InstallEntry,
    *,
    harness_root: Path | None = None,
    project_root: Path | None = None,
    harness_name: str = "manual",
) -> list[MaterializationResult]:
    """Install the source agents cohort in the form *emitter* declares.

    The one applier every agent emission goes through: the registry row names
    the renderer, the target extension, the stale ``.md`` retirement and the
    excluded agents, and :func:`_apply_rendered_cohort` does the writing.
    """
    return _apply_rendered_cohort(
        entry,
        renderer=emitter.renderer,
        operation=emitter.mode,
        target_extension=emitter.target_extension,
        remove_stale_markdown=emitter.remove_stale_markdown,
        exclude=emitter.exclude,
        harness_root=harness_root,
        project_root=project_root,
        harness_name=harness_name,
    )


def apply_codex_agents(
    entry: InstallEntry,
    *,
    harness_root: Path | None = None,
    project_root: Path | None = None,
    harness_name: str = "manual",
) -> list[MaterializationResult]:
    """Install Markdown agent files as Codex TOML custom agents."""
    return apply_agent_emitter(
        AGENT_EMITTERS["codex_agents"],
        entry,
        harness_root=harness_root,
        project_root=project_root,
        harness_name=harness_name,
    )


def apply_gemini_agents(
    entry: InstallEntry,
    *,
    harness_root: Path | None = None,
    project_root: Path | None = None,
    harness_name: str = "manual",
) -> list[MaterializationResult]:
    """Install normalized Gemini CLI Markdown subagent definitions."""
    return apply_agent_emitter(
        AGENT_EMITTERS["gemini_agents"],
        entry,
        harness_root=harness_root,
        project_root=project_root,
        harness_name=harness_name,
    )


def apply_opencode_agents(
    entry: InstallEntry,
    *,
    harness_root: Path | None = None,
    project_root: Path | None = None,
    harness_name: str = "manual",
) -> list[MaterializationResult]:
    """Install normalized OpenCode Markdown subagent definitions."""
    return apply_agent_emitter(
        AGENT_EMITTERS["opencode_agents"],
        entry,
        harness_root=harness_root,
        project_root=project_root,
        harness_name=harness_name,
    )


def apply_qwen_agents(
    entry: InstallEntry,
    *,
    harness_root: Path | None = None,
    project_root: Path | None = None,
    harness_name: str = "manual",
) -> list[MaterializationResult]:
    """Install normalized Qwen Code Markdown subagent definitions."""
    return apply_agent_emitter(
        AGENT_EMITTERS["qwen_agents"],
        entry,
        harness_root=harness_root,
        project_root=project_root,
        harness_name=harness_name,
    )
