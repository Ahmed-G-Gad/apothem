# SPDX-License-Identifier: MIT

"""Surgical removal of Apothem's contribution from operator-owned configs."""

from __future__ import annotations

import contextlib
import json
from dataclasses import replace
from pathlib import Path

import yaml

from apothem.lib.harness_materializer import (
    remove_managed_block,
)

from .install_driver_backup import _guarded_unlink, backup_existing, write_bytes_safely
from .install_driver_jsonmerge import _is_apothem_hook
from .install_driver_pathsafety import _validate_target_path
from .install_driver_types import (
    _REMOVE_KEY,
    MaterializationResult,
    _path_text,
    _result,
)


def _remove_apothem_hook_handlers(existing_entries: object) -> object:
    """Strip Apothem hook handlers from one hooks event's matcher list.

    The inverse of :func:`_merge_hooks` for a single event: walks the operator's
    matcher entries, drops every handler :func:`_is_apothem_hook` recognizes, and
    drops a matcher entry once its ``hooks`` list is emptied (an empty-hooks
    matcher entry is meaningless — an Apothem matcher's sibling attributes such as
    ``sequential`` go with it). An operator-authored handler under any matcher
    survives, keeping that matcher entry alive. Returns :data:`_REMOVE_KEY` when
    no matcher entry survives, so the caller drops the ``hooks`` event entirely.
    """
    if not isinstance(existing_entries, list):
        return existing_entries
    retained: list[object] = []
    for entry in existing_entries:
        if not isinstance(entry, dict):
            retained.append(entry)
            continue
        handlers = entry.get("hooks")
        if not isinstance(handlers, list):
            retained.append(entry)
            continue
        kept_handlers = [
            handler for handler in handlers if not _is_apothem_hook(handler)
        ]
        if not kept_handlers:
            # Every handler under this matcher was Apothem's: drop the entry.
            continue
        survivor = dict(entry)
        survivor["hooks"] = kept_handlers
        retained.append(survivor)
    if not retained:
        return _REMOVE_KEY
    return retained


def _remove_apothem_hooks(
    existing_hooks: object,
    template_hooks: object,
) -> object:
    """Strip Apothem-managed handlers from an operator ``hooks`` object.

    Each event the template contributed is filtered through
    :func:`_remove_apothem_hook_handlers`; an event the operator added that the
    template never wrote is preserved untouched. Returns :data:`_REMOVE_KEY` when
    the resulting hooks object is empty, so the parent drops the key.
    """
    if not isinstance(existing_hooks, dict):
        return existing_hooks
    template = template_hooks if isinstance(template_hooks, dict) else {}
    result: dict[str, object] = {}
    for event_name, existing_entries in existing_hooks.items():
        if event_name not in template:
            result[event_name] = existing_entries
            continue
        stripped = _remove_apothem_hook_handlers(existing_entries)
        if stripped is _REMOVE_KEY:
            continue
        result[event_name] = stripped
    if not result:
        return _REMOVE_KEY
    return result


def _remove_apothem_list_items(
    existing: list[object], template: list[object]
) -> object:
    """Drop the items the template contributed from an operator list.

    Removes one occurrence per template item (operator-added entries and
    operator duplicates beyond the template's count survive). Returns
    :data:`_REMOVE_KEY` only when the operator list is left empty *and* the
    template list was non-empty — an operator who kept an Apothem list key but
    emptied it of operator content carried only Apothem items, so the key goes.
    """
    remaining = list(existing)
    for item in template:
        with contextlib.suppress(ValueError):
            remaining.remove(item)
    if not remaining and template:
        return _REMOVE_KEY
    return remaining


def _remove_apothem_values(existing: object, template: object) -> object:
    """Return *existing* with Apothem's *template* contribution removed.

    The structural inverse of the install-side overlay merge. Recurses through
    mappings: a key whose operator value equals the template value is removed
    (it was purely Apothem's); a key the operator overrode to a different value
    or added beyond the template is kept; nested mappings recurse; ``hooks`` is
    handled by the dedicated handler-aware stripper; list-valued keys drop the
    template-contributed items and keep operator-added ones. Returns
    :data:`_REMOVE_KEY` when a mapping is emptied of all operator content so the
    parent drops the key. Non-mapping *existing* is returned unchanged (the
    caller decides container-level deletion).
    """
    if not isinstance(existing, dict) or not isinstance(template, dict):
        return existing
    result: dict[str, object] = {}
    for key, value in existing.items():
        if key not in template:
            # Operator-added key absent from the Apothem template: always kept.
            result[key] = value
            continue
        template_value = template[key]
        if key == "hooks" and isinstance(value, dict):
            stripped_hooks = _remove_apothem_hooks(value, template_value)
            if stripped_hooks is not _REMOVE_KEY:
                result[key] = stripped_hooks
            continue
        if isinstance(value, dict) and isinstance(template_value, dict):
            reduced = _remove_apothem_values(value, template_value)
            if reduced is not _REMOVE_KEY:
                result[key] = reduced
            continue
        if isinstance(value, list) and isinstance(template_value, list):
            reduced_list = _remove_apothem_list_items(value, template_value)
            if reduced_list is not _REMOVE_KEY:
                result[key] = reduced_list
            continue
        if value == template_value:
            # Purely Apothem's contribution: drop it.
            continue
        # Operator overrode the value: keep the operator's version.
        result[key] = value
    if not result:
        return _REMOVE_KEY
    return result


def _drop_owned_top_keys(
    operator: dict[str, object], apothem_keys: frozenset[str]
) -> dict[str, object]:
    """Drop the *apothem_keys* top-level keys Apothem fully owns from *operator*.

    Profile-derived materializer keys (hermes ``auxiliary``, qwen ``mcpServers``)
    carry operator-data-shaped values the empty-profile template cannot
    reproduce, so the structured value match never recognizes them. The adapter
    declares the top-level namespaces it fully owns; those are removed wholesale
    here, while every other operator key flows on to the value-level recursion.
    """
    return {key: value for key, value in operator.items() if key not in apothem_keys}


def _strip_apothem_json(
    operator_text: str,
    template_text: str,
    *,
    apothem_keys: frozenset[str] = frozenset(),
) -> str | None:
    """Return *operator_text* JSON with Apothem's *template_text* keys removed.

    Parses both documents, removes Apothem's recursive contribution (plus any
    *apothem_keys* top-level namespaces Apothem fully owns), and re-dumps the
    operator remainder. Returns ``None`` when the remainder is an empty object
    (the file became Apothem-only and the caller should delete it). Returns the
    operator text unchanged when either side is unparseable JSON (never destroy
    content the merge inverse cannot reason about).
    """
    try:
        operator = json.loads(operator_text)
        template = json.loads(template_text)
    except json.JSONDecodeError:
        return operator_text
    if isinstance(operator, dict) and apothem_keys:
        operator = _drop_owned_top_keys(operator, apothem_keys)
    reduced = _remove_apothem_values(operator, template)
    if reduced is _REMOVE_KEY:
        return None
    if isinstance(reduced, dict) and not reduced:
        return None
    return json.dumps(reduced, indent=2, ensure_ascii=False) + "\n"


def _strip_apothem_yaml(
    operator_text: str,
    template_text: str,
    *,
    apothem_keys: frozenset[str] = frozenset(),
) -> str | None:
    """Return *operator_text* YAML with Apothem's *template_text* keys removed.

    The YAML mirror of :func:`_strip_apothem_json`: parse both documents, remove
    Apothem's recursive contribution (plus any *apothem_keys* top-level
    namespaces Apothem fully owns), re-dump the operator remainder. Returns
    ``None`` when the remainder is empty (delete) and the operator text unchanged
    when either side is unparseable (never destroy what the inverse cannot map).
    PyYAML round-trips values, not comments, so a managed header comment is not
    reproduced — operator value keys are what survive.
    """
    try:
        operator = yaml.safe_load(operator_text)
        template = yaml.safe_load(template_text)
    except yaml.YAMLError:
        return operator_text
    if operator is None:
        # yaml.safe_load maps an empty OR a comment-only document to None.
        # Apothem only ever contributes value keys, never bare comments, so a
        # document that still carries text (operator comments) is pure operator
        # content — preserve it. Delete only when the document is genuinely
        # empty, mirroring _strip_apothem_json's "never destroy content the
        # inverse cannot reason about" contract.
        return None if not operator_text.strip() else operator_text
    if not isinstance(operator, dict):
        return operator_text
    if apothem_keys:
        operator = _drop_owned_top_keys(operator, apothem_keys)
    template_dict = template if isinstance(template, dict) else {}
    reduced = _remove_apothem_values(operator, template_dict)
    if reduced is _REMOVE_KEY:
        return None
    if isinstance(reduced, dict) and not reduced:
        return None
    return yaml.safe_dump(reduced, sort_keys=False, allow_unicode=True)


def _surgical_remove_from_target(
    target: Path,
    template_text: str,
    *,
    mode: str,
    install_root: Path,
    harness_name: str,
    allowed_root: Path,
    apothem_keys: frozenset[str] = frozenset(),
) -> MaterializationResult | None:
    """Surgically remove Apothem's contribution from one operator-owned target.

    The reversal of the install-side operator-owned write. Backs the target up
    under the Apothem backup root first, then:

    - ``sentinel_merge`` anchors: strip the managed block via
      :func:`remove_managed_block`; delete when the remainder is whitespace-only,
      else atomic-rewrite the operator prose.
    - ``.json`` / ``.yaml`` / ``.yml`` targets: remove only Apothem's keys/hooks
      via the recursive structured stripper (operator-added/overridden keys
      survive), plus any *apothem_keys* top-level namespaces Apothem fully owns;
      delete when the remainder is empty, else atomic-rewrite.
    - Any other suffix: delete when the file content equals the rendered template
      (Apothem-owned, untouched); otherwise leave it in place (never destroy
      unrecognized operator content) — the backup already captured it.

    Returns ``None`` when *target* does not exist (nothing to remove). The
    *template_text* is the rendered Apothem template (path tokens already
    substituted) the install wrote, used to identify Apothem's contribution.
    """
    if not target.exists() or not target.is_file():
        return None
    target_error = _validate_target_path(
        target, allowed_root=allowed_root, operation="surgical_uninstall"
    )
    if target_error is not None:
        return target_error
    try:
        existing = target.read_text(encoding="utf-8")
    except OSError:  # pragma: no cover - defensive
        return None
    backup = backup_existing(
        target,
        install_root=install_root,
        harness_name=harness_name,
        allowed_root=allowed_root,
    )
    suffix = target.suffix.lower()
    remainder: str | None
    if mode == "sentinel_merge":
        stripped = remove_managed_block(existing)
        remainder = None if not stripped.strip() else stripped
    elif suffix == ".json":
        remainder = _strip_apothem_json(
            existing, template_text, apothem_keys=apothem_keys
        )
    elif suffix in {".yaml", ".yml"}:
        remainder = _strip_apothem_yaml(
            existing, template_text, apothem_keys=apothem_keys
        )
    else:
        # Unrecognized operator content: only delete an exact template copy.
        remainder = None if existing == template_text else existing
    if remainder is None:
        result = _guarded_unlink(
            target, allowed_root=allowed_root, operation="surgical_uninstall"
        )
    elif remainder == existing:
        result = _result(
            "unchanged",
            "surgical_uninstall",
            target,
            "no Apothem contribution to remove",
        )
    else:
        result = write_bytes_safely(
            target,
            remainder.encode("utf-8"),
            install_root=install_root,
            harness_name=harness_name,
            operation="surgical_uninstall",
            allowed_root=allowed_root,
        )
    return replace(
        result,
        backup_path=_path_text(backup) if backup is not None else result.backup_path,
    )


def surgically_remove_materialized_config(
    target: Path,
    template_text: str,
    *,
    install_root: Path,
    harness_name: str,
    allowed_root: Path | None = None,
    apothem_keys: frozenset[str] = frozenset(),
) -> MaterializationResult | None:
    """Surgically remove Apothem's keys from an adapter-rendered native config.

    The adapter-uninstall entry point for materializer configs that are not
    manifest entries (hermes ``config.yaml``, open-claw / opencode / qwen-code
    JSON). *template_text* is the config the adapter's materializer renders (from
    an empty profile) used to recognize Apothem's structural contribution.
    *apothem_keys* names the top-level namespaces Apothem fully owns whose values
    are profile-derived (e.g. hermes ``auxiliary``, qwen ``mcpServers``) — these
    carry operator-data-shaped values the empty-profile template cannot reproduce,
    so they are stripped wholesale. Operator-added keys outside this set are
    preserved and an Apothem-only file is deleted. Backs the target up before
    mutation. Returns ``None`` when the target is absent. This is the surgical
    replacement for the retired whole-file ``backup_file_to_sibling`` rename.
    """
    return _surgical_remove_from_target(
        target,
        template_text,
        mode="write_text",
        install_root=install_root,
        harness_name=harness_name,
        allowed_root=allowed_root or install_root,
        apothem_keys=apothem_keys,
    )
