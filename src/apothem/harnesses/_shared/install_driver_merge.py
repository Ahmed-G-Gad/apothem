# SPDX-License-Identifier: MIT

"""Managed-block + JSON/YAML key-merge and the operator-owned write path."""

from __future__ import annotations

import contextlib
import difflib
import json
import re
from dataclasses import dataclass, replace
from pathlib import Path
from string import Template
from typing import Any

from apothem.lib.harness_materializer import (
    merge_managed_block,
)
from apothem.lib.install_ledger import OwnedEntry
from apothem.lib.propagation import (
    InstallEntry,
    resolve_target,
)

from .install_driver_backup import write_bytes_safely
from .install_driver_jsonmerge import (
    _LossyRewriteError,
    _merge_json_settings,
    _overlay_json_settings,
    _read_existing,
    _refused_result,
)
from .install_driver_ownership import (
    MergeOutcome,
    _LegacyOwnership,
    _merge_native_content,
    _operator_json_merge,
    prior_ownership,
)
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
    detail: dict[str, str] = {"ownership_class": ownership_class}
    try:
        existing_text = _read_existing(target)
        merge = _merge_native_content(
            target,
            content,
            before=existing_text,
            harness_root=install_root,
            prior=prior_ownership(harness_name, install_root, target),
        )
    except _LossyRewriteError as refusal:
        return _refused_result("write_text", target, refusal, detail)
    merged = merge.text
    existed = existing_text is not None
    before = existing_text or ""
    diff = _unified_diff(before, merged, target)
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
    return replace(_with_detail(result, detail), owned=merge.owned)


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


_LEADING_HTML_COMMENTS = re.compile(r"\A(?:\s*<!--.*?-->)*\s*", re.S)


def _fold_profile_body(
    entry: InstallEntry, content: str, profile_body: str | None
) -> str:
    """Fold the projected *profile_body* into a ``sentinel_merge`` template.

    The default ``profile_position: last`` appends the profile after the
    template governance. ``first`` puts it ahead of the governance, after the
    template's leading HTML comments (the SPDX header), for a harness that may
    not process a long instruction file in full. Any other entry, or no
    profile, returns *content* unchanged.
    """
    if entry.mode != "sentinel_merge" or not profile_body:
        return content
    if entry.profile_position != "first":
        return f"{content.rstrip()}\n\n{profile_body}"
    split = _LEADING_HTML_COMMENTS.match(content)
    head = split.group(0).strip() if split else ""
    rest = content[split.end() :] if split else content
    lead = f"{head}\n\n" if head else ""
    return f"{lead}{profile_body}\n\n{rest.strip()}"


def _operator_owned_merge_text(
    entry: InstallEntry,
    target: Path,
    content: str,
    *,
    before: str | None,
    hook_root: Path | None = None,
    prior: tuple[OwnedEntry, ...] | _LegacyOwnership = (),
) -> MergeOutcome:
    """Return the prospective merged text (and ownership) for a target.

    *before* is the target's current text (``None`` when it does not exist).
    ``sentinel_merge`` entries fold *content* into the operator anchor as a
    sentinel-delimited managed block, preserving operator prose outside the
    block. ``write_text`` entries on an existing JSON target run the JSON
    merge with the incoming template authoritative: template-carried keys
    update in place so fixes ship to existing installs, while operator-added
    keys absent from the template are preserved, and the operator's bytes are
    kept when no value changes. The backup-before-replace and
    destructive-authorization gate still guard the write. A non-existent
    target merges to *content* verbatim.

    Raises:
        _LossyRewriteError: When an existing JSON target cannot be rewritten
            losslessly (see :func:`_operator_json_merge`).
    """
    if entry.mode == "sentinel_merge":
        return MergeOutcome(merge_managed_block(before or "", content), None)
    if target.suffix.lower() != ".json":
        return MergeOutcome(content, None)
    if before is not None and before.strip():
        return _operator_json_merge(
            target, before, content, harness_root=hook_root, prior=prior
        )
    return _merge_native_content(target, content, before=None)


@dataclass(frozen=True)
class _OperatorOwnedPreview:
    """The no-write prospective outcome of one operator-owned manifest entry."""

    target: Path
    outcome: MaterializationOutcome
    diff: str
    gate_required: bool
    refusal: _LossyRewriteError | None = None


def _operator_owned_preview(
    entry: InstallEntry,
    *,
    harness_root: Path | None,
    project_root: Path | None,
    profile_body: str | None = None,
    harness_name: str = "manual",
) -> _OperatorOwnedPreview | None:
    """Return the prospective outcome, unified diff and gate flag for an entry.

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
    gated write would show. A target the real write would refuse (see
    :func:`_operator_json_merge`) previews as ``error`` and carries the refusal.
    ``None`` when the source file is absent (nothing to preview — the plan
    validator already errors on a missing source, so this is a defensive
    fallback).
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
    content = _fold_profile_body(entry, content, profile_body)
    try:
        existing_text = _read_existing(target)
        after = _operator_owned_merge_text(
            entry,
            target,
            content,
            before=existing_text,
            hook_root=harness_root or project_root,
            prior=prior_ownership(
                harness_name, _root_for(harness_root, project_root), target
            ),
        ).text
    except _LossyRewriteError as refusal:
        return _OperatorOwnedPreview(target, "error", "", False, refusal)
    existed = existing_text is not None
    before = existing_text or ""
    diff = _unified_diff(before, after, target)
    gate_required = existed and before != after
    outcome: MaterializationOutcome = (
        "created" if not existed else ("updated" if gate_required else "unchanged")
    )
    return _OperatorOwnedPreview(target, outcome, diff, gate_required)


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
    *profile_body* (the projected shared-profile managed block) is folded into
    the template governance, after it or before it per the entry's
    ``profile_position``, so the anchor's managed block carries both. A
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
    content = _fold_profile_body(entry, content, profile_body)
    detail: dict[str, str] = {"ownership_class": entry.ownership_class}
    try:
        existing_text = _read_existing(target)
        merge = _operator_owned_merge_text(
            entry,
            target,
            content,
            before=existing_text,
            hook_root=harness_root or project_root,
            prior=prior_ownership(harness_name, root, target),
        )
    except _LossyRewriteError as refusal:
        return [_refused_result(entry.mode, target, refusal, detail, source=src)]
    merged = merge.text
    existed = existing_text is not None
    before = existing_text or ""
    diff = _unified_diff(before, merged, target)
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
    return [replace(_with_detail(result, detail), owned=merge.owned)]


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
