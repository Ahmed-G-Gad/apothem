# SPDX-License-Identifier: MIT

"""Own-file native hook registrations: the ``native_hooks`` install mode.

Some harnesses read hooks from a directory of small JSON files, one per
author, rather than from a settings file the operator shares with the tool.
Apothem writes one of those files, named ``apothem.json``, and the file is the
Apothem-owned place its hook entries live. The mode renders a template into
that file, and tells Apothem's entries from any entry the operator added to the
same file by what each entry's command runs: the native dispatcher,
``.apothem/support/[<harness>/]hooks/dispatch.py``, with a ``--contract <id>``
argument (:func:`is_apothem_contract_command`). The test reads the command text
and nothing else, so it holds whether or not the install ledger has a record,
whether or not the interpreter token in the template can be rendered again (an
uninstall renders without it), and whichever project path the entry was written
under: a project that was renamed, moved or cloned again keeps one set of
entries, and an operator's own ``hooks/dispatch.py`` or ``python -m
apothem.conformity.gate`` hook is never taken for Apothem's.

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
holds operator entries, they are kept ahead of Apothem's. The one thing an
operator sets on an Apothem entry, Kiro's ``enabled`` flag, which Kiro's own hook
management writes, is carried over to the entry the install writes; every other
field of an Apothem entry is Apothem's and is refreshed. A previous file that is
replaced is copied to the Apothem backup root first. An uninstall removes
Apothem's entries, deletes the file when nothing else is left in it, and leaves
a file it cannot read exactly as it is.

The ownership class of the manifest entry sets how a file Apothem cannot merge
into is treated. An ``apothem-owned`` entry (Kiro's and Copilot's ``apothem.json``)
is a file only Apothem writes, so a file that is not a hook registration is
replaced, after the backup. An ``operator-owned`` entry (Cursor's
``.cursor/hooks.json``, the one project hook file, which a team edits and commits)
is the operator's file: a registration with no ``hooks`` key gets one, and a file
Apothem would have to damage to merge into (one that does not parse, such as JSON
with comments, that is not a JSON object, or whose ``hooks`` is the other shape)
is refused with ``config.unparseable`` and left exactly as it is, the way the
key-merge of a settings file refuses.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Final, NamedTuple

from apothem.lib.propagation import InstallEntry, resolve_target

from .install_driver_backup import _guarded_unlink, backup_existing, write_bytes_safely
from .install_driver_jsonmerge import (
    _LossyRewriteError,
    _refused_result,
    is_apothem_contract_command,
    mentions_native_dispatcher,
)
from .install_driver_merge import (
    _unified_diff,
    content_token_values,
    render_content_tokens,
)
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


def _is_ours(hook: object) -> bool:
    """Return True when *hook* runs Apothem's native dispatcher, whatever the root."""
    return is_apothem_contract_command(_command_text(hook))


def _without_ours(doc: object) -> tuple[dict[str, object], int] | None:
    """Return *doc* without Apothem's hooks, plus how many hooks remain.

    ``None`` when *doc* is not a hook registration of either shape.
    """
    if not isinstance(doc, dict):
        return None
    hooks = doc.get("hooks")
    if isinstance(hooks, list):
        kept = [hook for hook in hooks if not _is_ours(hook)]
        return {**doc, "hooks": kept}, len(kept)
    if isinstance(hooks, dict):
        events: dict[str, object] = {}
        remaining = 0
        for event, listed in hooks.items():
            if not isinstance(listed, list):
                events[event] = listed
                remaining += 1
                continue
            survivors = [hook for hook in listed if not _is_ours(hook)]
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


def _restore_enabled(
    before: object, incoming: dict[str, object], rendered: str
) -> tuple[dict[str, object], str]:
    """Carry the operator's ``enabled`` flag from Apothem's old hooks to the new ones.

    Kiro documents ``hooks[].enabled`` ("Set false to skip the hook without
    deleting it", https://kiro.dev/docs/hooks/, retrieved 2026-10-28) and its own
    hook management writes it, so a hook the operator switched off must stay off
    when an update rewrites the entry. Hooks are matched by ``name`` (the list
    shape only; the event-map shape has no such flag). Every other field of an
    Apothem hook is Apothem's: a changed ``timeout`` is indistinguishable from an
    earlier release's, so it is refreshed, not kept. Returns the incoming
    registration and its text, both unchanged when no flag is carried.
    """
    old, new = (
        before.get("hooks") if isinstance(before, dict) else None,
        incoming.get("hooks"),
    )
    if not (isinstance(old, list) and isinstance(new, list)):
        return incoming, rendered
    flags = {
        hook["name"]: hook["enabled"]
        for hook in old
        if isinstance(hook, dict)
        and _is_ours(hook)
        and isinstance(hook.get("name"), str)
        and "enabled" in hook
    }
    carried = [
        {**hook, "enabled": flags[hook["name"]]}
        if isinstance(hook, dict) and hook.get("name") in flags
        else hook
        for hook in new
    ]
    if carried == new:
        return incoming, rendered
    restored = {**incoming, "hooks": carried}
    return restored, _dump(restored)


class _UnmergeableError(Exception):
    """An operator-owned hook file Apothem would have to damage to merge into."""

    def __init__(self, what: str) -> None:
        """Record *what* is wrong with the file, as the end of a sentence."""
        super().__init__(what)
        self.what = what


def _merge_operator_file(
    existing: str, rendered: str, incoming: dict[str, object]
) -> str:
    """Return an operator's hook file with Apothem's hooks added after theirs.

    Raises:
        _UnmergeableError: When the file does not parse, is not a JSON object, or
            holds ``hooks`` in a shape other than the template's.
    """
    try:
        parsed = json.loads(existing)
    except ValueError:
        raise _UnmergeableError(
            "does not parse as JSON (comments and trailing commas are not JSON)"
        ) from None
    if not isinstance(parsed, dict):
        raise _UnmergeableError("is not a JSON object")
    if "hooks" not in parsed:
        parsed = {**parsed, "hooks": type(incoming["hooks"])()}
    kept = _without_ours(parsed)
    if kept is None or type(kept[0].get("hooks")) is not type(incoming.get("hooks")):
        raise _UnmergeableError("holds hooks in a shape other than the one it should")
    doc, remaining = kept
    incoming, rendered = _restore_enabled(parsed, incoming, rendered)
    if remaining == 0 and set(doc) <= {"version", "hooks"}:
        return rendered
    return _dump(_combine(doc, incoming))


def merge_registration(
    existing: str | None,
    rendered: str,
    *,
    operator_owned: bool = False,
) -> str:
    """Return the file text an install writes over *existing*.

    *rendered* is the template with its tokens resolved. It is returned as is
    unless *existing* holds hooks the operator added, in which case those stay
    ahead of Apothem's. With *operator_owned*, a file that cannot be merged into
    without damage is refused instead of replaced (see the module docstring).

    Raises:
        _UnmergeableError: Only with *operator_owned*, as described above.
    """
    if existing is None or not existing.strip():
        return rendered
    if operator_owned:
        incoming = json.loads(rendered)
        if isinstance(incoming, dict) and "hooks" in incoming:
            return _merge_operator_file(existing, rendered, incoming)
        return rendered
    try:
        parsed = json.loads(existing)
        incoming = json.loads(rendered)
    except ValueError:
        return rendered
    kept = _without_ours(parsed)
    if kept is None or not isinstance(incoming, dict):
        return rendered
    doc, remaining = kept
    incoming, rendered = _restore_enabled(parsed, incoming, rendered)
    if remaining == 0 and set(doc) <= {"version", "hooks"}:
        return rendered
    if type(doc.get("hooks")) is not type(incoming.get("hooks")):
        # The operator's file is the other vendor shape; nothing of it fits.
        return rendered
    return _dump(_combine(doc, incoming))


def strip_registration(existing: str) -> str | None:
    """Return *existing* without Apothem's hooks; ``None`` means delete the file.

    Text that is not a readable hook registration comes back unchanged, so an
    uninstall never destroys what it cannot reason about. A file keeps its other
    top-level keys; it is deleted only when it held nothing but Apothem's hooks.
    """
    try:
        before = json.loads(existing)
    except ValueError:
        return existing
    stripped = _without_ours(before)
    if stripped is None:
        return existing
    doc, remaining = stripped
    if doc == before:
        return existing
    if remaining == 0 and set(doc) <= {"version", "hooks"}:
        return None
    return _dump(doc)


def _unreadable_with_dispatcher(text: str) -> bool:
    """Return True when *text* names Apothem's dispatcher but is no readable registration."""
    if not mentions_native_dispatcher(text):
        return False
    try:
        return _without_ours(json.loads(text)) is None
    except ValueError:
        return True


def _read(target: Path) -> str | None:
    try:
        return target.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _is_operator_owned(entry: InstallEntry) -> bool:
    return entry.ownership_class == "operator-owned"


def _merged_text(
    entry: InstallEntry, target: Path, rendered: str
) -> tuple[str, str | None]:
    """Return the text an install writes to *target* and the text it replaces.

    Raises:
        _LossyRewriteError: For an ``operator-owned`` entry whose file cannot be
            merged into without damage (see the module docstring).
    """
    before = _read(target)
    operator_owned = _is_operator_owned(entry)
    if operator_owned and before is None and target.exists():
        raise _LossyRewriteError(
            f"{target} cannot be read as UTF-8 text",
            f"Check that {target.name} is a readable UTF-8 file, then re-run.",
        )
    try:
        merged = merge_registration(before, rendered, operator_owned=operator_owned)
    except _UnmergeableError as refused:
        raise _LossyRewriteError(
            f"{target} {refused.what}, so Apothem cannot add its hooks without "
            "rewriting it",
            f'Make {target.name} plain JSON with a "hooks" object, or add '
            "Apothem's hook entries to it yourself, then re-run.",
        ) from None
    return merged, before


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
    detail = {"ownership_class": entry.ownership_class}
    try:
        merged, _before = _merged_text(entry, target, text)
    except _LossyRewriteError as refusal:
        return [
            _refused_result(
                entry.mode, target, refusal, detail, source=resolve_source(entry.source)
            )
        ]
    result = write_bytes_safely(
        target,
        merged.encode("utf-8"),
        install_root=root,
        harness_name=harness_name,
        operation=entry.mode,
        source=resolve_source(entry.source),
        allowed_root=_allowed_write_root(harness_root, project_root),
    )
    return [_with_detail(result, detail)]


class HookPreview(NamedTuple):
    """What :func:`apply_native_hooks` would do: the outcome, its diff, any refusal."""

    outcome: MaterializationOutcome
    diff: str
    refusal: _LossyRewriteError | None = None


def preview_native_hooks(
    entry: InstallEntry,
    *,
    harness_root: Path | None,
    project_root: Path | None,
) -> HookPreview:
    """Return the outcome and unified diff :func:`apply_native_hooks` would produce."""
    target = resolve_target(
        entry.target, harness_root=harness_root, project_root=project_root
    )
    text = _rendered(entry, harness_root=harness_root, project_root=project_root)
    if text is None:
        return HookPreview("skipped", "")
    try:
        after, before = _merged_text(entry, target, text)
    except _LossyRewriteError as refusal:
        return HookPreview("error", "", refusal)
    if before is None:
        return HookPreview("created", _unified_diff("", after, target))
    if before == after:
        return HookPreview("unchanged", "")
    return HookPreview("updated", _unified_diff(before, after, target))


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
    remainder = strip_registration(existing)
    if remainder == existing:
        if _unreadable_with_dispatcher(existing):
            return _result(
                "skipped",
                "surgical_uninstall",
                target,
                f"{target} is not a hook registration Apothem can read (it may "
                "carry comments or trailing commas) and it still names Apothem's "
                "dispatcher; remove the entry that runs "
                ".apothem/support/<harness>/hooks/dispatch.py from it by hand",
            )
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


def _registers_hooks(entry: InstallEntry, *, project_scope: bool) -> bool:
    """Return True when *entry*'s template is a hook registration Apothem writes.

    A ``native_hooks`` entry always is. A ``write_text`` entry is when the install
    is project-scope and its template is a JSON object with a ``hooks`` key (the
    CodeBuddy ``settings.local.json`` and the Devin ``config.local.json``); the
    same template under a user-scope root (Claude Code's ``settings.json``) is
    not this module's to judge.
    """
    if entry.mode == HOOK_FILE_MODE:
        return True
    if entry.mode != "write_text" or not project_scope:
        return False
    try:
        template = json.loads(resolve_source(entry.source).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(template, dict) and "hooks" in template


def _holds_apothem_hook(node: object) -> bool:
    """Return True when any hook anywhere in *node* runs Apothem's native dispatcher."""
    if isinstance(node, dict):
        return _is_ours(node) or any(_holds_apothem_hook(v) for v in node.values())
    if isinstance(node, list):
        return any(_holds_apothem_hook(item) for item in node)
    return False


def registration_present(
    entry: InstallEntry, target: Path, *, project_scope: bool
) -> bool:
    """Return False when *entry* should register Apothem's hooks and *target* holds none.

    ``verify`` uses it, so an install whose hook entries were reverted, deleted by
    hand or lost in a fresh clone of an operator-owned file no longer reads as
    installed. An entry that registers no hooks, or a file that does not parse
    (reported on its own), passes.
    """
    if not _registers_hooks(entry, project_scope=project_scope):
        return True
    from apothem.lib import lenient_json

    text = _read(target)
    if text is None:
        return True
    try:
        parsed = lenient_json.loads(text)
    except lenient_json.LenientJSONError:
        return True
    return _holds_apothem_hook(parsed)


#: Characters that change what a shell runs inside a double-quoted hook command
#: (``$`` expands, a backtick substitutes, ``"`` and ``\`` end or escape the
#: quoting) and that also break the JSON string the path is rendered into.
_UNSAFE_IN_COMMAND: Final[frozenset[str]] = frozenset('"\\$`')


def unsafe_command_path(
    entry: InstallEntry,
    *,
    harness_root: Path | None,
    project_root: Path | None,
) -> MaterializationResult | None:
    """Return an error when a path rendered into a hook command cannot be quoted.

    A hook registration puts the project path and the interpreter path inside a
    double-quoted command that ``sh``, Git Bash and PowerShell each read. One
    escape rule cannot serve all of them, so a path holding ``$``, a backtick, a
    double quote, a backslash or a control character is refused before anything
    is written, naming the path, instead of registering a command that runs the
    wrong file and exits 2. A space or an apostrophe is fine inside the quotes.
    """
    if not _registers_hooks(entry, project_scope=harness_root is None):
        return None
    src = resolve_source(entry.source)
    try:
        template = src.read_text(encoding="utf-8")
    except OSError:
        return None
    values = content_token_values(harness_root, project_root)
    for name in sorted(values):
        value = values[name]
        if f"${{{name}}}" not in template:
            continue
        bad = sorted(ch for ch in set(value) if ch in _UNSAFE_IN_COMMAND or ch < " ")
        if not bad:
            continue
        shown = " ".join(repr(ch) for ch in bad)
        target = resolve_target(
            entry.target, harness_root=harness_root, project_root=project_root
        )
        return _with_detail(
            _result(
                "error",
                entry.mode,
                target,
                f"{name} is {value!r}; the character {shown} in it would change "
                "what the shell runs inside the quoted hook command",
                source=src,
            ),
            {
                "fix": f"Use a path for {name} without those characters (for a "
                "project, move or rename it), then re-run. Nothing was written."
            },
        )
    return None
