# SPDX-License-Identifier: MIT

"""The hook files Kiro and Copilot install agree with their vendor contracts.

A registration is only as good as the contract row its command names. These tests
read the committed templates, split each command into its dispatcher call, and
hold every call to ``hooks/lib/vendor_contract.py``: the contract exists, the
event the vendor fires is one the contract knows, and the vendor hands that
event's output to the model. A guard registered where the vendor discards its
output would cost a process start per tool call and deliver nothing.
"""

from __future__ import annotations

import json
import shlex
import sys
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[2] / "src" / "apothem"
for _path in (_SRC / "hooks", _SRC / "hooks" / "lib"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import vendor_contract as vc  # noqa: E402

_KIRO = _SRC / "harnesses" / "kiro" / "templates" / "apothem-hooks.json"
_COPILOT = _SRC / "harnesses" / "github_copilot" / "templates" / "apothem-hooks.json"
_MESSAGES = _SRC / "hooks" / "messages"


def _calls(template: Path) -> list[tuple[str, str, list[str], str]]:
    """Return (vendor event, contract id, message names, powershell) per hook."""
    doc = json.loads(template.read_text(encoding="utf-8"))
    out: list[tuple[str, str, list[str], str]] = []
    if isinstance(doc["hooks"], list):
        pairs = [(h["trigger"], h["action"]["command"], "") for h in doc["hooks"]]
    else:
        pairs = [
            (event, hook["bash"], hook["powershell"])
            for event, hooks in doc["hooks"].items()
            for hook in hooks
        ]
    for trigger, command, powershell in pairs:
        tokens = shlex.split(command)
        script = next(i for i, t in enumerate(tokens) if t.endswith("dispatch.py"))
        rest = tokens[script + 1 :]
        assert rest[0] == "--contract", command
        assert rest[2] == trigger, "the dispatcher is given the event the file fires"
        out.append((trigger, rest[1], rest[3:], powershell))
    return out


@pytest.mark.parametrize(
    ("template", "contract_id", "events"),
    [
        (_KIRO, "kiro", ["SessionStart"]),
        (_COPILOT, "copilot", ["sessionStart", "postToolUse"]),
    ],
    ids=["kiro", "copilot"],
)
def test_every_registered_event_is_one_the_vendor_delivers(
    template: Path, contract_id: str, events: list[str]
) -> None:
    calls = _calls(template)
    assert [c[0] for c in calls] == events
    contract = vc.get_contract(contract_id)
    for trigger, call_contract, _messages, _powershell in calls:
        assert call_contract == contract_id
        assert contract.canonical_event(trigger) in contract.delivers, trigger


def test_kiro_registers_session_start_only() -> None:
    # Kiro adds a command's stdout to the context for SessionStart and
    # UserPromptSubmit; PreToolUse and PostToolUse stdout is ignored, so a hook
    # there would run and say nothing.
    assert vc.get_contract("kiro").delivers == {"SessionStart", "UserPromptSubmit"}
    assert [c[0] for c in _calls(_KIRO)] == ["SessionStart"]
    doc = json.loads(_KIRO.read_text(encoding="utf-8"))
    assert doc["version"] == "v1"
    for hook in doc["hooks"]:
        assert hook["trigger"] in {"SessionStart"}
        assert "matcher" not in hook


def test_copilot_registers_the_camel_case_events_whose_output_is_documented() -> None:
    contract = vc.get_contract("copilot")
    assert contract.shape_for("SessionStart") == vc.FLAT
    assert contract.shape_for("PostToolUse") == vc.FLAT
    doc = json.loads(_COPILOT.read_text(encoding="utf-8"))
    assert doc["version"] == 1
    # camelCase names carry the documented additionalContext output fields; the
    # PascalCase spelling's output handling is an open question (TODO(clarify)).
    assert sorted(doc["hooks"]) == ["postToolUse", "sessionStart"]
    assert contract.canonical_event("sessionStart") == "SessionStart"
    assert contract.canonical_event("postToolUse") == "PostToolUse"
    assert "preToolUse" not in doc["hooks"]


def test_copilot_powershell_command_is_the_bash_command_with_a_call_operator() -> None:
    doc = json.loads(_COPILOT.read_text(encoding="utf-8"))
    for hooks in doc["hooks"].values():
        for hook in hooks:
            assert hook["powershell"] == f"& {hook['bash']}"


def test_registered_messages_exist_in_the_hooks_tree() -> None:
    for template in (_KIRO, _COPILOT):
        for _trigger, _contract, messages, _powershell in _calls(template):
            for name in messages:
                assert (_MESSAGES / f"{name}.md").is_file(), name


def test_the_dispatcher_stays_advisory_for_both_vendors() -> None:
    # No registered command can carry a decision: the shapes these two contracts
    # emit hold context only.
    for contract_id in ("kiro", "copilot"):
        contract = vc.get_contract(contract_id)
        assert contract.output in {vc.PLAIN, vc.FLAT}
        for event in contract.delivers:
            assert contract.shape_for(event) in {vc.PLAIN, vc.FLAT}


# --- Cursor (a flat map) and Devin Local (Claude-shaped), the other two vendors ----

_CURSOR = _SRC / "harnesses" / "cursor" / "templates" / "apothem-hooks.json"
_DEVIN = _SRC / "harnesses" / "windsurf" / "templates" / "config-local.json"


def _dispatch_args(command: str) -> list[str]:
    """Return the words after ``dispatch.py`` in *command*: the contract call."""
    tokens = shlex.split(command)
    script = next(i for i, t in enumerate(tokens) if t.endswith("dispatch.py"))
    return tokens[script + 1 :]


def _devin_calls() -> list[tuple[str, str, list[str], dict[str, object]]]:
    """Return (event, contract id, message names, group) per Devin handler."""
    doc = json.loads(_DEVIN.read_text(encoding="utf-8"))
    out: list[tuple[str, str, list[str], dict[str, object]]] = []
    for event, groups in doc["hooks"].items():
        for group in groups:
            for handler in group["hooks"]:
                args = _dispatch_args(handler["command"])
                assert args[0] == "--contract", handler["command"]
                assert args[2] == event, "the dispatcher is given the event fired"
                out.append((event, args[1], args[3:], group))
    return out


def test_cursor_registers_session_start_with_the_snake_case_output() -> None:
    doc = json.loads(_CURSOR.read_text(encoding="utf-8"))
    assert doc["version"] == 1
    assert list(doc["hooks"]) == ["sessionStart"]
    [hook] = doc["hooks"]["sessionStart"]
    # The call operator is a token: "& " on a Windows host, where Cursor runs the
    # command through PowerShell, and empty elsewhere.
    assert hook["command"].startswith('${CALL_OP}"${PYTHON_BIN}" ')
    args = _dispatch_args(hook["command"])
    assert args == ["--contract", "cursor", "sessionStart"]
    contract = vc.get_contract("cursor")
    assert contract.canonical_event("sessionStart") == "SessionStart"
    assert contract.delivers == {"SessionStart"}
    assert contract.shape_for("SessionStart") == vc.SNAKE
    assert "matcher" not in hook, "sessionStart is not matched"
    assert "failClosed" not in hook, "a failing hook must not block"
    assert "preToolUse" not in doc["hooks"], "agent_message is read on a deny only"


def test_devin_registers_the_events_whose_context_reaches_the_model() -> None:
    contract = vc.get_contract("devin")
    calls = _devin_calls()
    assert [c[0] for c in calls] == ["SessionStart", "PostToolUse"]
    for event, contract_id, _messages, group in calls:
        assert contract_id == "devin"
        assert contract.canonical_event(event) in contract.delivers, event
        # Devin's matcher is a regex; an omitted one matches all and "*" is invalid.
        assert "matcher" not in group
        assert contract.shape_for(event) == vc.ENVELOPE
    assert "PreToolUse" not in json.loads(_DEVIN.read_text(encoding="utf-8"))["hooks"]


def test_session_start_is_idempotent_per_session_on_both_import_vendors() -> None:
    # Cursor and Devin Local also load Claude Code's settings file, so a
    # SessionStart command can fire twice for one session.
    for contract_id in ("cursor", "devin"):
        assert vc.get_contract(contract_id).dedupe_session_start is True


def test_the_cursor_and_devin_messages_exist_in_the_hooks_tree() -> None:
    messages = [name for _e, _c, names, _g in _devin_calls() for name in names]
    assert messages == ["posttooluse-proactive-compaction"]
    for name in messages:
        assert (_MESSAGES / f"{name}.md").is_file(), name


def test_the_dispatcher_stays_advisory_for_cursor_and_devin() -> None:
    for contract_id in ("cursor", "devin"):
        contract = vc.get_contract(contract_id)
        assert contract.output in {vc.SNAKE, vc.ENVELOPE}
        for event in contract.delivers:
            assert contract.shape_for(event) in {vc.SNAKE, vc.ENVELOPE}
