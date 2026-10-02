# SPDX-License-Identifier: MIT

"""Shared propagation driver for harness adapters.

Every harness adapter's ``install.py`` propagates the apothem convention
surface by the same recipe: load the harness's rules from the canonical
manifest, sweep stale top-level paths from earlier install layouts, then
apply each install entry in declaration order (``write_text`` entries write
a single template with backup/merge safeguards; ``replace_tree`` entries refresh a directory
under the manifest's exclude globs and per-directory filename filter). This
module carries that recipe once so the adapters hold only their
harness-specific identity (the manifest key) and scope (user-scope harness
root vs. project-scope project root).

Scope is expressed by which keyword the caller supplies:

- **User-scope** adapters (claude_code, codex, antigravity) pass
  ``harness_root`` — the harness's configuration root (e.g. ``~/.claude``).
  The root is created if absent.
- **Project-scope** adapters (cursor, github_copilot, gemini_cli, windsurf)
  pass ``project_root`` — the operator-supplied project directory. The root
  is assumed to exist; only per-entry target parents are created.

The manifest's ``${HARNESS_ROOT}`` / ``${PROJECT_ROOT}`` placeholders are
substituted by ``apothem.lib.propagation.resolve_target`` against whichever
root the caller supplied; a placeholder with no matching root is left
literal so callers surface the unresolved form instead of a misleading
absolute path.
"""

from __future__ import annotations

from apothem.lib import install_ledger as install_ledger
from apothem.lib.propagation import load_manifest as load_manifest
from apothem.lib.propagation import resolve_target as resolve_target

from .install_driver_apply import _COHORT_DOC_FILES as _COHORT_DOC_FILES
from .install_driver_apply import apply_antigravity_rules as apply_antigravity_rules
from .install_driver_apply import apply_claude_rules as apply_claude_rules
from .install_driver_apply import apply_codex_agents as apply_codex_agents
from .install_driver_apply import apply_command_skills as apply_command_skills
from .install_driver_apply import apply_gemini_agents as apply_gemini_agents
from .install_driver_apply import apply_gemini_commands as apply_gemini_commands
from .install_driver_apply import apply_markdown_commands as apply_markdown_commands
from .install_driver_apply import apply_merge_tree_entries as apply_merge_tree_entries
from .install_driver_apply import apply_opencode_agents as apply_opencode_agents
from .install_driver_apply import apply_qwen_agents as apply_qwen_agents
from .install_driver_apply import apply_replace_tree as apply_replace_tree
from .install_driver_apply import apply_write_text as apply_write_text
from .install_driver_backup import _LEDGER_OUTCOMES as _LEDGER_OUTCOMES
from .install_driver_backup import _NON_LEDGER_OPERATIONS as _NON_LEDGER_OPERATIONS
from .install_driver_backup import _backup_relative_path as _backup_relative_path
from .install_driver_backup import _compensating_rollback as _compensating_rollback
from .install_driver_backup import _guarded_unlink as _guarded_unlink
from .install_driver_backup import _install_lock_path as _install_lock_path
from .install_driver_backup import _ledger_targets as _ledger_targets
from .install_driver_backup import _replace_path as _replace_path
from .install_driver_backup import _reserve_unique_backup as _reserve_unique_backup
from .install_driver_backup import _sibling_backup_path as _sibling_backup_path
from .install_driver_backup import _unique_path as _unique_path
from .install_driver_backup import _write_file_atomically as _write_file_atomically
from .install_driver_backup import backup_existing as backup_existing
from .install_driver_backup import backup_file_to_sibling as backup_file_to_sibling
from .install_driver_backup import finalize_install as finalize_install
from .install_driver_backup import list_backup_timestamps as list_backup_timestamps
from .install_driver_backup import record_install as record_install
from .install_driver_backup import restore_backup as restore_backup
from .install_driver_backup import write_bytes_safely as write_bytes_safely
from .install_driver_converters import (
    _OPENCODE_PERMISSION_MAP as _OPENCODE_PERMISSION_MAP,
)
from .install_driver_converters import _QWEN_TOOL_MAP as _QWEN_TOOL_MAP
from .install_driver_converters import _agent_body as _agent_body
from .install_driver_converters import _agent_description as _agent_description
from .install_driver_converters import _agent_name as _agent_name
from .install_driver_converters import _agent_scalar_list as _agent_scalar_list
from .install_driver_converters import _agent_tool_names as _agent_tool_names
from .install_driver_converters import _codex_agent_text as _codex_agent_text
from .install_driver_converters import _gemini_agent_text as _gemini_agent_text
from .install_driver_converters import _gemini_command_text as _gemini_command_text
from .install_driver_converters import _generated_skill_text as _generated_skill_text
from .install_driver_converters import (
    _installed_reference_note as _installed_reference_note,
)
from .install_driver_converters import (
    _native_markdown_command_text as _native_markdown_command_text,
)
from .install_driver_converters import _opencode_agent_text as _opencode_agent_text
from .install_driver_converters import (
    _opencode_permission_lines as _opencode_permission_lines,
)
from .install_driver_converters import _qwen_agent_text as _qwen_agent_text
from .install_driver_converters import _qwen_approval_mode as _qwen_approval_mode
from .install_driver_converters import (
    _strip_leading_html_comment as _strip_leading_html_comment,
)
from .install_driver_converters import (
    _strip_markdown_frontmatter as _strip_markdown_frontmatter,
)
from .install_driver_converters import _toml_multiline_string as _toml_multiline_string
from .install_driver_converters import _toml_string as _toml_string
from .install_driver_converters import _yaml_list as _yaml_list
from .install_driver_converters import _yaml_scalar as _yaml_scalar
from .install_driver_jsonmerge import _APOTHEM_HOOK_MARKERS as _APOTHEM_HOOK_MARKERS
from .install_driver_jsonmerge import (
    CONFIG_UNPARSEABLE_CODE as CONFIG_UNPARSEABLE_CODE,
)
from .install_driver_jsonmerge import _dedupe_json_list as _dedupe_json_list
from .install_driver_jsonmerge import _is_apothem_hook as _is_apothem_hook
from .install_driver_jsonmerge import _leading_comment_block as _leading_comment_block
from .install_driver_jsonmerge import _merge_hook_entry as _merge_hook_entry
from .install_driver_jsonmerge import _merge_hooks as _merge_hooks
from .install_driver_jsonmerge import _merge_json_settings as _merge_json_settings
from .install_driver_jsonmerge import _merge_json_values as _merge_json_values
from .install_driver_jsonmerge import _overlay_json_settings as _overlay_json_settings
from .install_driver_lifecycle import FidelityResult as FidelityResult
from .install_driver_lifecycle import _native_config_parses as _native_config_parses
from .install_driver_lifecycle import _profile_anchor_targets as _profile_anchor_targets
from .install_driver_lifecycle import _remove_data_home as _remove_data_home
from .install_driver_lifecycle import _rendered_template_text as _rendered_template_text
from .install_driver_lifecycle import build_plan as build_plan
from .install_driver_lifecycle import check_fidelity as check_fidelity
from .install_driver_lifecycle import detect_install as detect_install
from .install_driver_lifecycle import fidelity_is_faithful as fidelity_is_faithful
from .install_driver_lifecycle import run_uninstall as run_uninstall
from .install_driver_lifecycle import verify_install as verify_install
from .install_driver_materialize import (
    _capability_projection_results as _capability_projection_results,
)
from .install_driver_materialize import (
    _dispatch_install_entry as _dispatch_install_entry,
)
from .install_driver_materialize import _dry_run_results as _dry_run_results
from .install_driver_materialize import (
    _materialize_data_surfaces as _materialize_data_surfaces,
)
from .install_driver_materialize import run_install as run_install
from .install_driver_merge import (
    _apply_operator_owned_file as _apply_operator_owned_file,
)
from .install_driver_merge import _merged_json_text as _merged_json_text
from .install_driver_merge import (
    _operator_owned_merge_text as _operator_owned_merge_text,
)
from .install_driver_merge import _operator_owned_preview as _operator_owned_preview
from .install_driver_merge import _unified_diff as _unified_diff
from .install_driver_merge import (
    apply_managed_block_anchor as apply_managed_block_anchor,
)
from .install_driver_merge import (
    apply_operator_owned_content as apply_operator_owned_content,
)
from .install_driver_merge import apply_sentinel_merge as apply_sentinel_merge
from .install_driver_merge import project_profile_document as project_profile_document
from .install_driver_merge import render_content_tokens as render_content_tokens
from .install_driver_merge import write_text_safely as write_text_safely
from .install_driver_ownership import _merge_native_content as _merge_native_content
from .install_driver_pathsafety import _allowed_write_root as _allowed_write_root
from .install_driver_pathsafety import _existing_chain as _existing_chain
from .install_driver_pathsafety import (
    _filesystem_is_case_insensitive as _filesystem_is_case_insensitive,
)
from .install_driver_pathsafety import _is_relative_to as _is_relative_to
from .install_driver_pathsafety import _normalized as _normalized
from .install_driver_pathsafety import _root_for as _root_for
from .install_driver_pathsafety import _unsafe_symlink as _unsafe_symlink
from .install_driver_pathsafety import _validate_target_path as _validate_target_path
from .install_driver_pathsafety import _within_allowed_root as _within_allowed_root
from .install_driver_planvalidation import (
    _generated_targets_for_entry as _generated_targets_for_entry,
)
from .install_driver_planvalidation import (
    _projected_profile_body as _projected_profile_body,
)
from .install_driver_planvalidation import (
    _validate_install_plan as _validate_install_plan,
)
from .install_driver_planvalidation import (
    _validate_ownership_class as _validate_ownership_class,
)
from .install_driver_planvalidation import _validate_source as _validate_source
from .install_driver_planvalidation import load_rules as load_rules
from .install_driver_planvalidation import make_ignore as make_ignore
from .install_driver_removal import _drop_owned_top_keys as _drop_owned_top_keys
from .install_driver_removal import (
    _remove_apothem_hook_handlers as _remove_apothem_hook_handlers,
)
from .install_driver_removal import _remove_apothem_hooks as _remove_apothem_hooks
from .install_driver_removal import (
    _remove_apothem_list_items as _remove_apothem_list_items,
)
from .install_driver_removal import _remove_apothem_values as _remove_apothem_values
from .install_driver_removal import _strip_apothem_json as _strip_apothem_json
from .install_driver_removal import _strip_apothem_yaml as _strip_apothem_yaml
from .install_driver_removal import (
    _surgical_remove_from_target as _surgical_remove_from_target,
)
from .install_driver_removal import (
    surgically_remove_materialized_config as surgically_remove_materialized_config,
)
from .install_driver_treeops import (
    _directory_contents_equal as _directory_contents_equal,
)
from .install_driver_treeops import _iter_relative_files as _iter_relative_files
from .install_driver_treeops import (
    _single_file_directory_matches as _single_file_directory_matches,
)
from .install_driver_treeops import (
    _write_single_file_directory as _write_single_file_directory,
)
from .install_driver_treeops import replace_tree as replace_tree
from .install_driver_treeops import sweep_stale as sweep_stale
from .install_driver_types import _INSTALL_ENTRY_MODES as _INSTALL_ENTRY_MODES
from .install_driver_types import _OUTCOMES as _OUTCOMES
from .install_driver_types import (
    _REFUSED_OWNERSHIP_CLASSES as _REFUSED_OWNERSHIP_CLASSES,
)
from .install_driver_types import _REMOVE_KEY as _REMOVE_KEY
from .install_driver_types import APOTHEM_SRC as APOTHEM_SRC
from .install_driver_types import BACKUP_ROOT as BACKUP_ROOT
from .install_driver_types import OPERATION_LABELS as OPERATION_LABELS
from .install_driver_types import AuthorizationRequest as AuthorizationRequest
from .install_driver_types import AuthorizeFn as AuthorizeFn
from .install_driver_types import IgnoreFn as IgnoreFn
from .install_driver_types import MaterializationError as MaterializationError
from .install_driver_types import MaterializationOutcome as MaterializationOutcome
from .install_driver_types import MaterializationResult as MaterializationResult
from .install_driver_types import MaterializationRun as MaterializationRun
from .install_driver_types import _handle_rm_error as _handle_rm_error
from .install_driver_types import _is_excluded_path as _is_excluded_path
from .install_driver_types import _path_text as _path_text
from .install_driver_types import _result as _result
from .install_driver_types import _timestamp_slug as _timestamp_slug
from .install_driver_types import _with_detail as _with_detail
from .install_driver_types import operation_label as operation_label
from .install_driver_types import preview_status as preview_status
from .install_driver_types import resolve_source as resolve_source

__all__ = [
    "APOTHEM_SRC",
    "BACKUP_ROOT",
    "OPERATION_LABELS",
    "AuthorizationRequest",
    "AuthorizeFn",
    "FidelityResult",
    "IgnoreFn",
    "MaterializationError",
    "MaterializationOutcome",
    "MaterializationResult",
    "MaterializationRun",
    "apply_claude_rules",
    "apply_codex_agents",
    "apply_command_skills",
    "apply_gemini_agents",
    "apply_gemini_commands",
    "apply_managed_block_anchor",
    "apply_markdown_commands",
    "apply_merge_tree_entries",
    "apply_opencode_agents",
    "apply_operator_owned_content",
    "apply_qwen_agents",
    "apply_replace_tree",
    "apply_sentinel_merge",
    "apply_write_text",
    "backup_existing",
    "build_plan",
    "check_fidelity",
    "detect_install",
    "fidelity_is_faithful",
    "finalize_install",
    "list_backup_timestamps",
    "load_rules",
    "make_ignore",
    "operation_label",
    "preview_status",
    "record_install",
    "replace_tree",
    "resolve_source",
    "resolve_target",
    "restore_backup",
    "run_install",
    "run_uninstall",
    "surgically_remove_materialized_config",
    "sweep_stale",
    "verify_install",
    "write_bytes_safely",
    "write_text_safely",
]
