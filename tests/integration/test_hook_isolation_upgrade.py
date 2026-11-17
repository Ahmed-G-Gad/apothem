# SPDX-License-Identifier: MIT

"""Hook entries move to the ``-E -s`` start on upgrade, and leave on uninstall.

Every hook command Apothem registers starts Python with ``-E -s`` (see
``tests/hooks/test_hook_interpreter_isolation.py`` for why). A file written by
the previous release holds the same entries without the two flags. Each adapter
tells its own entries apart by the script path the command runs (and, in a
project file, the ``--contract`` argument), never by the interpreter flags, so:

* an install or update over the previous release's file replaces those entries
  with the new ones, and the file holds one set, every entry with the flags;
* an uninstall removes Apothem's entries in either form, also from a file that
  holds both at once;
* an operator's own hooks in the same event survive every step, including one
  that runs a ``hooks/dispatch.py`` of their own with ``-E -s``.

Covered: the eight adapters that register hooks, in their three file shapes
(Claude-style matcher groups, Cursor's and GitHub Copilot's event maps, Kiro's
hook list). The user home is isolated per test by ``tests/conftest.py``.
"""

from __future__ import annotations

import copy
import json
import shlex
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from apothem.lib.harness_registry import get_harness_entry, load_adapter_class


@dataclass(frozen=True)
class Surface:
    """Where one adapter registers its hooks, and in which shape."""

    public_id: str
    file: str  # relative to the user home, or to the project for a project scope
    project_scope: bool
    shape: str  # claude | cursor | copilot | kiro


SURFACES = pytest.mark.parametrize(
    "surface",
    [
        Surface("claude-code", ".claude/settings.json", False, "claude"),
        Surface("codex", ".codex/hooks.json", False, "claude"),
        Surface("qwen-code", ".qwen/settings.json", False, "claude"),
        Surface("codebuddy", ".codebuddy/settings.local.json", True, "claude"),
        Surface("windsurf", ".devin/config.local.json", True, "claude"),
        Surface("cursor", ".cursor/hooks.json", True, "cursor"),
        Surface("kiro", ".kiro/hooks/apothem.json", True, "kiro"),
        Surface("github-copilot", ".github/hooks/apothem.json", True, "copilot"),
    ],
    ids=lambda surface: surface.public_id,
)

#: Handler keys whose string value is a command line.
_COMMAND_KEYS = ("command", "commandWindows", "bash", "powershell")
#: An operator's own dispatcher, outside every Apothem tree, started the same way.
_LOOKALIKE = 'python3 -E -s "/srv/team-tools/hooks/dispatch.py" SessionStart'


@dataclass
class Setup:
    """The adapter under test, how to call it, and the file it writes."""

    adapter: Any
    kwargs: dict[str, Path]
    target: Path


def _setup(surface: Surface, tmp_path: Path) -> Setup:
    adapter = load_adapter_class(get_harness_entry(surface.public_id))()
    if surface.project_scope:
        project = tmp_path / "project"
        project.mkdir()
        return Setup(adapter, {"project": project}, project / surface.file)
    return Setup(adapter, {}, Path.home() / surface.file)


def _handlers(node: object) -> Iterator[dict[str, Any]]:
    """Yield every mapping in *node* that carries a command line."""
    if isinstance(node, dict):
        if any(isinstance(node.get(key), str) for key in _COMMAND_KEYS):
            yield node
            return
        for value in node.values():
            yield from _handlers(value)
    elif isinstance(node, list):
        for item in node:
            yield from _handlers(item)


def _text(handler: dict[str, Any]) -> str:
    parts = [handler[key] for key in _COMMAND_KEYS if isinstance(handler.get(key), str)]
    args = handler.get("args")
    if isinstance(args, list):
        parts.extend(str(arg) for arg in args)
    return " ".join(parts)


def _ours(doc: object, operator: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return the handlers Apothem wrote: they run its dispatcher or its gate."""
    return [
        handler
        for handler in _handlers(doc)
        if handler not in operator
        and ("dispatch.py" in _text(handler) or "gate.py" in _text(handler))
    ]


def _signatures(handlers: list[dict[str, Any]]) -> list[str]:
    return sorted(json.dumps(handler, sort_keys=True) for handler in handlers)


def _shell_isolated(command: str) -> bool:
    tokens = shlex.split(command.removeprefix("& "))
    script = next(
        index
        for index, token in enumerate(tokens)
        if token.endswith(("dispatch.py", "gate.py"))
    )
    return tokens[script - 2 : script] == ["-E", "-s"]


def _isolated(handler: dict[str, Any]) -> bool:
    """Return True when every command line of *handler* starts Python with -E -s."""
    args = handler.get("args")
    if isinstance(args, list):
        return args[:2] == ["-E", "-s"]
    commands = [handler[k] for k in _COMMAND_KEYS if isinstance(handler.get(k), str)]
    return bool(commands) and all(_shell_isolated(command) for command in commands)


def _previous_release(doc: dict[str, Any]) -> dict[str, Any]:
    """Return *doc* as the previous release wrote it: the same entries, no flags."""
    old = copy.deepcopy(doc)
    for handler in _handlers(old):
        args = handler.get("args")
        if isinstance(args, list) and args[:2] == ["-E", "-s"]:
            del args[:2]
        for key in _COMMAND_KEYS:
            value = handler.get(key)
            if isinstance(value, str):
                handler[key] = value.replace(' -E -s "', ' "')
    return old


def _session_start_list(surface: Surface, doc: dict[str, Any]) -> list[Any]:
    """Return the list Apothem's session-start entry sits in, in *doc*."""
    hooks = doc["hooks"]
    if surface.shape == "claude":
        return hooks["SessionStart"][0]["hooks"]
    if surface.shape == "kiro":
        return hooks
    return hooks["sessionStart"]


def _operator_entries(surface: Surface) -> list[dict[str, Any]]:
    """Return two hooks an operator keeps beside Apothem's session-start entry."""
    if surface.shape == "kiro":
        return [
            {
                "name": f"team-start-{index}",
                "trigger": "SessionStart",
                "action": {"type": "command", "command": command},
            }
            for index, command in enumerate(("echo operator-hook", _LOOKALIKE))
        ]
    key = "bash" if surface.shape == "copilot" else "command"
    return [
        {"type": "command", key: "echo operator-hook"},
        {"type": "command", key: _LOOKALIKE},
    ]


def _with_operator_hooks(
    surface: Surface, doc: dict[str, Any]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Return *doc* with the operator's hooks added, and those hooks' handlers."""
    entries = _operator_entries(surface)
    _session_start_list(surface, doc).extend(entries)
    return doc, [handler for entry in entries for handler in _handlers(entry)]


def _load(target: Path) -> dict[str, Any]:
    doc = json.loads(target.read_text(encoding="utf-8"))
    assert isinstance(doc, dict), target
    return doc


def _save(target: Path, doc: object) -> None:
    target.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def _fresh_install(setup: Setup) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Install, and return the file and Apothem's entries, each with -E -s."""
    setup.adapter.install({}, **setup.kwargs)
    fresh = _load(setup.target)
    ours = _ours(fresh, [])
    assert ours, "the install registered hooks"
    bare = [handler for handler in ours if not _isolated(handler)]
    assert not bare, f"entries that do not start Python with -E -s: {bare}"
    return fresh, ours


def _assert_only_operator_hooks(target: Path, operator: list[dict[str, Any]]) -> None:
    remaining = _load(target) if target.exists() else {}
    assert _ours(remaining, operator) == [], "an Apothem entry was left behind"
    handlers = list(_handlers(remaining))
    for handler in operator:
        assert handler in handlers, f"the operator's hook went: {handler}"


@SURFACES
def test_entries_take_the_flags_on_update_and_leave_in_either_form(
    surface: Surface, tmp_path: Path
) -> None:
    setup = _setup(surface, tmp_path)
    fresh, ours = _fresh_install(setup)
    # The previous release's file, with an operator's hooks beside Apothem's.
    previous, operator = _with_operator_hooks(surface, _previous_release(fresh))
    assert len(_ours(previous, operator)) == len(ours)
    assert not any(_isolated(handler) for handler in _ours(previous, operator))
    _save(setup.target, previous)

    setup.adapter.update({}, **setup.kwargs)

    upgraded = _load(setup.target)
    assert _signatures(_ours(upgraded, operator)) == _signatures(ours)
    handlers = list(_handlers(upgraded))
    for handler in operator:
        assert handler in handlers, f"the update dropped the operator's hook {handler}"

    # Entries of both forms side by side, as a hand-merged file may hold them.
    both = copy.deepcopy(previous)
    _session_start_list(surface, both).extend(
        copy.deepcopy(_session_start_list(surface, fresh))
    )
    forms = {_isolated(handler) for handler in _ours(both, operator)}
    assert forms == {True, False}, "the file holds entries of both forms"
    _save(setup.target, both)

    setup.adapter.uninstall(**setup.kwargs)

    _assert_only_operator_hooks(setup.target, operator)
