# SPDX-License-Identifier: MIT

"""Structured-value merge for operator-owned JSON / YAML configs.

The key-merge primitives the install path folds Apothem's managed values into an
operator's config with (the overlay merge, the hook-handler merge, the list
union), plus the lossless-rewrite guard: an operator file that does not parse,
or that parses only as JSONC / JSON5 / commented YAML, is left byte-identical
when the merge changes no value and refused (``config.unparseable``) when it
would, so a re-serialization never silently drops the operator's comments or
syntax.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final

from .install_driver_types import MaterializationResult, _result, _with_detail

#: Substrings that identify an Apothem-managed hook handler when no harness root
#: is known (the legacy, unscoped check). Covers both the module-invocation
#: spelling and the installed script-path spelling.
_APOTHEM_HOOK_MARKERS: tuple[str, ...] = (
    "apothem.hooks.dispatch",
    "apothem.conformity.gate",
    "hooks/dispatch.py",
    "conformity/gate.py",
)

#: Module spellings that name Apothem's own hook entry points. They identify a
#: handler as Apothem's wherever it lives.
_APOTHEM_HOOK_MODULES: tuple[str, ...] = (
    "apothem.hooks.dispatch",
    "apothem.conformity.gate",
)

#: Installed script names Apothem's handlers run, under the harness root.
_APOTHEM_HOOK_SCRIPTS = r"(?:hooks/dispatch\.py|conformity/gate\.py)"


def _handler_text(handler: dict[object, object]) -> str:
    """Return the command-bearing text of one hook handler."""
    parts = [str(handler.get("command", "")), str(handler.get("commandWindows", ""))]
    args = handler.get("args", [])
    if isinstance(args, list):
        parts.extend(str(arg) for arg in args)
    return " ".join(parts)


def is_apothem_hook(handler: object, *, harness_root: Path | None = None) -> bool:
    """Return True when a hook handler belongs to Apothem's managed surface.

    With *harness_root*, ownership is exact: the handler must run one of
    Apothem's installed scripts (``.../hooks/dispatch.py`` or
    ``.../conformity/gate.py``) at a path under that harness root (current or
    earlier layout, resolved or as the unrendered ``${HARNESS_ROOT}`` token),
    or invoke Apothem's hook modules by name. An operator's own
    ``/elsewhere/hooks/dispatch.py`` is not Apothem's and survives install and
    uninstall. Without a root, the legacy substring check applies.
    """
    if not isinstance(handler, dict):
        return False
    text = _handler_text(handler)
    if harness_root is None:
        return any(marker in text for marker in _APOTHEM_HOOK_MARKERS)
    if any(module in text for module in _APOTHEM_HOOK_MODULES):
        return True
    roots = {
        harness_root.resolve().as_posix(),
        harness_root.as_posix(),
        "${HARNESS_ROOT}",
    }
    alternatives = "|".join(re.escape(root.rstrip("/")) for root in sorted(roots))
    pattern = rf"(?:{alternatives})/(?:[^\s\"']*/)?{_APOTHEM_HOOK_SCRIPTS}"
    return re.search(pattern, text) is not None


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
    *,
    harness_root: Path | None = None,
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
            handler
            for handler in handlers
            if not is_apothem_hook(handler, harness_root=harness_root)
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
    *,
    harness_root: Path | None = None,
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
                retained.append(
                    _merge_hook_entry(
                        existing_entries, incoming_entry, harness_root=harness_root
                    )
                )
            else:
                retained.append(incoming_entry)
        merged[event_name] = retained
    return merged


def _merge_json_settings(
    existing: object, incoming: object, *, harness_root: Path | None = None
) -> object:
    """Merge JSON settings while preserving operator-authored keys."""
    return _merge_json_values(
        existing, incoming, prefer_existing=True, harness_root=harness_root
    )


def _overlay_json_settings(
    existing: object, incoming: object, *, harness_root: Path | None = None
) -> object:
    """Merge JSON settings while incoming managed values take precedence."""
    return _merge_json_values(
        existing, incoming, prefer_existing=False, harness_root=harness_root
    )


def _merge_json_values(
    existing: object,
    incoming: object,
    *,
    prefer_existing: bool,
    harness_root: Path | None = None,
) -> object:
    """Merge JSON objects, preserving keys absent from the incoming object.

    *harness_root* scopes hook-handler ownership (see :func:`is_apothem_hook`).
    """
    if isinstance(existing, dict) and isinstance(incoming, dict):
        merged: dict[str, object] = dict(existing)
        for key, value in incoming.items():
            current = existing.get(key)
            if key == "hooks" and isinstance(current, dict) and isinstance(value, dict):
                merged[key] = _merge_hooks(current, value, harness_root=harness_root)
            elif (
                prefer_existing
                and isinstance(current, list)
                and isinstance(value, list)
            ):
                merged[key] = _dedupe_json_list(current, value)
            elif isinstance(current, dict) and isinstance(value, dict):
                merged[key] = _merge_json_values(
                    current,
                    value,
                    prefer_existing=prefer_existing,
                    harness_root=harness_root,
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


#: Structured error code a refused operator-config write carries in its
#: result ``detail`` (and the CLI surfaces as the error envelope's ``code``).
CONFIG_UNPARSEABLE_CODE: Final[str] = "config.unparseable"


#: A YAML comment starts at the beginning of a line or after whitespace.
_YAML_COMMENT_RE: Final[re.Pattern[str]] = re.compile(r"(?:^|\s)#", re.MULTILINE)


class _LossyRewriteError(ValueError):
    """The merge would have to rewrite an operator config it cannot round-trip.

    Raised when the operator's file does not parse, or when it parses only as
    JSONC / JSON5 / commented YAML and the merge must change a value: a
    strict re-serialization would drop the operator's comments or syntax, so
    the write is refused and the file is left untouched.
    """

    def __init__(self, reason: str, fix: str) -> None:
        """Record the operator-facing *reason* and *fix*."""
        super().__init__(reason)
        self.reason = reason
        self.fix = fix


def _changed_top_keys(existing: object, merged: object) -> list[str]:
    """Return the top-level keys whose value the merge adds or changes."""
    if not isinstance(merged, dict):
        return []
    current = existing if isinstance(existing, dict) else {}
    return [key for key, value in merged.items() if current.get(key) != value]


def _lossy_rewrite(
    target: Path, kind: str, plain_format: str, existing: object, merged: object
) -> _LossyRewriteError:
    """Build the refusal for a rewrite that would lose the operator's *kind*."""
    keys = ", ".join(_changed_top_keys(existing, merged)) or "(none)"
    return _LossyRewriteError(
        f"{target} carries {kind}, which rewriting it would lose",
        f"Convert {target.name} to plain {plain_format} without comments, or add "
        f"these keys yourself and re-run: {keys}",
    )


def _yaml_has_operator_comments(existing_text: str, managed_header: str) -> bool:
    """Return True when *existing_text* carries comments Apothem did not write.

    Apothem's own leading header (re-prepended on every merge) is not an
    operator comment, so it is ignored when the file starts with it.
    """
    body = existing_text
    if managed_header and body.startswith(managed_header):
        body = body[len(managed_header) :]
    return _YAML_COMMENT_RE.search(body) is not None


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


def _refused_result(
    operation: str,
    target: Path,
    refusal: _LossyRewriteError,
    detail: dict[str, str],
    *,
    source: Path | None = None,
) -> MaterializationResult:
    """Return the ``error`` result for a refused operator-config rewrite."""
    return _with_detail(
        _result("error", operation, target, refusal.reason, source=source),
        {**detail, "code": CONFIG_UNPARSEABLE_CODE, "fix": refusal.fix},
    )


def _read_existing(target: Path) -> str | None:
    """Return *target*'s text, ``None`` when absent.

    Raises:
        _LossyRewriteError: When the file exists but cannot be read as UTF-8 text,
            so the merge refuses it rather than treating it as empty.
    """
    if not target.exists():
        return None
    try:
        return target.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise _LossyRewriteError(
            f"{target} cannot be read: {exc}",
            f"Check that {target.name} is a readable UTF-8 file, then re-run.",
        ) from exc
