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
