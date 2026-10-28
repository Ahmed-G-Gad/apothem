# SPDX-License-Identifier: MIT

"""The ``native_hooks`` mode: merge and removal on the two hook-file shapes.

Kiro's hook file is a list of hooks (``action.command``) and Copilot's is a map
from event to hooks (``bash`` / ``powershell``). Neither nests handlers under a
matcher, which is the one shape the Claude-shaped merge understands, so the mode
carries its own ownership test: a hook is Apothem's when its command runs the
native dispatcher (``.apothem/support/[<harness>/]hooks/dispatch.py``) with a
``--contract`` argument, whichever project path it was written under. These tests
pin that test, the merge that keeps an operator's hooks, and the removal that works
from the file's text alone.
"""

from __future__ import annotations

import json

import pytest

from apothem.harnesses._shared.install_driver_hookfile import (
    HOOK_FILE_MODE,
    _UnmergeableError,
    merge_registration,
    strip_registration,
)

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
        {"type": "command", "powershell": f'& "py" "{_DISPATCHER}" --contract x y'},
        {"type": "command", "command": f'"py" "{_DISPATCHER}" --contract=x y'},
        # The root it was written under is not consulted: another checkout's entry,
        # a renamed or moved project, and a Windows spelling are all Apothem's.
        {
            "type": "command",
            "command": '"py" "/other/proj/.apothem/support/kiro/hooks/dispatch.py"'
            " --contract kiro x",
        },
        {
            "type": "command",
            "command": '"C:\\py\\python.exe" '
            '"C:\\Users\\me\\proj\\.apothem\\support\\hooks\\dispatch.py" '
            "--contract codebuddy x",
        },
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
    assert strip_registration(_text(doc)) is None


@pytest.mark.parametrize(
    "command",
    [
        '"/usr/bin/python3" "/opt/team/hooks/dispatch.py" SessionStart',
        "npm run lint",
        # An operator's own script that shares the dispatcher's file name, inside
        # the project, with and without a contract argument of its own.
        '"py" "/work/project/tools/hooks/dispatch.py" start',
        '"py" "/work/project/tools/hooks/dispatch.py" --contract mine start',
        '"py" "/work/project/scripts/conformity/gate.py" --check',
        # The module spellings an operator runs on purpose (a conformity gate on Stop).
        "python -m apothem.conformity.gate --all --strict .",
        "python -m apothem.hooks.dispatch SessionStart",
        # The support-tree path with no contract argument is not a registration
        # Apothem writes here.
        f'"py" "{_DISPATCHER}" x',
        # Nor a path that only ends in the same words.
        '"py" "/work/project/vendor.apothem/support/kiro/hooks/dispatch.pyc" '
        "--contract kiro x",
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
    assert strip_registration(text) == text


def test_ownership_needs_no_interpreter_token() -> None:
    # An uninstall renders the template without the interpreter, so the test must
    # hold for any interpreter spelling.
    for python in ("py", "C:/Python314/python.exe", "/usr/bin/python3"):
        hook = _ours()
        hook["action"] = {
            "type": "command",
            "command": f'"{python}" "{_DISPATCHER}" --contract kiro x',
        }
        assert strip_registration(_text({"version": "v1", "hooks": [hook]})) is None


# --- merge ---------------------------------------------------------------------


def test_an_absent_or_blank_file_takes_the_template_verbatim() -> None:
    rendered = _text({"version": "v1", "hooks": [_ours()]})
    assert merge_registration(None, rendered) == rendered
    assert merge_registration("  \n", rendered) == rendered


def test_a_file_of_only_apothems_hooks_is_replaced_by_the_template() -> None:
    rendered = _text({"version": "v1", "hooks": [_ours()]})
    stale = _text({"version": "v1", "hooks": [{**_ours(), "timeout": 5}]})
    assert merge_registration(stale, rendered) == rendered
    assert merge_registration(rendered, rendered) == rendered


def test_a_list_file_keeps_the_operators_hooks_ahead_of_apothems() -> None:
    rendered = _text({"version": "v1", "hooks": [_ours()]})
    existing = _text({"version": "v1", "hooks": [_theirs("a"), _ours(), _theirs("b")]})

    merged = json.loads(merge_registration(existing, rendered))

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

    merged = json.loads(merge_registration(existing, rendered))

    assert merged["disableAllHooks"] is False
    assert merged["hooks"]["preToolUse"] == [mine]
    assert merged["hooks"]["postToolUse"][0] == mine
    assert len(merged["hooks"]["postToolUse"]) == 2
    assert merged["hooks"]["sessionStart"] == [_copilot_ours()]
    # No Claude-style nesting is ever added to a flat entry.
    assert all("hooks" not in h for hs in merged["hooks"].values() for h in hs)


def test_a_second_merge_changes_nothing() -> None:
    rendered = _text({"version": "v1", "hooks": [_ours()]})
    once = merge_registration(_text({"version": "v1", "hooks": [_theirs()]}), rendered)
    assert merge_registration(once, rendered) == once


@pytest.mark.parametrize("existing", ["{ not json", "[]", '{"hooks": "x"}', '{"a": 1}'])
def test_a_file_that_is_not_a_hook_registration_is_replaced(existing: str) -> None:
    rendered = _text({"version": "v1", "hooks": [_ours()]})
    assert merge_registration(existing, rendered) == rendered


def test_a_file_in_the_other_vendor_shape_is_replaced_not_mixed() -> None:
    rendered = _text({"version": "v1", "hooks": [_ours()]})
    other = _text({"version": 1, "hooks": {"stop": [{"type": "command", "bash": "x"}]}})
    assert merge_registration(other, rendered) == rendered


def test_an_operator_top_level_key_is_kept_even_with_no_operator_hooks() -> None:
    rendered = _text({"version": 1, "hooks": {"sessionStart": [_copilot_ours()]}})
    existing = _text({"version": 1, "disableAllHooks": True, "hooks": {}})
    merged = json.loads(merge_registration(existing, rendered))
    assert merged["disableAllHooks"] is True
    assert merged["hooks"]["sessionStart"] == [_copilot_ours()]


# --- removal -------------------------------------------------------------------


def test_removal_deletes_a_file_of_only_apothems_hooks() -> None:
    assert strip_registration(_text({"version": "v1", "hooks": [_ours()]})) is None
    mapped = {"version": 1, "hooks": {"sessionStart": [_copilot_ours()]}}
    assert strip_registration(_text(mapped)) is None


def test_removal_keeps_the_operators_hooks_and_the_version() -> None:
    existing = _text({"version": "v1", "hooks": [_theirs(), _ours()]})
    remainder = strip_registration(existing)
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
    remainder = strip_registration(existing)
    assert remainder is not None
    assert json.loads(remainder) == {"version": 1, "hooks": {"postToolUse": [mine]}}


def test_removal_leaves_an_operators_empty_event_list_alone() -> None:
    text = _text({"version": 1, "hooks": {"stop": []}})
    assert strip_registration(text) == text


def test_removal_deletes_a_file_left_with_only_empty_event_lists() -> None:
    existing = _text(
        {"version": 1, "hooks": {"stop": [], "sessionStart": [_copilot_ours()]}}
    )
    assert strip_registration(existing) is None


def test_removal_keeps_a_file_with_operator_top_level_keys() -> None:
    existing = _text(
        {
            "version": 1,
            "disableAllHooks": True,
            "hooks": {"sessionStart": [_copilot_ours()]},
        }
    )
    remainder = strip_registration(existing)
    assert remainder is not None
    assert json.loads(remainder) == {"version": 1, "disableAllHooks": True, "hooks": {}}


@pytest.mark.parametrize("text", ["{ not json", "// c\n{}", "[]", '{"version": "v1"}'])
def test_removal_leaves_what_it_cannot_read_exactly_as_it_is(text: str) -> None:
    assert strip_registration(text) == text


def test_removal_is_a_no_op_when_nothing_of_apothems_is_there() -> None:
    text = _text({"version": "v1", "hooks": [_theirs()]})
    assert strip_registration(text) == text


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
    return merge_registration(existing, _cursor_rendered(), operator_owned=True)


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
    assert merge_registration(existing, _cursor_rendered()) == _cursor_rendered()


# --- identity: the project was renamed, moved or cloned again -------------------


def test_an_install_from_another_path_replaces_the_old_set_not_adds_to_it() -> None:
    moved = _ours()
    moved["action"] = {
        "type": "command",
        "command": '"py" "/home/mate/clone/.apothem/support/kiro/hooks/dispatch.py" '
        "--contract kiro SessionStart",
    }
    rendered = _text({"version": "v1", "hooks": [_ours()]})
    existing = _text({"version": "v1", "hooks": [_theirs(), moved]})

    merged = json.loads(merge_registration(existing, rendered))

    assert [h["name"] for h in merged["hooks"]] == ["lint", "apothem-session-start"]
    assert "/work/project/" in merged["hooks"][1]["action"]["command"]
    assert strip_registration(_text(merged)) is not None
    assert json.loads(strip_registration(_text(merged)) or "{}")["hooks"] == [_theirs()]


# --- Kiro's enabled flag --------------------------------------------------------


def test_an_operator_who_disabled_the_hook_keeps_it_disabled_on_update() -> None:
    rendered = _text({"version": "v1", "hooks": [_ours()]})
    existing = _text({"version": "v1", "hooks": [{**_ours(), "enabled": False}]})

    merged = json.loads(merge_registration(existing, rendered))

    assert merged["hooks"] == [{**_ours(), "enabled": False}]
    # Idempotent: a second update changes nothing.
    again = merge_registration(_text(merged), rendered)
    assert json.loads(again) == merged


def test_only_the_enabled_flag_is_carried_over_the_rest_is_refreshed() -> None:
    rendered = _text({"version": "v1", "hooks": [_ours()]})
    edited = {**_ours(), "enabled": True, "timeout": 5, "description": "mine"}

    merged = json.loads(
        merge_registration(_text({"version": "v1", "hooks": [edited]}), rendered)
    )

    assert merged["hooks"] == [{**_ours(), "enabled": True}]


def test_the_enabled_flag_of_an_operators_own_hook_is_left_alone() -> None:
    rendered = _text({"version": "v1", "hooks": [_ours()]})
    mine = {**_theirs(), "enabled": False}

    merged = json.loads(
        merge_registration(_text({"version": "v1", "hooks": [mine]}), rendered)
    )

    assert merged["hooks"] == [mine, _ours()]


def test_a_template_without_the_flag_and_a_file_without_it_stay_byte_identical() -> (
    None
):
    rendered = _text({"version": "v1", "hooks": [_ours()]})
    assert merge_registration(rendered, rendered) == rendered
