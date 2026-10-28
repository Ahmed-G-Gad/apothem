# SPDX-License-Identifier: MIT

"""Own-file native hook registrations: the ``native_hooks`` install mode.

Some harnesses read hooks from a directory of small JSON files, one per
author, rather than from a settings file the operator shares with the tool.
Apothem writes one of those files, named ``apothem.json``, and the file is the
Apothem-owned place its hook entries live. The mode renders a template into
that file, and tells Apothem's entries from any entry the operator added to the
same file by what each entry's command runs: the dispatcher under the project
(``.../hooks/dispatch.py``), the same test :func:`is_apothem_hook` applies to a
shared settings file. The test reads the command text, so it holds whether or
not the install ledger has a record, and whether or not the interpreter token
in the template can be rendered again (an uninstall renders without it).

Two document shapes are understood, because the two vendors use them:

* a **list** shape, ``{"version": "v1", "hooks": [<hook>, ...]}``, where a hook
  carries its command at ``action.command`` (Kiro, https://kiro.dev/docs/hooks/);
* an **event map** shape, ``{"version": 1, "hooks": {<event>: [<hook>, ...]}}``,
  where a hook carries ``bash``, ``powershell`` or ``command`` (GitHub Copilot,
  https://docs.github.com/en/copilot/reference/hooks-reference).

Neither shape nests handlers under a matcher the way Claude Code's settings do,
so the Claude-shaped merge and removal in :mod:`install_driver_jsonmerge` and
:mod:`install_driver_ownership` do not apply: applied to an event map they add a
stray ``"hooks": []`` to every entry.

An install writes the rendered template as the whole file when the file is
absent, empty, unreadable as JSON, not a hook registration, or holds nothing but
Apothem's own entries, so a repeat install is byte-identical. When the file also
holds operator entries, they are kept ahead of Apothem's. A previous file that is
replaced is copied to the Apothem backup root first. An uninstall removes
Apothem's entries, deletes the file when nothing else is left in it, and leaves
a file it cannot read exactly as it is.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Final

from apothem.lib.propagation import InstallEntry, resolve_target

from .install_driver_backup import _guarded_unlink, backup_existing, write_bytes_safely
from .install_driver_jsonmerge import is_apothem_hook
from .install_driver_merge import _unified_diff, render_content_tokens
from .install_driver_pathsafety import (
    _allowed_write_root,
    _root_for,
    _validate_target_path,
)
from .install_driver_types import (
    MaterializationOutcome,
    MaterializationResult,
    _path_text,
    _result,
    _with_detail,
    resolve_source,
)

#: The install-entry mode this module serves.
HOOK_FILE_MODE: Final[str] = "native_hooks"

#: Entry keys whose string value is a command line the hook runs.
_COMMAND_KEYS: Final[tuple[str, ...]] = ("command", "bash", "powershell")


def _command_text(hook: object) -> str:
    """Return every command line *hook* runs, joined, or ``""`` for a non-command hook."""
    if not isinstance(hook, dict):
        return ""
    parts = [hook.get(key) for key in _COMMAND_KEYS]
    action = hook.get("action")
    if isinstance(action, dict):
        parts.append(action.get("command"))
    return " ".join(part for part in parts if isinstance(part, str))


def _is_ours(hook: object, root: Path) -> bool:
    """Return True when *hook* runs the Apothem dispatcher installed under *root*."""
    text = _command_text(hook)
    return bool(text) and is_apothem_hook({"command": text}, harness_root=root)


def _without_ours(doc: object, root: Path) -> tuple[dict[str, object], int] | None:
    """Return *doc* without Apothem's hooks, plus how many hooks remain.

    ``None`` when *doc* is not a hook registration of either shape.
    """
    if not isinstance(doc, dict):
        return None
    hooks = doc.get("hooks")
    if isinstance(hooks, list):
        kept = [hook for hook in hooks if not _is_ours(hook, root)]
        return {**doc, "hooks": kept}, len(kept)
    if isinstance(hooks, dict):
        events: dict[str, object] = {}
        remaining = 0
        for event, listed in hooks.items():
            if not isinstance(listed, list):
                events[event] = listed
                remaining += 1
                continue
            survivors = [hook for hook in listed if not _is_ours(hook, root)]
            if survivors or not listed:
                events[event] = survivors
                remaining += len(survivors)
        return {**doc, "hooks": events}, remaining
    return None


def _dump(doc: object) -> str:
    return json.dumps(doc, indent=2, ensure_ascii=False) + "\n"


def _combine(
    operator: dict[str, object], incoming: dict[str, object]
) -> dict[str, object]:
    """Return the operator's registration with Apothem's hooks added after theirs."""
    merged = {**operator, **{k: v for k, v in incoming.items() if k != "hooks"}}
    theirs, ours = operator.get("hooks"), incoming.get("hooks")
    if isinstance(ours, list) and isinstance(theirs, list):
        merged["hooks"] = [*theirs, *ours]
    elif isinstance(ours, dict) and isinstance(theirs, dict):
        events = dict(theirs)
        for event, listed in ours.items():
            held = events.get(event)
            events[event] = [*(held if isinstance(held, list) else []), *listed]
        merged["hooks"] = events
    else:
        merged["hooks"] = ours
    return merged


def merge_registration(existing: str | None, rendered: str, *, root: Path) -> str:
    """Return the file text an install writes over *existing*.

    *rendered* is the template with its tokens resolved. It is returned as is
    unless *existing* holds hooks the operator added, in which case those stay
    ahead of Apothem's.
    """
    if existing is None or not existing.strip():
        return rendered
    try:
        kept = _without_ours(json.loads(existing), root)
        incoming = json.loads(rendered)
    except ValueError:
        return rendered
    if kept is None or not isinstance(incoming, dict):
        return rendered
    doc, remaining = kept
    if remaining == 0 and set(doc) <= {"version", "hooks"}:
        return rendered
    if type(doc.get("hooks")) is not type(incoming.get("hooks")):
        # The operator's file is the other vendor shape; nothing of it fits.
        return rendered
    return _dump(_combine(doc, incoming))


def strip_registration(existing: str, *, root: Path) -> str | None:
    """Return *existing* without Apothem's hooks; ``None`` means delete the file.

    Text that is not a readable hook registration comes back unchanged, so an
    uninstall never destroys what it cannot reason about. A file keeps its other
    top-level keys; it is deleted only when it held nothing but Apothem's hooks.
    """
    try:
        before = json.loads(existing)
    except ValueError:
        return existing
    stripped = _without_ours(before, root)
    if stripped is None:
        return existing
    doc, remaining = stripped
    if doc == before:
        return existing
    if remaining == 0 and set(doc) <= {"version", "hooks"}:
        return None
    return _dump(doc)


def _read(target: Path) -> str | None:
    try:
        return target.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _rendered(
    entry: InstallEntry, *, harness_root: Path | None, project_root: Path | None
) -> str | None:
    src = resolve_source(entry.source)
    if not src.is_file():
        return None
    return render_content_tokens(
        src.read_text(encoding="utf-8"),
        harness_root=harness_root,
        project_root=project_root,
    )


def apply_native_hooks(
    entry: InstallEntry,
    *,
    harness_root: Path | None = None,
    project_root: Path | None = None,
    harness_name: str = "manual",
) -> list[MaterializationResult]:
    """Apply a ``native_hooks`` entry: write the rendered registration file."""
    target = resolve_target(
        entry.target, harness_root=harness_root, project_root=project_root
    )
    text = _rendered(entry, harness_root=harness_root, project_root=project_root)
    if text is None:
        return [
            _result(
                "skipped",
                entry.mode,
                target,
                "source file does not exist",
                source=resolve_source(entry.source),
            )
        ]
    root = _root_for(harness_root, project_root)
    merged = merge_registration(_read(target), text, root=root)
    result = write_bytes_safely(
        target,
        merged.encode("utf-8"),
        install_root=root,
        harness_name=harness_name,
        operation=entry.mode,
        source=resolve_source(entry.source),
        allowed_root=_allowed_write_root(harness_root, project_root),
    )
    return [_with_detail(result, {"ownership_class": entry.ownership_class})]


def preview_native_hooks(
    entry: InstallEntry,
    *,
    harness_root: Path | None,
    project_root: Path | None,
) -> tuple[MaterializationOutcome, str]:
    """Return the outcome and unified diff :func:`apply_native_hooks` would produce."""
    target = resolve_target(
        entry.target, harness_root=harness_root, project_root=project_root
    )
    text = _rendered(entry, harness_root=harness_root, project_root=project_root)
    if text is None:
        return "skipped", ""
    before = _read(target)
    after = merge_registration(before, text, root=_root_for(harness_root, project_root))
    if before is None:
        return "created", _unified_diff("", after, target)
    if before == after:
        return "unchanged", ""
    return "updated", _unified_diff(before, after, target)


def release_native_hooks(
    entry: InstallEntry,
    *,
    harness_root: Path | None,
    project_root: Path | None,
    harness_name: str,
) -> MaterializationResult | None:
    """Remove Apothem's hooks from a ``native_hooks`` entry's file on uninstall.

    The file is backed up under the Apothem backup root first. ``None`` when the
    file does not exist.
    """
    target = resolve_target(
        entry.target, harness_root=harness_root, project_root=project_root
    )
    existing = _read(target) if target.is_file() else None
    if existing is None:
        return None
    root = _root_for(harness_root, project_root)
    allowed = _allowed_write_root(harness_root, project_root)
    error = _validate_target_path(target, allowed_root=allowed, operation=entry.mode)
    if error is not None:
        return error
    remainder = strip_registration(existing, root=root)
    if remainder == existing:
        return _result(
            "unchanged", "surgical_uninstall", target, "no Apothem hook to remove"
        )
    backup = backup_existing(
        target, install_root=root, harness_name=harness_name, allowed_root=allowed
    )
    if remainder is None:
        result = _guarded_unlink(
            target, allowed_root=allowed, operation="surgical_uninstall"
        )
    else:
        result = write_bytes_safely(
            target,
            remainder.encode("utf-8"),
            install_root=root,
            harness_name=harness_name,
            operation="surgical_uninstall",
            allowed_root=allowed,
        )
    return replace(
        result, backup_path=_path_text(backup) if backup is not None else None
    )
