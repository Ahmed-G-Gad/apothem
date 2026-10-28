# SPDX-License-Identifier: MIT

"""The ``native_hooks`` mode: merge and removal on the two hook-file shapes.

Kiro's hook file is a list of hooks (``action.command``) and Copilot's is a map
from event to hooks (``bash`` / ``powershell``). Neither nests handlers under a
matcher, which is the one shape the Claude-shaped merge understands, so the mode
carries its own ownership test: a hook is Apothem's when its command runs the
dispatcher under the project. These tests pin that test, the merge that keeps an
operator's hooks, and the removal that works from the file's text alone.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from apothem.harnesses._shared.install_driver_hookfile import (
    HOOK_FILE_MODE,
    _UnmergeableError,
    merge_registration,
    strip_registration,
)

_PROJECT = Path("/work/project")
_DISPATCHER = "/work/project/.apothem/support/kiro/hooks/dispatch.py"


def _ours(event: str = "SessionStart") -> dict[str, object]:
    return {
        "name": "apothem-session-start",
        "trigger": event,
        "action": {
            "type": "command",
            "command": f'"/usr/bin/python3" "{_DISPATCHER}" --contract kiro {event}',
        },
        "timeout": 30,
    }


def _theirs(name: str = "lint") -> dict[str, object]:
    return {
        "name": name,
        "trigger": "PostToolUse",
        "action": {"type": "command", "command": "npm run lint"},
    }


def _copilot_ours(event: str = "sessionStart") -> dict[str, object]:
    command = f'"/usr/bin/python3" "{_DISPATCHER}" --contract copilot {event}'
    return {
        "type": "command",
        "bash": command,
        "powershell": f"& {command}",
        "timeoutSec": 30,
    }


def _text(doc: object) -> str:
    return json.dumps(doc, indent=2) + "\n"


def test_the_mode_name_is_registered_with_a_label() -> None:
    from apothem.harnesses._shared.install_driver_types import (
        _INSTALL_ENTRY_MODES,
        OPERATION_LABELS,
    )

    assert HOOK_FILE_MODE in _INSTALL_ENTRY_MODES
    assert OPERATION_LABELS[HOOK_FILE_MODE]


# --- ownership -----------------------------------------------------------------


@pytest.mark.parametrize(
    "hook",
    [
        _ours(),
        # A Copilot hook is Apothem's by either of its two command fields.
        {"type": "command", "bash": f'"py" "{_DISPATCHER}" --contract copilot x'},
        {"type": "command", "powershell": f'& "py" "{_DISPATCHER}" x'},
        {"type": "command", "command": f'"py" "{_DISPATCHER}" x'},
    ],
)
def test_a_hook_that_runs_the_project_dispatcher_is_apothems(
    hook: dict[str, object],
) -> None:
    doc = (
        {"version": "v1", "hooks": [hook]}
        if "action" in hook
        else {"version": 1, "hooks": {"sessionStart": [hook]}}
    )
    assert strip_registration(_text(doc), root=_PROJECT) is None


@pytest.mark.parametrize(
    "command",
    [
        '"/usr/bin/python3" "/opt/team/hooks/dispatch.py" SessionStart',
        "npm run lint",
        '"py" "/work/other-project/.apothem/support/kiro/hooks/dispatch.py" x',
    ],
)
def test_a_hook_that_runs_something_else_is_not_apothems(command: str) -> None:
    doc = {
        "version": "v1",
        "hooks": [
            {"name": "x", "trigger": "SessionStart", "action": {"command": command}}
        ],
    }
    text = _text(doc)
    assert strip_registration(text, root=_PROJECT) == text


def test_ownership_needs_no_interpreter_token() -> None:
    # An uninstall renders the template without the interpreter, so the test must
    # hold for any interpreter spelling.
    for python in ("py", "C:/Python314/python.exe", "/usr/bin/python3"):
        hook = _ours()
        hook["action"] = {"type": "command", "command": f'"{python}" "{_DISPATCHER}" x'}
        assert (
            strip_registration(_text({"version": "v1", "hooks": [hook]}), root=_PROJECT)
            is None
        )


# --- merge ---------------------------------------------------------------------


def test_an_absent_or_blank_file_takes_the_template_verbatim() -> None:
    rendered = _text({"version": "v1", "hooks": [_ours()]})
    assert merge_registration(None, rendered, root=_PROJECT) == rendered
    assert merge_registration("  \n", rendered, root=_PROJECT) == rendered


def test_a_file_of_only_apothems_hooks_is_replaced_by_the_template() -> None:
    rendered = _text({"version": "v1", "hooks": [_ours()]})
    stale = _text({"version": "v1", "hooks": [{**_ours(), "timeout": 5}]})
    assert merge_registration(stale, rendered, root=_PROJECT) == rendered
    assert merge_registration(rendered, rendered, root=_PROJECT) == rendered


def test_a_list_file_keeps_the_operators_hooks_ahead_of_apothems() -> None:
    rendered = _text({"version": "v1", "hooks": [_ours()]})
    existing = _text({"version": "v1", "hooks": [_theirs("a"), _ours(), _theirs("b")]})

    merged = json.loads(merge_registration(existing, rendered, root=_PROJECT))

    assert [h["name"] for h in merged["hooks"]] == ["a", "b", "apothem-session-start"]
    assert merged["version"] == "v1"


def test_a_map_file_keeps_the_operators_hooks_per_event() -> None:
    rendered = _text(
        {
            "version": 1,
            "hooks": {
                "sessionStart": [_copilot_ours()],
                "postToolUse": [_copilot_ours("postToolUse")],
            },
        }
    )
    mine = {"type": "command", "bash": "echo mine"}
    existing = _text(
        {
            "version": 1,
            "disableAllHooks": False,
            "hooks": {
                "postToolUse": [mine, _copilot_ours("postToolUse")],
                "preToolUse": [mine],
            },
        }
    )

    merged = json.loads(merge_registration(existing, rendered, root=_PROJECT))

    assert merged["disableAllHooks"] is False
    assert merged["hooks"]["preToolUse"] == [mine]
    assert merged["hooks"]["postToolUse"][0] == mine
    assert len(merged["hooks"]["postToolUse"]) == 2
    assert merged["hooks"]["sessionStart"] == [_copilot_ours()]
    # No Claude-style nesting is ever added to a flat entry.
    assert all("hooks" not in h for hs in merged["hooks"].values() for h in hs)


def test_a_second_merge_changes_nothing() -> None:
    rendered = _text({"version": "v1", "hooks": [_ours()]})
    once = merge_registration(
        _text({"version": "v1", "hooks": [_theirs()]}), rendered, root=_PROJECT
    )
    assert merge_registration(once, rendered, root=_PROJECT) == once


@pytest.mark.parametrize("existing", ["{ not json", "[]", '{"hooks": "x"}', '{"a": 1}'])
def test_a_file_that_is_not_a_hook_registration_is_replaced(existing: str) -> None:
    rendered = _text({"version": "v1", "hooks": [_ours()]})
    assert merge_registration(existing, rendered, root=_PROJECT) == rendered


def test_a_file_in_the_other_vendor_shape_is_replaced_not_mixed() -> None:
    rendered = _text({"version": "v1", "hooks": [_ours()]})
    other = _text({"version": 1, "hooks": {"stop": [{"type": "command", "bash": "x"}]}})
    assert merge_registration(other, rendered, root=_PROJECT) == rendered


def test_an_operator_top_level_key_is_kept_even_with_no_operator_hooks() -> None:
    rendered = _text({"version": 1, "hooks": {"sessionStart": [_copilot_ours()]}})
    existing = _text({"version": 1, "disableAllHooks": True, "hooks": {}})
    merged = json.loads(merge_registration(existing, rendered, root=_PROJECT))
    assert merged["disableAllHooks"] is True
    assert merged["hooks"]["sessionStart"] == [_copilot_ours()]


# --- removal -------------------------------------------------------------------


def test_removal_deletes_a_file_of_only_apothems_hooks() -> None:
    assert (
        strip_registration(_text({"version": "v1", "hooks": [_ours()]}), root=_PROJECT)
        is None
    )
    mapped = {"version": 1, "hooks": {"sessionStart": [_copilot_ours()]}}
    assert strip_registration(_text(mapped), root=_PROJECT) is None


def test_removal_keeps_the_operators_hooks_and_the_version() -> None:
    existing = _text({"version": "v1", "hooks": [_theirs(), _ours()]})
    remainder = strip_registration(existing, root=_PROJECT)
    assert remainder is not None
    assert json.loads(remainder) == {"version": "v1", "hooks": [_theirs()]}


def test_removal_drops_an_event_it_emptied_and_keeps_the_rest() -> None:
    mine = {"type": "command", "bash": "echo mine"}
    existing = _text(
        {
            "version": 1,
            "hooks": {
                "sessionStart": [_copilot_ours()],
                "postToolUse": [mine, _copilot_ours("postToolUse")],
            },
        }
    )
    remainder = strip_registration(existing, root=_PROJECT)
    assert remainder is not None
    assert json.loads(remainder) == {"version": 1, "hooks": {"postToolUse": [mine]}}


def test_removal_leaves_an_operators_empty_event_list_alone() -> None:
    text = _text({"version": 1, "hooks": {"stop": []}})
    assert strip_registration(text, root=_PROJECT) == text


def test_removal_deletes_a_file_left_with_only_empty_event_lists() -> None:
    existing = _text(
        {"version": 1, "hooks": {"stop": [], "sessionStart": [_copilot_ours()]}}
    )
    assert strip_registration(existing, root=_PROJECT) is None


def test_removal_keeps_a_file_with_operator_top_level_keys() -> None:
    existing = _text(
        {
            "version": 1,
            "disableAllHooks": True,
            "hooks": {"sessionStart": [_copilot_ours()]},
        }
    )
    remainder = strip_registration(existing, root=_PROJECT)
    assert remainder is not None
    assert json.loads(remainder) == {"version": 1, "disableAllHooks": True, "hooks": {}}


@pytest.mark.parametrize("text", ["{ not json", "// c\n{}", "[]", '{"version": "v1"}'])
def test_removal_leaves_what_it_cannot_read_exactly_as_it_is(text: str) -> None:
    assert strip_registration(text, root=_PROJECT) == text


def test_removal_is_a_no_op_when_nothing_of_apothems_is_there() -> None:
    text = _text({"version": "v1", "hooks": [_theirs()]})
    assert strip_registration(text, root=_PROJECT) == text


# --- an operator-owned file (Cursor's .cursor/hooks.json) -----------------------

_CURSOR_DISPATCHER = "/work/project/.apothem/support/cursor/hooks/dispatch.py"


def _cursor_ours() -> dict[str, object]:
    command = (
        f'"/usr/bin/python3" "{_CURSOR_DISPATCHER}" --contract cursor sessionStart'
    )
    return {"type": "command", "command": command, "timeout": 30}


def _cursor_rendered() -> str:
    return _text({"version": 1, "hooks": {"sessionStart": [_cursor_ours()]}})


def _merge_owned(existing: str | None) -> str:
    return merge_registration(
        existing, _cursor_rendered(), root=_PROJECT, operator_owned=True
    )


def test_an_operator_owned_file_keeps_every_entry_and_key_the_operator_wrote() -> None:
    mine = {"command": "./audit.sh", "matcher": "Shell", "failClosed": True}
    existing = _text(
        {
            "version": 1,
            "x-team": {"owner": "platform"},
            "hooks": {"stop": [mine], "sessionStart": [mine, _cursor_ours()]},
        }
    )

    merged = json.loads(_merge_owned(existing))

    assert merged["x-team"] == {"owner": "platform"}
    assert merged["hooks"]["stop"] == [mine]
    assert merged["hooks"]["sessionStart"] == [mine, _cursor_ours()]
    # A flat entry is never given a Claude-style handler list.
    assert all("hooks" not in h for hs in merged["hooks"].values() for h in hs)


def test_an_operator_owned_merge_is_idempotent() -> None:
    once = _merge_owned(_text({"version": 1, "hooks": {"stop": [{"command": "x"}]}}))
    assert _merge_owned(once) == once


def test_an_operator_owned_file_with_no_hooks_key_gets_one() -> None:
    merged = json.loads(_merge_owned(_text({"version": 1, "x-team": True})))
    assert merged["x-team"] is True
    assert merged["hooks"] == {"sessionStart": [_cursor_ours()]}


def test_an_operator_owned_file_of_only_apothems_hooks_takes_the_template() -> None:
    assert _merge_owned(None) == _cursor_rendered()
    assert _merge_owned("") == _cursor_rendered()
    assert _merge_owned(_cursor_rendered()) == _cursor_rendered()
    stale = _text(
        {"version": 1, "hooks": {"sessionStart": [{**_cursor_ours(), "timeout": 5}]}}
    )
    assert _merge_owned(stale) == _cursor_rendered()


@pytest.mark.parametrize(
    "existing",
    [
        '{\n  // team notes\n  "version": 1, "hooks": {}\n}\n',
        '{"version": 1, "hooks": {},}',
        "[]",
        '"hooks"',
        '{"version": 1, "hooks": "x"}',
        # The other vendor's shape: a list of hooks where a map belongs.
        '{"version": 1, "hooks": [{"command": "x"}]}',
    ],
)
def test_an_operator_owned_file_apothem_would_have_to_damage_is_refused(
    existing: str,
) -> None:
    with pytest.raises(_UnmergeableError):
        _merge_owned(existing)
    # The same text in an Apothem-owned file is replaced, after the backup.
    assert (
        merge_registration(existing, _cursor_rendered(), root=_PROJECT)
        == _cursor_rendered()
    )
