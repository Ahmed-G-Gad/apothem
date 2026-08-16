# SPDX-License-Identifier: MIT

"""Managed-block + JSON/YAML key-merge and the operator-owned write path."""

from __future__ import annotations

import contextlib
import difflib
import json
from pathlib import Path
from string import Template
from typing import Any

import yaml

from apothem.lib.harness_materializer import (
    merge_managed_block,
)
from apothem.lib.propagation import (
    InstallEntry,
    resolve_target,
)

from .install_driver_backup import write_bytes_safely
from .install_driver_pathsafety import (
    _allowed_write_root,
    _root_for,
    _validate_target_path,
)
from .install_driver_types import (
    AuthorizationRequest,
    AuthorizeFn,
    MaterializationOutcome,
    MaterializationResult,
    _path_text,
    _result,
    _with_detail,
    resolve_source,
)


def apply_managed_block_anchor(
    target: Path,
    body: str,
    *,
    install_root: Path,
    harness_name: str,
    allowed_root: Path | None = None,
) -> MaterializationResult:
    """Fold a profile-projected managed block into an operator-owned anchor.

    Reads the existing anchor (if any), merges *body* into the canonical Apothem
    sentinel block via :func:`merge_managed_block` (operator prose outside the
    sentinels preserved verbatim), and writes the result atomically with
    backup-before-replace + no-op detection. This is the reusable projection
    write path every instruction-anchor adapter shares: the profile-projection
    seam renders *body*, this helper lands it in the harness's Markdown anchor.
    """
    try:
        existing = target.read_text(encoding="utf-8") if target.exists() else ""
    except OSError:
        existing = ""
    merged = merge_managed_block(existing, body)
    return write_bytes_safely(
        target,
        merged.encode("utf-8"),
        install_root=install_root,
        harness_name=harness_name,
        operation="sentinel_merge",
        allowed_root=allowed_root,
    )


def project_profile_document(
    harness_root: Path,
    *,
    harness_id: str,
    harness_name: str,
    profile: dict[str, Any],
    relative_path: str = "apothem/rules/00-apothem-profile.md",
) -> MaterializationResult:
    """Write the profile's projected managed block to a config adapter's anchor.

    The single-file-config adapters render a native config whose schema accepts
    only documented keys (skills pointers, MCP), so the profile's identity /
    preferences / rules / opted-in behaviors reach the harness through this
    dedicated apothem profile document under the adapter's apothem rules
    directory — the same directory the native config's instructions pointer
    references. Written through the gated managed-block anchor path, so it is
    operator-preserving and idempotent.
    """
    from apothem.lib.profile import coerce_profile
    from apothem.lib.profile_projection import project

    for_harness = coerce_profile(profile).for_harness(harness_id)
    surfaces = project(for_harness, harness_id)
    return apply_managed_block_anchor(
        harness_root / relative_path,
        surfaces.managed_block_body,
        install_root=harness_root,
        harness_name=harness_name,
        allowed_root=harness_root.parent,
    )


#: Substrings that identify an Apothem-managed hook handler. Covers both the
#: module-invocation spelling and the installed script-path spelling (the
#: settings templates point hooks at the materialized ``hooks/dispatch.py``
#: and ``conformity/gate.py`` scripts under the harness root).
_APOTHEM_HOOK_MARKERS: tuple[str, ...] = (
    "apothem.hooks.dispatch",
    "apothem.conformity.gate",
    "hooks/dispatch.py",
    "conformity/gate.py",
)


def _is_apothem_hook(handler: object) -> bool:
    """Return True when a hook handler belongs to Apothem's managed surface."""
    if not isinstance(handler, dict):
        return False
    command = str(handler.get("command", ""))
    args = handler.get("args", [])
    args_text = " ".join(str(arg) for arg in args) if isinstance(args, list) else ""
    haystacks = (command, args_text)
    return any(
        marker in haystack for marker in _APOTHEM_HOOK_MARKERS for haystack in haystacks
    )


def _dedupe_json_list(existing: list[object], incoming: list[object]) -> list[object]:
    """Append incoming JSON values that are not already present."""
    merged = list(existing)
    for item in incoming:
        if item not in merged:
            merged.append(item)
    return merged


def _merge_hook_entry(
    existing_entries: list[object],
    incoming_entry: dict[str, object],
) -> dict[str, object]:
    """Merge one incoming hook matcher with existing non-Apothem handlers."""
    matcher = incoming_entry.get("matcher")
    preserved_handlers: list[object] = []
    for entry in existing_entries:
        if not isinstance(entry, dict) or entry.get("matcher") != matcher:
            continue
        handlers = entry.get("hooks", [])
        if not isinstance(handlers, list):
            continue
        preserved_handlers.extend(
            handler for handler in handlers if not _is_apothem_hook(handler)
        )

    incoming_handlers = incoming_entry.get("hooks", [])
    if not isinstance(incoming_handlers, list):
        incoming_handlers = []

    merged_entry = dict(incoming_entry)
    merged_entry["hooks"] = preserved_handlers + incoming_handlers
    return merged_entry


def _merge_hooks(
    existing_hooks: dict[str, object],
    incoming_hooks: dict[str, object],
) -> dict[str, object]:
    """Merge Claude Code hook settings while replacing Apothem-owned handlers."""
    merged = dict(existing_hooks)
    for event_name, incoming_entries in incoming_hooks.items():
        if not isinstance(incoming_entries, list):
            merged[event_name] = incoming_entries
            continue
        existing_entries_obj = existing_hooks.get(event_name, [])
        existing_entries = (
            existing_entries_obj if isinstance(existing_entries_obj, list) else []
        )
        incoming_matchers = {
            entry.get("matcher")
            for entry in incoming_entries
            if isinstance(entry, dict)
        }
        retained = [
            entry
            for entry in existing_entries
            if not isinstance(entry, dict)
            or entry.get("matcher") not in incoming_matchers
        ]
        for incoming_entry in incoming_entries:
            if isinstance(incoming_entry, dict):
                retained.append(_merge_hook_entry(existing_entries, incoming_entry))
            else:
                retained.append(incoming_entry)
        merged[event_name] = retained
    return merged


def _merge_json_settings(existing: object, incoming: object) -> object:
    """Merge JSON settings while preserving operator-authored keys."""
    return _merge_json_values(existing, incoming, prefer_existing=True)


def _overlay_json_settings(existing: object, incoming: object) -> object:
    """Merge JSON settings while incoming managed values take precedence."""
    return _merge_json_values(existing, incoming, prefer_existing=False)


def _merge_json_values(
    existing: object, incoming: object, *, prefer_existing: bool
) -> object:
    """Merge JSON objects, preserving keys absent from the incoming object."""
    if isinstance(existing, dict) and isinstance(incoming, dict):
        merged: dict[str, object] = dict(existing)
        for key, value in incoming.items():
            current = existing.get(key)
            if key == "hooks" and isinstance(current, dict) and isinstance(value, dict):
                merged[key] = _merge_hooks(current, value)
            elif (
                prefer_existing
                and isinstance(current, list)
                and isinstance(value, list)
            ):
                merged[key] = _dedupe_json_list(current, value)
            elif isinstance(current, dict) and isinstance(value, dict):
                merged[key] = _merge_json_values(
                    current, value, prefer_existing=prefer_existing
                )
            elif key not in merged:
                merged[key] = value
            elif prefer_existing:
                merged[key] = current
            else:
                merged[key] = value
        return merged
    if isinstance(existing, list) and isinstance(incoming, list):
        if prefer_existing:
            return _dedupe_json_list(existing, incoming)
        return incoming
    return existing


def _merged_json_text(
    target: Path, content: str, *, prefer_existing: bool = True
) -> str:
    """Return JSON text merged with an existing JSON target when possible."""
    incoming = json.loads(content)
    try:
        existing = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return json.dumps(incoming, indent=2, ensure_ascii=False) + "\n"
    merger = _merge_json_settings if prefer_existing else _overlay_json_settings
    merged = merger(existing, incoming)
    return json.dumps(merged, indent=2, ensure_ascii=False) + "\n"


def write_text_safely(
    target: Path,
    content: str,
    *,
    install_root: Path,
    harness_name: str,
    prefer_existing_json_values: bool = True,
    allowed_root: Path | None = None,
) -> MaterializationResult:
    """Write text with backup-before-replace and JSON-preserving merge."""
    target_error = _validate_target_path(
        target,
        allowed_root=allowed_root or install_root,
        operation="write_text",
    )
    if target_error is not None:
        return target_error
    output = content
    if target.suffix.lower() == ".json" and target.exists():
        with contextlib.suppress(json.JSONDecodeError):
            output = _merged_json_text(
                target,
                content,
                prefer_existing=prefer_existing_json_values,
            )
    return write_bytes_safely(
        target,
        output.encode("utf-8"),
        install_root=install_root,
        harness_name=harness_name,
        operation="write_text",
        allowed_root=allowed_root,
    )


def _leading_comment_block(text: str) -> str:
    """Return the leading comment/blank lines of *text* (a managed YAML header).

    PyYAML drops comments on round-trip, so the incoming config's leading
    ``#`` header is captured here and re-prepended to a merged YAML body. This
    keeps the merge byte-stable: re-merging identical content reproduces the
    same header + body, so install stays idempotent.
    """
    kept: list[str] = []
    for line in text.splitlines(keepends=True):
        stripped = line.lstrip()
        if stripped == "" or stripped.startswith("#"):
            kept.append(line)
        else:
            break
    return "".join(kept)


def _merged_yaml_text(target: Path, content: str, *, prefer_existing: bool) -> str:
    """Return YAML text merged with an existing YAML target when possible.

    The YAML mirror of :func:`_merged_json_text`: parse both documents, overlay
    operator keys per the shared key-merge, re-dump, and re-prepend the incoming
    managed header comment. Operator keys absent from the incoming managed
    config are preserved; operator *comments* are not retained across a
    merge-over-existing (PyYAML round-trips values, not comments). A clean
    install with no existing target writes *content* verbatim.
    """
    try:
        incoming = yaml.safe_load(content)
        existing = yaml.safe_load(target.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return content
    if not isinstance(incoming, dict) or not isinstance(existing, dict):
        return content
    merger = _merge_json_settings if prefer_existing else _overlay_json_settings
    merged = merger(existing, incoming)
    header = _leading_comment_block(content)
    return header + yaml.safe_dump(merged, sort_keys=False, allow_unicode=True)


def _merge_native_content(target: Path, content: str, *, existed: bool) -> str:
    """Return the prospective merged text for a materializer-rendered config.

    JSON and YAML targets key-merge with the operator's existing file (incoming
    managed values authoritative, operator-added keys preserved); other suffixes
    and non-existent targets render *content* verbatim.
    """
    if not existed:
        return content
    suffix = target.suffix.lower()
    if suffix == ".json":
        with contextlib.suppress(json.JSONDecodeError, OSError):
            return _merged_json_text(target, content, prefer_existing=False)
    elif suffix in {".yaml", ".yml"}:
        return _merged_yaml_text(target, content, prefer_existing=False)
    return content


def apply_operator_owned_content(
    target: Path,
    content: str,
    *,
    install_root: Path,
    harness_name: str,
    ownership_class: str = "operator-owned",
    allowed_root: Path | None = None,
    authorize: AuthorizeFn | None = None,
) -> MaterializationResult:
    """Write materializer-rendered content to an operator-owned native config.

    The content-based sibling of :func:`_apply_operator_owned_file` (which reads
    from a source file): the same gated apply path for adapters whose config is
    rendered dynamically from the profile. Computes a suffix-aware
    key-preserving merge (JSON / YAML), records a unified diff on the result,
    consults *authorize* on a non-additive overwrite (declining leaves the
    operator file untouched), then writes atomically with backup-before-replace
    and no-op detection.
    """
    write_allowed = allowed_root or install_root
    target_error = _validate_target_path(
        target, allowed_root=write_allowed, operation="write_text"
    )
    if target_error is not None:
        return target_error
    existed = target.exists()
    before = ""
    if existed:
        with contextlib.suppress(OSError):
            before = target.read_text(encoding="utf-8")
    merged = _merge_native_content(target, content, existed=existed)
    diff = _unified_diff(before, merged, target)
    detail: dict[str, str] = {"ownership_class": ownership_class}
    if diff:
        detail["diff"] = diff
    if existed and before != merged:
        detail["destructive_gate"] = "required"
        if authorize is not None and not authorize(
            AuthorizationRequest(
                harness=harness_name,
                path=_path_text(target),
                operation="write_text",
                ownership_class=ownership_class,
                diff=diff,
            )
        ):
            return _with_detail(
                _result(
                    "skipped",
                    "write_text",
                    target,
                    "operator declined the native-config change",
                ),
                detail,
            )
    result = write_bytes_safely(
        target,
        merged.encode("utf-8"),
        install_root=install_root,
        harness_name=harness_name,
        operation="write_text",
        allowed_root=allowed_root,
    )
    return _with_detail(result, detail)


def _unified_diff(before: str, after: str, target: Path) -> str:
    """Return a unified diff from *before* to *after* for *target*."""
    return "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=f"a/{target.name}",
            tofile=f"b/{target.name}",
        )
    )


def render_content_tokens(
    content: str,
    *,
    harness_root: Path | None,
    project_root: Path | None = None,
) -> str:
    """Substitute ``${HARNESS_ROOT}`` / ``${PROJECT_ROOT}`` inside template text.

    The content-side mirror of :func:`apothem.lib.propagation.resolve_target`:
    target paths resolve placeholders at the manifest layer, and this helper
    resolves the same placeholders inside the template's *body* so a template
    can embed install-time absolute paths — the hook entries in
    ``settings.json`` and ``hooks.json`` point at the dispatcher's on-disk
    location this way. Substituted paths use forward-slash form so the result
    stays valid inside JSON string literals on every platform. An absent root
    leaves its placeholder untouched, matching the path-resolution helper.
    """
    if "${" not in content:
        return content
    mapping: dict[str, str] = {}
    if harness_root is not None:
        mapping["HARNESS_ROOT"] = harness_root.resolve().as_posix()
    if project_root is not None:
        mapping["PROJECT_ROOT"] = project_root.resolve().as_posix()
    if not mapping:
        return content
    return Template(content).safe_substitute(mapping)


def _operator_owned_merge_text(
    entry: InstallEntry, target: Path, content: str, *, existed: bool
) -> str:
    """Return the prospective merged text for an operator-owned target.

    ``sentinel_merge`` entries fold *content* into the operator anchor as a
    sentinel-delimited managed block, preserving operator prose outside the
    block. ``write_text`` entries on an existing JSON target run the JSON
    merge with the incoming template authoritative: template-carried keys
    update in place so fixes ship to existing installs, while operator-added
    keys absent from the template are preserved. The backup-before-replace
    and destructive-authorization gate still guard the write. A non-existent
    target merges to *content* verbatim.
    """
    if entry.mode == "sentinel_merge":
        existing = ""
        if existed:
            with contextlib.suppress(OSError):
                existing = target.read_text(encoding="utf-8")
        return merge_managed_block(existing, content)
    if target.suffix.lower() == ".json" and existed:
        with contextlib.suppress(json.JSONDecodeError, OSError):
            return _merged_json_text(target, content, prefer_existing=False)
    return content


def _operator_owned_preview(
    entry: InstallEntry,
    *,
    harness_root: Path | None,
    project_root: Path | None,
    profile_body: str | None = None,
) -> tuple[Path, MaterializationOutcome, str, bool] | None:
    """Return (target, outcome, unified-diff, gate-required) for an entry.

    Reads the source and the current target without writing, then computes the
    prospective merge exactly as :func:`_apply_operator_owned_file` would — the
    projected *profile_body* is folded into a ``sentinel_merge`` anchor so the
    preview reflects the same managed block the real write lands — and
    classifies the no-write outcome against the current on-disk bytes:

    - ``created`` when the target does not yet exist,
    - ``unchanged`` when the prospective merge reproduces the current bytes,
    - ``updated`` when the prospective merge changes existing bytes.

    The unified diff and the destructive-gate flag (``True`` only for an
    ``updated`` outcome, i.e. an overwrite of differing operator content)
    accompany the outcome so a dry-run preview can render the same diff the
    gated write would show. ``None`` when the source file is absent (nothing to
    preview — the plan validator already errors on a missing source, so this is
    a defensive fallback).
    """
    src = resolve_source(entry.source)
    if not src.is_file():
        return None
    target = resolve_target(
        entry.target, harness_root=harness_root, project_root=project_root
    )
    content = render_content_tokens(
        src.read_text(encoding="utf-8"),
        harness_root=harness_root,
        project_root=project_root,
    )
    if entry.mode == "sentinel_merge" and profile_body:
        content = f"{content.rstrip()}\n\n{profile_body}"
    existed = target.exists()
    before = ""
    if existed:
        with contextlib.suppress(OSError):
            before = target.read_text(encoding="utf-8")
    after = _operator_owned_merge_text(entry, target, content, existed=existed)
    diff = _unified_diff(before, after, target)
    gate_required = existed and before != after
    outcome: MaterializationOutcome = (
        "created" if not existed else ("updated" if gate_required else "unchanged")
    )
    return target, outcome, diff, gate_required


def _apply_operator_owned_file(
    entry: InstallEntry,
    *,
    target: Path,
    src: Path,
    root: Path,
    harness_name: str,
    allowed_root: Path,
    authorize: AuthorizeFn | None,
    harness_root: Path | None = None,
    project_root: Path | None = None,
    profile_body: str | None = None,
) -> list[MaterializationResult]:
    """Merge-write an operator-owned file with backup, diff, and gate.

    The Apothem-managed content (a sentinel block for Markdown anchors, the
    key-merged object for JSON config) is folded into the operator's file so
    operator content is preserved. Path tokens inside the template body are
    rendered first per ``render_content_tokens``. For ``sentinel_merge`` anchors,
    *profile_body* (the projected shared-profile managed block) is appended to
    the template governance so the anchor's managed block carries both. A
    unified diff is recorded on the result. When the change is a non-additive
    overwrite of an existing file and an *authorize* gate is supplied, the gate
    is consulted per target; declining skips the write and leaves the operator
    file untouched.
    """
    content = render_content_tokens(
        src.read_text(encoding="utf-8"),
        harness_root=harness_root,
        project_root=project_root,
    )
    if entry.mode == "sentinel_merge" and profile_body:
        content = f"{content.rstrip()}\n\n{profile_body}"
    existed = target.exists()
    before = ""
    if existed:
        with contextlib.suppress(OSError):
            before = target.read_text(encoding="utf-8")
    merged = _operator_owned_merge_text(entry, target, content, existed=existed)
    diff = _unified_diff(before, merged, target)
    detail: dict[str, str] = {"ownership_class": entry.ownership_class}
    if diff:
        detail["diff"] = diff
    if existed and before != merged:
        detail["destructive_gate"] = "required"
        if authorize is not None and not authorize(
            AuthorizationRequest(
                harness=harness_name,
                path=_path_text(target),
                operation=entry.mode,
                ownership_class=entry.ownership_class,
                diff=diff,
            )
        ):
            return [
                _with_detail(
                    _result(
                        "skipped",
                        entry.mode,
                        target,
                        "operator declined the managed-block change",
                        source=src,
                    ),
                    detail,
                )
            ]
    result = write_bytes_safely(
        target,
        merged.encode("utf-8"),
        install_root=root,
        harness_name=harness_name,
        operation=entry.mode,
        source=src,
        allowed_root=allowed_root,
    )
    return [_with_detail(result, detail)]


def apply_sentinel_merge(
    entry: InstallEntry,
    *,
    harness_root: Path | None = None,
    project_root: Path | None = None,
    harness_name: str = "manual",
    authorize: AuthorizeFn | None = None,
    profile_body: str | None = None,
) -> list[MaterializationResult]:
    """Apply a ``sentinel_merge`` entry: fold a managed block into an anchor.

    When *profile_body* is supplied (the projected shared profile), it is folded
    into the anchor's managed block alongside the template governance.
    """
    target = resolve_target(
        entry.target, harness_root=harness_root, project_root=project_root
    )
    src = resolve_source(entry.source)
    if not src.is_file():
        return [
            _result(
                "skipped",
                "sentinel_merge",
                target,
                "source file does not exist",
                source=src,
            )
        ]
    return _apply_operator_owned_file(
        entry,
        target=target,
        src=src,
        root=_root_for(harness_root, project_root),
        harness_name=harness_name,
        allowed_root=_allowed_write_root(harness_root, project_root),
        authorize=authorize,
        harness_root=harness_root,
        project_root=project_root,
        profile_body=profile_body,
    )
