# SPDX-License-Identifier: MIT

"""Per-mode install-entry appliers (write_text, replace_tree, merge_tree, agents, commands)."""

from __future__ import annotations

import contextlib
import shutil
from collections.abc import Callable
from pathlib import Path

from apothem.lib.propagation import (
    InstallEntry,
    resolve_target,
)

from .install_driver_backup import _replace_path, write_bytes_safely
from .install_driver_converters import (
    _antigravity_rule_text,
    _claude_rule_text,
    _codex_agent_text,
    _command_skill_files,
    _gemini_agent_text,
    _gemini_command_text,
    _native_markdown_command_text,
    _opencode_agent_text,
    _qwen_agent_text,
)
from .install_driver_merge import (
    _apply_operator_owned_file,
    render_content_tokens,
    write_text_safely,
)
from .install_driver_pathsafety import (
    _allowed_write_root,
    _root_for,
    _validate_target_path,
)
from .install_driver_treeops import (
    _directory_contents_equal,
    _native_skill_dir_files,
    _skill_children,
    _write_generated_directory,
    replace_tree,
)
from .install_driver_types import (
    AuthorizeFn,
    IgnoreFn,
    MaterializationResult,
    _is_excluded_path,
    _result,
    resolve_source,
)


def apply_write_text(
    entry: InstallEntry,
    *,
    harness_root: Path | None = None,
    project_root: Path | None = None,
    harness_name: str = "manual",
    authorize: AuthorizeFn | None = None,
) -> list[MaterializationResult]:
    """Apply a single ``write_text`` install entry as a template copy.

    Operator-owned targets (e.g. ``settings.json``, ``hooks.json``) route
    through the key-preserving merge with a unified diff and the
    destructive-authorization gate; Apothem-owned targets (e.g. plugin
    metadata) are written directly.
    """
    target = resolve_target(
        entry.target, harness_root=harness_root, project_root=project_root
    )
    src = resolve_source(entry.source)
    if not src.is_file():
        return [
            _result(
                "skipped",
                "write_text",
                target,
                "source file does not exist",
                source=src,
            )
        ]
    root = _root_for(harness_root, project_root)
    allowed_root = _allowed_write_root(harness_root, project_root)
    if entry.ownership_class == "operator-owned":
        return _apply_operator_owned_file(
            entry,
            target=target,
            src=src,
            root=root,
            harness_name=harness_name,
            allowed_root=allowed_root,
            authorize=authorize,
            harness_root=harness_root,
            project_root=project_root,
        )
    return [
        write_text_safely(
            target,
            render_content_tokens(
                src.read_text(encoding="utf-8"),
                harness_root=harness_root,
                project_root=project_root,
            ),
            install_root=root,
            harness_name=harness_name,
            allowed_root=allowed_root,
        )
    ]


def apply_replace_tree(
    entry: InstallEntry,
    ignore: IgnoreFn,
    *,
    harness_root: Path | None = None,
    project_root: Path | None = None,
    harness_name: str = "manual",
) -> list[MaterializationResult]:
    """Apply a single ``replace_tree`` install entry."""
    src = resolve_source(entry.source)
    dst = resolve_target(
        entry.target, harness_root=harness_root, project_root=project_root
    )
    return [
        replace_tree(
            src,
            dst,
            ignore,
            install_root=_root_for(harness_root, project_root),
            harness_name=harness_name,
            allowed_root=_allowed_write_root(harness_root, project_root),
        )
    ]


def apply_merge_tree_entries(
    entry: InstallEntry,
    ignore: IgnoreFn,
    exclude: list[str],
    *,
    harness_root: Path | None = None,
    project_root: Path | None = None,
    harness_name: str = "manual",
) -> list[MaterializationResult]:
    """Merge a source directory by replacing only its direct child entries."""
    src = resolve_source(entry.source)
    dst = resolve_target(
        entry.target, harness_root=harness_root, project_root=project_root
    )
    if not src.is_dir():
        return [
            _result(
                "skipped",
                "merge_tree_entries",
                dst,
                "source directory does not exist",
                source=src,
            )
        ]
    allowed_root = _allowed_write_root(harness_root, project_root)
    target_error = _validate_target_path(
        dst,
        allowed_root=allowed_root,
        operation="merge_tree_entries",
    )
    if target_error is not None:
        return [target_error]
    dst.mkdir(parents=True, exist_ok=True)
    root = _root_for(harness_root, project_root)
    results: list[MaterializationResult] = []
    for source_path in sorted(src.iterdir()):
        if _is_excluded_path(source_path, exclude):
            continue
        # The copytree ignore callback only runs for nested directory copies.
        if source_path.name in ignore(str(src), [source_path.name]):
            continue
        target = dst / source_path.name
        if source_path.is_dir():
            if _directory_contents_equal(source_path, target, ignore):
                results.append(
                    _result(
                        "unchanged",
                        "merge_tree_entries",
                        target,
                        "directory already matches",
                        source=source_path,
                    )
                )
                continue
            removed = _replace_path(
                target,
                install_root=root,
                harness_name=harness_name,
                allowed_root=allowed_root,
            )
            if removed is not None and removed.outcome == "error":
                results.append(removed)
                continue
            shutil.copytree(source_path, target, ignore=ignore)
            results.append(
                _result(
                    "updated" if removed else "created",
                    "merge_tree_entries",
                    target,
                    "copied directory entry",
                    source=source_path,
                    backup_path=(
                        Path(removed.backup_path)
                        if removed and removed.backup_path
                        else None
                    ),
                )
            )
        elif source_path.is_file():
            data = source_path.read_bytes()
            if b"${" in data:
                # Render install-time path tokens in text entries (e.g. the
                # statusline command pointing at its installed render script).
                with contextlib.suppress(UnicodeDecodeError):
                    data = render_content_tokens(
                        data.decode("utf-8"),
                        harness_root=harness_root,
                        project_root=project_root,
                    ).encode("utf-8")
            results.append(
                write_bytes_safely(
                    target,
                    data,
                    install_root=root,
                    harness_name=harness_name,
                    operation="merge_tree_entries",
                    source=source_path,
                    allowed_root=allowed_root,
                )
            )
    return results


def apply_command_skills(
    entry: InstallEntry,
    *,
    harness_root: Path | None = None,
    project_root: Path | None = None,
    harness_name: str = "manual",
) -> list[MaterializationResult]:
    """Install Markdown command files as native skill directories."""
    src = resolve_source(entry.source)
    dst = resolve_target(
        entry.target, harness_root=harness_root, project_root=project_root
    )
    if not src.is_dir():
        return [
            _result(
                "skipped",
                "command_skills",
                dst,
                "source directory does not exist",
                source=src,
            )
        ]
    allowed_root = _allowed_write_root(harness_root, project_root)
    target_error = _validate_target_path(
        dst,
        allowed_root=allowed_root,
        operation="command_skills",
    )
    if target_error is not None:
        return [target_error]
    dst.mkdir(parents=True, exist_ok=True)
    root = _root_for(harness_root, project_root)
    results: list[MaterializationResult] = []
    for source_path in sorted(src.glob("*.md")):
        if source_path.name in _COHORT_DOC_FILES:
            continue
        skill_dir = dst / source_path.stem
        results.append(
            _write_generated_directory(
                skill_dir,
                _command_skill_files(
                    source_path,
                    harness_name=harness_name,
                    install_root=root,
                ),
                root=root,
                harness_name=harness_name,
                operation="command_skills",
                source=source_path,
                allowed_root=allowed_root,
            )
        )
    return results


def apply_native_skills(
    entry: InstallEntry,
    *,
    ignore: IgnoreFn | None = None,
    exclude: list[str] | None = None,
    harness_root: Path | None = None,
    project_root: Path | None = None,
    harness_name: str = "manual",
) -> list[MaterializationResult]:
    """Install skill directories in the harness's native skill form.

    Like ``merge_tree_entries`` for a skills cohort (direct children replaced
    one by one, operator siblings kept), but each skill directory is emitted
    through :func:`_native_skill_emission`: the harness may translate
    ``SKILL.md`` frontmatter and add sidecar files. Plain files at the cohort
    root are copied unchanged.
    """
    src = resolve_source(entry.source)
    dst = resolve_target(
        entry.target, harness_root=harness_root, project_root=project_root
    )
    if not src.is_dir():
        return [
            _result(
                "skipped",
                "native_skills",
                dst,
                "source directory does not exist",
                source=src,
            )
        ]
    allowed_root = _allowed_write_root(harness_root, project_root)
    target_error = _validate_target_path(
        dst, allowed_root=allowed_root, operation="native_skills"
    )
    if target_error is not None:
        return [target_error]
    dst.mkdir(parents=True, exist_ok=True)
    root = _root_for(harness_root, project_root)
    results: list[MaterializationResult] = []
    for source_path in _skill_children(src, ignore, exclude):
        if source_path.is_dir():
            files = _native_skill_dir_files(
                source_path, harness_name=harness_name, ignore=ignore
            )
            results.append(
                _write_generated_directory(
                    dst / source_path.name,
                    files,
                    root=root,
                    harness_name=harness_name,
                    operation="native_skills",
                    source=source_path,
                    allowed_root=allowed_root,
                    ignore=ignore,
                )
            )
        elif source_path.is_file():
            results.append(
                write_bytes_safely(
                    dst / source_path.name,
                    source_path.read_bytes(),
                    install_root=root,
                    harness_name=harness_name,
                    operation="native_skills",
                    source=source_path,
                    allowed_root=allowed_root,
                )
            )
    return results


#: Documentation companions that live beside cohort members but are never
#: materialized as members themselves.
_COHORT_DOC_FILES: frozenset[str] = frozenset({"README.md", "AGENTS.md"})

#: A per-harness Markdown-to-native cohort renderer: ``source_path`` -> the
#: native definition text (encoded UTF-8 before it is written). Both the
#: ``apply_*_agents`` and the ``apply_*_commands`` families supply one.
CohortRenderer = Callable[[Path], str]


def _apply_rendered_cohort(
    entry: InstallEntry,
    *,
    renderer: CohortRenderer,
    operation: str,
    target_extension: str | None = None,
    remove_stale_markdown: bool = False,
    harness_root: Path | None = None,
    project_root: Path | None = None,
    harness_name: str = "manual",
) -> list[MaterializationResult]:
    """Materialize a source ``*.md`` cohort into a target directory.

    Every rendered-cohort mode (the ``apply_*_agents`` family and the
    ``apply_*_commands`` family) shares one shape: resolve the source cohort
    directory and its target, skip when the source is absent, validate the
    target path, create the target directory, then render each cohort member
    (excluding the documentation companions) to bytes and write it safely.
    The per-harness variance is carried by the parameters:

    Args:
        renderer: The harness's Markdown-to-native text renderer.
        operation: The mode name recorded on every emitted result.
        target_extension: When given (e.g. ``"toml"``), the target file keeps
            the source stem with this extension (``codex`` writes ``.toml``);
            when ``None`` the target reuses the source file name verbatim.
        remove_stale_markdown: When ``True``, a same-named ``.md`` left by an
            earlier install is backed up and removed before the renamed target
            is written (``codex``, which changed its extension to ``.toml``).
            Its removal result is recorded; an error outcome skips that member.
    """
    src = resolve_source(entry.source)
    dst = resolve_target(
        entry.target, harness_root=harness_root, project_root=project_root
    )
    if not src.is_dir():
        return [
            _result(
                "skipped",
                operation,
                dst,
                "source directory does not exist",
                source=src,
            )
        ]
    allowed_root = _allowed_write_root(harness_root, project_root)
    target_error = _validate_target_path(
        dst,
        allowed_root=allowed_root,
        operation=operation,
    )
    if target_error is not None:
        return [target_error]
    dst.mkdir(parents=True, exist_ok=True)
    root = _root_for(harness_root, project_root)
    results: list[MaterializationResult] = []
    for source_path in sorted(src.glob("*.md")):
        if source_path.name in _COHORT_DOC_FILES:
            continue
        if remove_stale_markdown:
            removed = _replace_path(
                dst / source_path.name,
                install_root=root,
                harness_name=harness_name,
                allowed_root=allowed_root,
            )
            if removed is not None:
                results.append(removed)
                if removed.outcome == "error":
                    continue
        target_name = (
            f"{source_path.stem}.{target_extension}"
            if target_extension is not None
            else source_path.name
        )
        results.append(
            write_bytes_safely(
                dst / target_name,
                renderer(source_path).encode("utf-8"),
                install_root=root,
                harness_name=harness_name,
                operation=operation,
                source=source_path,
                allowed_root=allowed_root,
            )
        )
    return results


def apply_codex_agents(
    entry: InstallEntry,
    *,
    harness_root: Path | None = None,
    project_root: Path | None = None,
    harness_name: str = "manual",
) -> list[MaterializationResult]:
    """Install Markdown agent files as Codex TOML custom agents."""
    return _apply_rendered_cohort(
        entry,
        renderer=_codex_agent_text,
        operation="codex_agents",
        target_extension="toml",
        remove_stale_markdown=True,
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
    return _apply_rendered_cohort(
        entry,
        renderer=_gemini_agent_text,
        operation="gemini_agents",
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
    return _apply_rendered_cohort(
        entry,
        renderer=_opencode_agent_text,
        operation="opencode_agents",
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
    return _apply_rendered_cohort(
        entry,
        renderer=_qwen_agent_text,
        operation="qwen_agents",
        harness_root=harness_root,
        project_root=project_root,
        harness_name=harness_name,
    )


def apply_gemini_commands(
    entry: InstallEntry,
    *,
    harness_root: Path | None = None,
    project_root: Path | None = None,
    harness_name: str = "manual",
) -> list[MaterializationResult]:
    """Install Markdown command files as Gemini CLI TOML slash commands."""
    return _apply_rendered_cohort(
        entry,
        renderer=_gemini_command_text,
        operation="gemini_commands",
        target_extension="toml",
        harness_root=harness_root,
        project_root=project_root,
        harness_name=harness_name,
    )


def apply_markdown_commands(
    entry: InstallEntry,
    *,
    harness_root: Path | None = None,
    project_root: Path | None = None,
    harness_name: str = "manual",
) -> list[MaterializationResult]:
    """Install Markdown command files as native Markdown slash commands."""
    return _apply_rendered_cohort(
        entry,
        renderer=_native_markdown_command_text,
        operation="markdown_commands",
        harness_root=harness_root,
        project_root=project_root,
        harness_name=harness_name,
    )


def apply_claude_rules(
    entry: InstallEntry,
    *,
    harness_root: Path | None = None,
    project_root: Path | None = None,
    harness_name: str = "manual",
) -> list[MaterializationResult]:
    """Install rule files with ``pathFilter`` rendered as Claude Code ``paths:``."""
    return _apply_rendered_cohort(
        entry,
        renderer=_claude_rule_text,
        operation="claude_rules",
        harness_root=harness_root,
        project_root=project_root,
        harness_name=harness_name,
    )


def apply_antigravity_rules(
    entry: InstallEntry,
    *,
    ignore: IgnoreFn | None = None,
    exclude: list[str] | None = None,
    harness_root: Path | None = None,
    project_root: Path | None = None,
    harness_name: str = "manual",
) -> list[MaterializationResult]:
    """Install Markdown rules as Antigravity rules with a valid ``trigger``.

    *ignore* and *exclude* are accepted for the shared emission signature (see
    :data:`HARNESS_EMISSION_APPLIERS`); a flat rules cohort uses neither.
    """
    del ignore, exclude
    return _apply_rendered_cohort(
        entry,
        renderer=_antigravity_rule_text,
        operation="antigravity_rules",
        harness_root=harness_root,
        project_root=project_root,
        harness_name=harness_name,
    )


#: Harness-specific emission modes. Each applier takes the entry plus the
#: ``ignore`` / ``exclude`` / ``harness_root`` / ``project_root`` /
#: ``harness_name`` keywords; the install dispatcher looks a mode up here, so
#: adding one is a single row.
HARNESS_EMISSION_APPLIERS: dict[str, Callable[..., list[MaterializationResult]]] = {
    "antigravity_rules": apply_antigravity_rules,
    "claude_rules": apply_claude_rules,
    "native_skills": apply_native_skills,
}
