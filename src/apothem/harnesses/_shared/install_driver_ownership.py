# SPDX-License-Identifier: MIT

"""Ownership-recording merge and removal for operator-owned JSON / YAML configs.

Install merges Apothem's keys into settings files the operator also edits
(Claude Code ``settings.json`` permission lists, Qwen Code ``mcpServers``,
OpenCode ``mcp``, the Hermes ``config.yaml``). Equality with Apothem's template
is not proof of ownership: an operator's own ``permissions.allow`` entry
``"Read"`` or ``$schema`` key can equal Apothem's value. So each merge records,
per target, the exact entries Apothem added (:class:`OwnedEntry` in the install
ledger), and the next install and uninstall act only on those:

* install strips the previously-owned entries first, then merges the incoming
  config into the operator's remainder (lists are unioned, operator items
  first), and records what it added;
* uninstall removes the owned entries, plus Apothem's hook handlers (identified
  by path, see :func:`_is_apothem_hook`), and drops containers Apothem created
  once they are empty.

An install whose ledger record predates ownership recording falls back once to
the old equality rule, then records ownership from then on.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import yaml

from apothem.lib import install_ledger, lenient_json
from apothem.lib.install_ledger import LedgerTarget, OwnedEntry

from .install_driver_jsonmerge import (
    _is_apothem_hook,
    _leading_comment_block,
    _lossy_rewrite,
    _LossyRewriteError,
    _merge_hooks,
    _yaml_has_operator_comments,
)


class _LegacyOwnership:
    """Marker: the current install record predates ownership recording."""


#: The ledger records an install for this target but no owned entries (an
#: older record): fall back to treating values equal to Apothem's as its own.
LEGACY_OWNERSHIP: Final[_LegacyOwnership] = _LegacyOwnership()

#: What Apothem owned in a target before this pass.
PriorOwnership = tuple[OwnedEntry, ...] | _LegacyOwnership

_MISSING: Final[object] = object()


@dataclass(frozen=True)
class MergeOutcome:
    """The merged text for a target, plus the entries Apothem now owns in it.

    ``owned`` is ``None`` for a target whose format carries no structured
    ownership (a Markdown anchor, a TOML file).
    """

    text: str
    owned: tuple[OwnedEntry, ...] | None


def current_target(harness_name: str, root: Path, target: Path) -> LedgerTarget | None:
    """Return *target*'s entry in the current install record, if any.

    An unreadable ledger reads as "no record" here: the caller then treats the
    target as freshly installed, which never removes operator content.
    """
    try:
        record = install_ledger.current_install_record(harness_name, root=root)
    except install_ledger.LedgerError:
        return None
    if record is None:
        return None
    wanted = str(target)
    return next((entry for entry in record.targets if entry.path == wanted), None)


def prior_ownership(harness_name: str, root: Path, target: Path) -> PriorOwnership:
    """Return what Apothem owned in *target* before this pass."""
    recorded = current_target(harness_name, root, target)
    if recorded is None:
        return ()
    if recorded.owned is None:
        return LEGACY_OWNERSHIP
    return recorded.owned


def _navigate(doc: object, path: tuple[str, ...]) -> object:
    """Return the value at *path* inside nested mappings, or ``_MISSING``."""
    node = doc
    for key in path:
        if not isinstance(node, dict) or key not in node:
            return _MISSING
        node = node[key]
    return node


def strip_owned(doc: object, owned: tuple[OwnedEntry, ...]) -> object:
    """Return a copy of *doc* without the entries Apothem owns.

    A ``key`` is removed while it still holds the value Apothem wrote (an
    operator edit to it is kept); an ``item`` is removed from its list; a
    ``container`` is removed only once it is empty, deepest first, so operator
    entries added inside an Apothem-created mapping or list survive.
    """
    result = copy.deepcopy(doc)
    if not isinstance(result, dict):
        return result
    for entry in owned:
        if entry.kind == "item":
            holder = _navigate(result, entry.path)
            if isinstance(holder, list) and entry.value in holder:
                holder.remove(entry.value)
        elif entry.kind == "key" and entry.path:
            parent = _navigate(result, entry.path[:-1])
            key = entry.path[-1]
            if (
                isinstance(parent, dict)
                and key in parent
                and parent[key] == entry.value
            ):
                del parent[key]
    containers = sorted(
        (entry for entry in owned if entry.kind == "container" and entry.path),
        key=lambda entry: len(entry.path),
        reverse=True,
    )
    for entry in containers:
        parent = _navigate(result, entry.path[:-1])
        key = entry.path[-1]
        if isinstance(parent, dict) and parent.get(key, _MISSING) in ({}, []):
            del parent[key]
    return result


def _strip_equal(existing: object, incoming: object) -> object:
    """Legacy ownership: drop the values of *existing* equal to *incoming*'s.

    Used once, for a target whose ledger record predates ownership recording:
    keys and list items equal to Apothem's incoming values are taken to be
    Apothem's own (the previous behaviour). ``hooks`` are left to the
    handler-aware hook merge.
    """
    if not isinstance(existing, dict) or not isinstance(incoming, dict):
        return existing
    result: dict[str, object] = {}
    for key, value in existing.items():
        if key not in incoming or key == "hooks":
            result[key] = value
            continue
        theirs = incoming[key]
        if isinstance(value, dict) and isinstance(theirs, dict):
            reduced = _strip_equal(value, theirs)
            if reduced or not value:
                result[key] = reduced
        elif isinstance(value, list) and isinstance(theirs, list):
            kept = [item for item in value if item not in theirs]
            if kept or not value:
                result[key] = kept
        elif value != theirs:
            result[key] = value
    return result


def ownership_merge(
    base: dict[str, object],
    incoming: dict[str, object],
    *,
    harness_root: Path | None,
) -> dict[str, object]:
    """Merge *incoming* into the operator's *base* (Apothem entries removed).

    Mappings merge recursively; ``hooks`` merge handler-aware; lists are the
    union with the operator's items first; scalars take the incoming value.
    Keys only in *base* are kept.
    """
    merged: dict[str, object] = dict(base)
    for key, value in incoming.items():
        current = base.get(key, _MISSING)
        if key == "hooks" and isinstance(current, dict) and isinstance(value, dict):
            merged[key] = _merge_hooks(current, value, harness_root=harness_root)
        elif isinstance(current, dict) and isinstance(value, dict):
            merged[key] = ownership_merge(current, value, harness_root=harness_root)
        elif isinstance(current, list) and isinstance(value, list):
            merged[key] = current + [item for item in value if item not in current]
        else:
            merged[key] = value
    return merged


def owned_additions(
    base: object, incoming: dict[str, object], path: tuple[str, ...] = ()
) -> list[OwnedEntry]:
    """Return the entries *incoming* adds to the operator's *base*.

    ``hooks`` handlers are owned by path, not recorded here; only a ``hooks``
    mapping Apothem creates is recorded (as a container).
    """
    owned: list[OwnedEntry] = []
    for key, value in incoming.items():
        at = (*path, key)
        current = base.get(key, _MISSING) if isinstance(base, dict) else _MISSING
        if key == "hooks" and isinstance(value, dict):
            if current is _MISSING:
                owned.append(OwnedEntry(at, "container"))
            continue
        if isinstance(value, dict):
            if current is _MISSING:
                owned.append(OwnedEntry(at, "container"))
                owned.extend(owned_additions({}, value, at))
            elif isinstance(current, dict):
                owned.extend(owned_additions(current, value, at))
        elif isinstance(value, list):
            if current is _MISSING:
                owned.append(OwnedEntry(at, "container"))
                owned.extend(OwnedEntry(at, "item", item) for item in value)
            elif isinstance(current, list):
                owned.extend(
                    OwnedEntry(at, "item", item)
                    for item in value
                    if item not in current
                )
        elif current is _MISSING:
            owned.append(OwnedEntry(at, "key", value))
    return owned


def _merge_mapping(
    existing: dict[str, object],
    incoming: dict[str, object],
    *,
    prior: PriorOwnership,
    harness_root: Path | None,
) -> tuple[dict[str, object], tuple[OwnedEntry, ...]]:
    """Return the merged mapping and the entries Apothem owns in it.

    The base the incoming config merges into is the operator's own content:
    Apothem's previously-owned entries and its hook handlers removed first.
    """
    operator_only = copy.deepcopy(existing)
    _strip_hook_handlers(operator_only, harness_root)
    if isinstance(prior, _LegacyOwnership):
        if operator_only.get("hooks") == {}:
            del operator_only["hooks"]
        base_obj = _strip_equal(operator_only, incoming)
    else:
        base_obj = strip_owned(operator_only, prior)
    base = base_obj if isinstance(base_obj, dict) else {}
    merged = ownership_merge(base, incoming, harness_root=harness_root)
    return merged, tuple(owned_additions(base, incoming))


def _operator_json_merge(
    target: Path,
    existing_text: str,
    content: str,
    *,
    harness_root: Path | None = None,
    prior: PriorOwnership = (),
) -> MergeOutcome:
    """Merge Apothem's JSON *content* into an existing operator JSON config.

    When the merge changes no value, the operator's bytes come back untouched,
    so their formatting is kept. A file that parses only as JSONC or JSON5
    cannot be rewritten without losing its comments or syntax, so a needed
    change raises :class:`_LossyRewriteError`; so does a file that does not
    parse at all, unless the incoming config is empty (nothing to merge).
    """
    incoming = json.loads(content)
    strict = True
    try:
        existing = json.loads(existing_text)
    except json.JSONDecodeError:
        strict = False
        try:
            existing = lenient_json.loads(existing_text)
        except lenient_json.LenientJSONError as exc:
            if incoming == {}:
                return MergeOutcome(existing_text, ())
            raise _LossyRewriteError(
                f"{target} is not valid JSON, JSONC or JSON5: {exc}",
                f"Repair {target.name} (or move it aside) and re-run.",
            ) from exc
    if not isinstance(existing, dict) or not isinstance(incoming, dict):
        return MergeOutcome(existing_text, ())
    merged, owned = _merge_mapping(
        existing, incoming, prior=prior, harness_root=harness_root
    )
    if merged == existing:
        return MergeOutcome(existing_text, owned)
    if not strict:
        raise _lossy_rewrite(
            target,
            "comments, trailing commas or JSON5 syntax",
            "JSON",
            existing,
            merged,
        )
    return MergeOutcome(json.dumps(merged, indent=2, ensure_ascii=False) + "\n", owned)


def _operator_yaml_merge(
    target: Path,
    existing_text: str,
    content: str,
    *,
    harness_root: Path | None = None,
    prior: PriorOwnership = (),
) -> MergeOutcome:
    """Merge Apothem's YAML *content* into an existing operator YAML config.

    The YAML mirror of :func:`_operator_json_merge`. PyYAML round-trips values,
    not comments, so a needed change to a file that carries operator comments,
    or to a file that is not a YAML mapping, raises :class:`_LossyRewriteError`.
    """
    incoming = yaml.safe_load(content)
    if not isinstance(incoming, dict):
        return MergeOutcome(content, None)
    try:
        existing = yaml.safe_load(existing_text)
    except yaml.YAMLError as exc:
        if not incoming:
            return MergeOutcome(existing_text, ())
        raise _LossyRewriteError(
            f"{target} is not valid YAML: {exc}",
            f"Repair {target.name} (or move it aside) and re-run.",
        ) from exc
    if existing is None:
        existing = {}
    if not isinstance(existing, dict):
        if not incoming:
            return MergeOutcome(existing_text, ())
        raise _LossyRewriteError(
            f"{target} is not a YAML mapping",
            f"Repair {target.name} (or move it aside) and re-run.",
        )
    merged, owned = _merge_mapping(
        existing, incoming, prior=prior, harness_root=harness_root
    )
    if merged == existing:
        return MergeOutcome(existing_text, owned)
    header = _leading_comment_block(content)
    if _yaml_has_operator_comments(existing_text, header):
        raise _lossy_rewrite(target, "comments", "YAML", existing, merged)
    dumped = yaml.safe_dump(merged, sort_keys=False, allow_unicode=True)
    return MergeOutcome(header + dumped, owned)


def _fresh_ownership(target: Path, content: str) -> tuple[OwnedEntry, ...] | None:
    """Return the entries Apothem owns in a file it creates from *content*."""
    suffix = target.suffix.lower()
    try:
        if suffix == ".json":
            parsed = json.loads(content)
        elif suffix in {".yaml", ".yml"}:
            parsed = yaml.safe_load(content)
        else:
            return None
    except (json.JSONDecodeError, yaml.YAMLError):
        return None
    if parsed is None:
        parsed = {}
    return tuple(owned_additions({}, parsed)) if isinstance(parsed, dict) else ()


def _merge_native_content(
    target: Path,
    content: str,
    *,
    before: str | None,
    harness_root: Path | None = None,
    prior: PriorOwnership = (),
) -> MergeOutcome:
    """Return the prospective merged text (and ownership) for a config file.

    *before* is the operator's current file text (``None`` when the target does
    not exist). JSON and YAML targets key-merge with it, preserving operator
    keys and keeping the operator's bytes when no value changes; other
    suffixes, absent targets and empty files render *content* verbatim.

    Raises:
        _LossyRewriteError: When the existing file cannot be rewritten losslessly.
    """
    if before is None or not before.strip():
        return MergeOutcome(content, _fresh_ownership(target, content))
    suffix = target.suffix.lower()
    if suffix == ".json":
        return _operator_json_merge(
            target, before, content, harness_root=harness_root, prior=prior
        )
    if suffix in {".yaml", ".yml"}:
        return _operator_yaml_merge(
            target, before, content, harness_root=harness_root, prior=prior
        )
    return MergeOutcome(content, None)


def _strip_hook_handlers(doc: dict[str, object], harness_root: Path | None) -> None:
    """Remove Apothem's hook handlers from *doc* in place.

    A matcher entry left with no handler is dropped, then an event left with
    no matcher entry; the ``hooks`` mapping itself is left (empty) for the
    ownership pass to remove when Apothem created it.
    """
    hooks = doc.get("hooks")
    if not isinstance(hooks, dict):
        return
    for event in list(hooks):
        entries = hooks[event]
        if not isinstance(entries, list):
            continue
        kept: list[object] = []
        for entry in entries:
            handlers = entry.get("hooks") if isinstance(entry, dict) else None
            if not isinstance(handlers, list):
                kept.append(entry)
                continue
            survivors = [
                handler
                for handler in handlers
                if not _is_apothem_hook(handler, harness_root=harness_root)
            ]
            if survivors:
                kept.append({**entry, "hooks": survivors})
        if kept:
            hooks[event] = kept
        else:
            del hooks[event]


def remove_owned_text(
    target: Path,
    existing_text: str,
    *,
    owned: tuple[OwnedEntry, ...],
    created: bool | None,
    harness_root: Path | None,
    managed_header: str = "",
) -> str | None:
    """Return *existing_text* with Apothem's owned entries removed.

    Returns the text unchanged when there is nothing of Apothem's to remove or
    the file does not parse; ``None`` when nothing is left and Apothem created
    the file (the caller deletes it).

    Raises:
        _LossyRewriteError: When removing Apothem's entries would require
            rewriting a file that carries comments or JSONC / JSON5 syntax.
    """
    suffix = target.suffix.lower()
    strict = True
    doc: object
    if suffix == ".json":
        try:
            doc = json.loads(existing_text)
        except json.JSONDecodeError:
            strict = False
            try:
                doc = lenient_json.loads(existing_text)
            except lenient_json.LenientJSONError:
                return existing_text
    else:
        try:
            doc = yaml.safe_load(existing_text)
        except yaml.YAMLError:
            return existing_text
        if doc is None:
            return None if not existing_text.strip() else existing_text
        strict = not _yaml_has_operator_comments(existing_text, managed_header)
    if not isinstance(doc, dict):
        return existing_text
    working = copy.deepcopy(doc)
    _strip_hook_handlers(working, harness_root)
    reduced = strip_owned(working, owned)
    if not reduced and (created is True or (created is None and reduced != doc)):
        return None
    if reduced == doc:
        return existing_text
    if not strict:
        raise _LossyRewriteError(
            f"{target} carries comments or JSON5 syntax; removing Apothem's "
            "entries would rewrite it without them",
            f"Remove Apothem's entries from {target.name} by hand.",
        )
    if not reduced:
        return "{}\n" if suffix == ".json" else ""
    if suffix == ".json":
        return json.dumps(reduced, indent=2, ensure_ascii=False) + "\n"
    return yaml.safe_dump(reduced, sort_keys=False, allow_unicode=True)
