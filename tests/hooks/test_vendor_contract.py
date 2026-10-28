# SPDX-License-Identifier: MIT

"""The per-vendor hook contracts (``dispatch.py --contract <id>``).

Each vendor row of ``hooks/lib/vendor_contract.py`` is pinned against a stdin
payload shaped like the one that vendor documents (design note section 1b,
vendor pages retrieved 2026-10-28), so a change to a spelling, a shape or a
delivery rule fails here. The default command line, which Claude Code, Codex and
Qwen Code run, must not change by one byte, and no shape may carry a decision.

Cursor and Devin Local also run the Claude Code copy of the SessionStart command,
which they import from ``~/.claude/settings.json``. The sessions section pins that
the vendor's own registration and that copy share one per-session marker.
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_HOOKS_DIR = Path(__file__).resolve().parents[2] / "src" / "apothem" / "hooks"
for _path in (_HOOKS_DIR, _HOOKS_DIR / "lib"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import dispatch  # noqa: E402
import vendor_contract as vc  # noqa: E402
from events import SUPPORTED_EVENTS  # noqa: E402

_DISPATCH = _HOOKS_DIR / "dispatch.py"
#: Keys that would make an advisory hook a gate. No shape may carry one.
_DECISION_KEYS = {
    "permission",
    "permissionDecision",
    "decision",
    "continue",
    "stopReason",
    "followup_message",
    "modifiedInput",
    "updatedInput",
    "updated_input",
    "modifiedArgs",
}


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    (root / ".git").mkdir(parents=True)
    return root


def _env(tmp_path: Path, extra: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    env["APOTHEM_HOOK_STATE_DIR"] = str(tmp_path / "state")
    env.pop("APOTHEM_HOOKS_DISABLE", None)
    # A run inside Cursor or Devin must not make the default line look hosted.
    for name in (*vc.HOST_CONTRACT_BY_ENV, "CLAUDE_PROJECT_DIR", "LLM_PROJECT_DIR"):
        env.pop(name, None)
    env.update(extra or {})
    return env


def _run(
    tmp_path: Path,
    project: Path,
    args: list[str],
    payload: dict[str, object] | str,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    text = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.run(
        [sys.executable, str(_DISPATCH), *args],
        input=text,
        capture_output=True,
        text=True,
        env=_env(tmp_path, env),
        cwd=str(project),
        timeout=60,
        check=False,
    )


def _keys(value: object) -> set[str]:
    if isinstance(value, dict):
        found = set(value)
        for child in value.values():
            found |= _keys(child)
        return found
    if isinstance(value, list):
        return set().union(*(_keys(child) for child in value)) if value else set()
    return set()


def _git_commit(project: Path, tool: str, event: str) -> dict[str, object]:
    return {
        "session_id": "s-pre",
        "hook_event_name": event,
        "cwd": str(project),
        "tool_name": tool,
        "tool_input": {"command": 'git commit -m "Update the Resumption Contract"'},
    }


# --------------------------------------------------------------------------- #
# The table
# --------------------------------------------------------------------------- #


def test_every_contract_names_only_supported_events() -> None:
    for contract in vc.CONTRACTS.values():
        assert contract.delivers <= SUPPORTED_EVENTS, contract.contract_id
        assert set(contract.events.values()) <= SUPPORTED_EVENTS, contract.contract_id
        assert contract.output in {vc.ENVELOPE, vc.PLAIN, vc.FLAT, vc.SNAKE}


def test_the_six_contract_ids() -> None:
    # Trae hooks are deferred until the pickup probe passes, so no contract names it.
    assert set(vc.CONTRACTS) == {
        "claude",
        "codebuddy",
        "devin",
        "cursor",
        "copilot",
        "kiro",
    }


def test_the_claude_contract_delivers_every_event_the_dispatcher_routes() -> None:
    assert vc.CONTRACTS["claude"].delivers == SUPPORTED_EVENTS


def test_unknown_contract_raises() -> None:
    with pytest.raises(ValueError, match="Unknown hook contract"):
        vc.get_contract("nope")


def test_only_the_claude_importers_deduplicate() -> None:
    deduplicated = {
        c.contract_id for c in vc.CONTRACTS.values() if c.dedupe_session_start
    }
    assert deduplicated == {"cursor", "devin"}


def test_the_host_environment_names_match_the_dispatcher_and_the_contracts() -> None:
    # dispatch.py tests these without importing the shim, so the two must agree.
    assert tuple(vc.HOST_CONTRACT_BY_ENV) == dispatch._IMPORTING_HOST_ENV
    assert set(vc.HOST_CONTRACT_BY_ENV.values()) <= {
        c.contract_id for c in vc.CONTRACTS.values() if c.dedupe_session_start
    }
    # CLAUDE_PROJECT_DIR is Cursor's alias, so it must never identify a host.
    assert "CLAUDE_PROJECT_DIR" not in vc.HOST_CONTRACT_BY_ENV


# --------------------------------------------------------------------------- #
# Event aliases and tool names, one vendor payload each
# --------------------------------------------------------------------------- #

_TOOL_CASES = [
    ("codebuddy", "Bash", "Bash"),
    ("codebuddy", "Write", "Write"),
    ("devin", "exec", "Bash"),
    ("devin", "write", "Write"),
    ("devin", "edit", "Edit"),
    ("devin", "read", "Read"),
    ("devin", "apply_patch", "apply_patch"),
    ("cursor", "Shell", "Bash"),
    ("cursor", "Write", "Write"),
    ("copilot", "bash", "Bash"),
    ("copilot", "powershell", "PowerShell"),
    ("copilot", "create", "Write"),
    ("copilot", "edit", "Edit"),
    ("copilot", "Bash", "Bash"),
    ("kiro", "execute_bash", "Bash"),
    ("kiro", "execute_pwsh", "PowerShell"),
    ("kiro", "fs_write", "Write"),
    ("kiro", "str_replace", "Edit"),
]


@pytest.mark.parametrize(("contract_id", "vendor_tool", "claude_tool"), _TOOL_CASES)
def test_tool_names_normalise_to_claude_spelling(
    contract_id: str, vendor_tool: str, claude_tool: str
) -> None:
    contract = vc.get_contract(contract_id)
    payload = {"tool_name": vendor_tool, "tool_input": {"command": "ls"}}
    out = vc.normalise_payload(contract, payload, "PreToolUse")
    assert out["tool_name"] == claude_tool


_EVENT_CASES = [
    ("cursor", "sessionStart", "SessionStart"),
    ("cursor", "preToolUse", "PreToolUse"),
    ("cursor", "postToolUse", "PostToolUse"),
    ("cursor", "beforeSubmitPrompt", "UserPromptSubmit"),
    ("copilot", "sessionStart", "SessionStart"),
    ("copilot", "userPromptSubmitted", "UserPromptSubmit"),
    ("copilot", "SessionStart", "SessionStart"),
    ("devin", "PostCompaction", "PostCompact"),
    ("kiro", "SessionStart", "SessionStart"),
    ("codebuddy", "SessionStart", "SessionStart"),
]


@pytest.mark.parametrize(("contract_id", "vendor_event", "canonical"), _EVENT_CASES)
def test_event_aliases(contract_id: str, vendor_event: str, canonical: str) -> None:
    assert vc.get_contract(contract_id).canonical_event(vendor_event) == canonical


def test_cursor_session_start_payload() -> None:
    # cursor.com/docs/hooks: sessionStart carries session_id, is_background_agent,
    # composer_mode and the common fields (conversation_id, workspace_roots).
    payload = {
        "conversation_id": "conv-1",
        "hook_event_name": "sessionStart",
        "workspace_roots": ["/work/app"],
        "is_background_agent": False,
        "composer_mode": "agent",
    }
    out = vc.normalise_payload(vc.get_contract("cursor"), payload, "SessionStart")
    assert out["session_id"] == "conv-1"
    assert out["cwd"] == "/work/app"
    assert out["hook_event_name"] == "SessionStart"
    assert out["composer_mode"] == "agent"


def test_cursor_keeps_its_own_session_id_over_the_conversation_id() -> None:
    payload = {"session_id": "sess", "conversation_id": "conv"}
    out = vc.normalise_payload(vc.get_contract("cursor"), payload, "SessionStart")
    assert out["session_id"] == "sess"


def test_copilot_camel_case_payload() -> None:
    # hooks-reference: camelCase events use sessionId, timestamp (epoch ms), cwd,
    # toolName and toolArgs, and a postToolUse adds toolResult.
    payload = {
        "sessionId": "cp-1",
        "timestamp": 1761600000000,
        "cwd": "/work/app",
        "toolName": "bash",
        "toolArgs": '{"command":"git status"}',
        "toolResult": {"resultType": "success", "textResultForLlm": "ok"},
    }
    out = vc.normalise_payload(vc.get_contract("copilot"), payload, "PostToolUse")
    assert out["session_id"] == "cp-1"
    assert out["tool_name"] == "Bash"
    assert out["tool_input"] == {"command": "git status"}
    assert out["tool_response"] == {"resultType": "success", "textResultForLlm": "ok"}


def test_copilot_tool_args_that_are_not_json_become_empty() -> None:
    payload = {"toolName": "bash", "toolArgs": "not json"}
    out = vc.normalise_payload(vc.get_contract("copilot"), payload, "PreToolUse")
    assert out["tool_input"] == {}


def test_copilot_pascal_case_payload_is_already_claude_shaped() -> None:
    # A PascalCase event name selects the VS Code-compatible snake_case payload.
    payload = {
        "hook_event_name": "PostToolUse",
        "session_id": "cp-2",
        "timestamp": "2026-10-28T10:00:00.000Z",
        "cwd": "/work/app",
        "tool_name": "Bash",
        "tool_input": {"command": "ls"},
    }
    out = vc.normalise_payload(vc.get_contract("copilot"), payload, "PostToolUse")
    assert out == payload


def test_kiro_payload() -> None:
    # kiro.dev hooks: hook_event_name, cwd, session_id, tool_name, tool_input.
    payload = {
        "hook_event_name": "PreToolUse",
        "cwd": "/work/app",
        "session_id": "k-1",
        "tool_name": "execute_bash",
        "tool_input": {"command": "ls"},
    }
    out = vc.normalise_payload(vc.get_contract("kiro"), payload, "PreToolUse")
    assert out["tool_name"] == "Bash"
    assert out["session_id"] == "k-1"


def test_devin_payload() -> None:
    # docs.devin.ai hooks: hook_event_name, lowercase tool_name, tool_input,
    # session_id.
    payload = {
        "hook_event_name": "PostToolUse",
        "session_id": "d-1",
        "tool_name": "exec",
        "tool_input": {"command": "ls"},
    }
    out = vc.normalise_payload(vc.get_contract("devin"), payload, "PostToolUse")
    assert out["tool_name"] == "Bash"


def test_devin_learns_the_project_directory_from_its_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # lifecycle-hooks.md documents no cwd on stdin; overview.md says
    # DEVIN_PROJECT_DIR is set to the project root.
    monkeypatch.setenv("DEVIN_PROJECT_DIR", "/work/devin-app")
    devin = vc.get_contract("devin")
    bare = {"hook_event_name": "SessionStart", "session_id": "d-1", "source": "startup"}
    assert vc.normalise_payload(devin, bare, "SessionStart")["cwd"] == "/work/devin-app"
    # A cwd the payload does carry, and Cursor's workspace_roots, still win.
    own = {**bare, "cwd": "/elsewhere"}
    assert vc.normalise_payload(devin, own, "SessionStart")["cwd"] == "/elsewhere"
    roots = {**bare, "workspace_roots": ["/work/roots"]}
    assert vc.normalise_payload(devin, roots, "SessionStart")["cwd"] == "/work/roots"
    monkeypatch.delenv("DEVIN_PROJECT_DIR")
    assert "cwd" not in vc.normalise_payload(devin, bare, "SessionStart")


def test_only_devin_reads_a_project_directory_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEVIN_PROJECT_DIR", "/work/devin-app")
    for contract_id in ("codebuddy", "kiro", "copilot", "cursor"):
        contract = vc.get_contract(contract_id)
        assert "cwd" not in vc.normalise_payload(contract, {}, "SessionStart")


def test_codebuddy_payload_passes_through_unchanged() -> None:
    # codebuddy.ai hooks: session_id, transcript_path, cwd, permission_mode,
    # hook_event_name, tool_name, tool_input (+ tool_response on PostToolUse).
    payload = {
        "session_id": "cb-1",
        "transcript_path": "/work/app/transcript.jsonl",
        "cwd": "/work/app",
        "permission_mode": "default",
        "hook_event_name": "PostToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": "ls"},
        "tool_response": {"stdout": "x"},
    }
    out = vc.normalise_payload(vc.get_contract("codebuddy"), payload, "PostToolUse")
    assert out == payload


# --------------------------------------------------------------------------- #
# Output shapes
# --------------------------------------------------------------------------- #

_ENVELOPE = json.dumps(
    {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": "Be brief.",
        }
    }
)
_SILENT = json.dumps(
    {"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": ""}}
)


def test_envelope_shape_is_left_byte_for_byte() -> None:
    codebuddy = vc.get_contract("codebuddy")
    assert (
        vc.shape_output(codebuddy, "SessionStart", _ENVELOPE + "\n") == _ENVELOPE + "\n"
    )
    assert vc.shape_output(codebuddy, "PostToolUse", "{}\n") == "{}\n"
    assert vc.shape_output(codebuddy, "PostToolUse", "") == ""


@pytest.mark.parametrize(
    ("contract_id", "expected"),
    [
        ("kiro", "Be brief.\n"),
        ("copilot", '{"additionalContext":"Be brief."}\n'),
        ("cursor", '{"additional_context":"Be brief."}\n'),
    ],
)
def test_session_start_shapes(contract_id: str, expected: str) -> None:
    contract = vc.get_contract(contract_id)
    assert vc.shape_output(contract, "SessionStart", _ENVELOPE + "\n") == expected


@pytest.mark.parametrize("contract_id", ["kiro", "copilot", "cursor"])
def test_a_silent_handler_stays_silent_in_every_shape(contract_id: str) -> None:
    contract = vc.get_contract(contract_id)
    for captured in ("", "{}\n", _SILENT + "\n"):
        assert vc.shape_output(contract, "SessionStart", captured) == ""


def test_system_message_is_not_model_context() -> None:
    contract = vc.get_contract("copilot")
    captured = json.dumps({"systemMessage": "for the operator"})
    assert vc.shape_output(contract, "PostToolUse", captured) == ""


@pytest.mark.parametrize("contract_id", sorted(vc.CONTRACTS))
def test_no_shape_carries_a_decision(contract_id: str) -> None:
    contract = vc.get_contract(contract_id)
    hostile = json.dumps(
        {
            "decision": "block",
            "continue": False,
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "additionalContext": "advice",
            },
        }
    )
    for event in ("SessionStart", "PostToolUse", "UserPromptSubmit"):
        shaped = vc.shape_output(contract, event, hostile)
        if contract.output == vc.ENVELOPE:
            continue  # left as the handler wrote it; the handlers never write a decision
        keys = _keys(json.loads(shaped)) if shaped.startswith("{") else set()
        assert not keys & _DECISION_KEYS, (contract_id, event, keys)


# --------------------------------------------------------------------------- #
# Delivery, failure and sessions (in process)
# --------------------------------------------------------------------------- #


def test_an_undelivered_event_runs_no_handler(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(sys, "stdin", io.StringIO("{}"))
    vc.run_contracted("kiro", "PreToolUse", calls.append)
    vc.run_contracted("cursor", "preToolUse", calls.append)
    vc.run_contracted("copilot", "preToolUse", calls.append)
    vc.run_contracted("codebuddy", "PreToolUse", calls.append)
    assert calls == []


def test_the_handler_gets_the_canonical_event_and_a_claude_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[tuple[str, object]] = []

    def handler(event: str) -> None:
        seen.append((event, json.loads(sys.stdin.read())))

    payload = {"conversation_id": "c9", "workspace_roots": ["/w"]}
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    vc.run_contracted("copilot", "sessionStart", handler)
    assert seen
    assert seen[0][0] == "SessionStart"
    assert seen[0][1]["session_id"] == "c9"  # type: ignore[index]
    assert seen[0][1]["cwd"] == "/w"  # type: ignore[index]


def test_a_handler_error_becomes_a_shaped_failure_message(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def boom(event: str) -> None:
        raise RuntimeError("handler broke")

    monkeypatch.setattr(sys, "stdin", io.StringIO("{}"))
    vc.run_contracted("kiro", "SessionStart", boom)
    assert capsys.readouterr().out == "Hook execution failure: handler broke\n"


def test_a_handler_error_under_an_envelope_contract_is_an_envelope(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def boom(event: str) -> None:
        raise RuntimeError("handler broke")

    monkeypatch.setattr(sys, "stdin", io.StringIO("{}"))
    vc.run_contracted("codebuddy", "PostToolUse", boom)
    parsed = json.loads(capsys.readouterr().out)
    assert parsed["hookSpecificOutput"]["hookEventName"] == "PostToolUse"
    assert "handler broke" in parsed["hookSpecificOutput"]["additionalContext"]


def test_stdin_is_restored_after_a_contracted_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = io.StringIO("{}")
    monkeypatch.setattr(sys, "stdin", original)
    vc.run_contracted("kiro", "SessionStart", lambda event: None)
    assert sys.stdin is original


def test_session_start_runs_once_per_session_and_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("APOTHEM_HOOK_STATE_DIR", str(tmp_path / "state"))
    first = {"session_id": "s1", "source": "startup"}
    assert vc.first_session_start(first) is True
    assert vc.first_session_start(first) is False
    # The compaction firing of the same session still delivers its recovery text.
    assert vc.first_session_start({"session_id": "s1", "source": "compact"})
    assert vc.first_session_start({"session_id": "s2", "source": "startup"})


def test_the_marker_is_shared_whichever_registration_runs_first(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The key names the session and the source, not the contract: the vendor's
    # own registration and the Claude Code copy it imports are one start.
    monkeypatch.setenv("APOTHEM_HOOK_STATE_DIR", str(tmp_path / "state"))
    payload = {"session_id": "shared", "source": "startup"}
    assert vc.first_session_start(payload) is True
    assert vc.first_session_start(dict(payload)) is False
    markers = list((tmp_path / "state" / "session-start").glob("*.seen"))
    assert [m.name for m in markers] == ["shared--start.seen"]


def test_a_missing_source_and_startup_are_the_same_first_start(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Cursor's sessionStart has no source; the Claude Code copy may say "startup".
    monkeypatch.setenv("APOTHEM_HOOK_STATE_DIR", str(tmp_path / "state"))
    assert vc.first_session_start({"session_id": "s1"}) is True
    assert vc.first_session_start({"session_id": "s1", "source": "startup"}) is False
    assert vc.first_session_start({"session_id": "s1", "source": "compact"}) is True


def test_a_repeat_after_the_window_is_a_new_start_not_a_duplicate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A second compaction (or resume, or clear) of one session delivers again; only
    # a start inside the duplicate window is silenced.
    monkeypatch.setenv("APOTHEM_HOOK_STATE_DIR", str(tmp_path / "state"))
    compact = {"session_id": "s1", "source": "compact"}
    assert vc.first_session_start(compact) is True
    assert vc.first_session_start(compact) is False
    marker = next((tmp_path / "state" / "session-start").glob("*.seen"))
    aged = marker.stat().st_mtime - (vc._DUPLICATE_WINDOW_SECONDS + 5)
    os.utime(marker, (aged, aged))
    assert vc.first_session_start(compact) is True
    # The second compaction's own duplicate is silent again.
    assert vc.first_session_start(compact) is False


def test_a_payload_with_no_session_id_is_never_suppressed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("APOTHEM_HOOK_STATE_DIR", str(tmp_path / "state"))
    for payload in (None, {}, {"source": "startup"}, {"session_id": "  "}):
        assert vc.first_session_start(payload) is True
        assert vc.first_session_start(payload) is True


def _record_starts(
    monkeypatch: pytest.MonkeyPatch, payload: dict[str, object], contract_id: str
) -> int:
    calls: list[str] = []
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    vc.run_contracted(contract_id, "sessionStart", calls.append)
    return len(calls)


def test_two_conversations_that_send_only_a_conversation_id_both_deliver(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The key is built from the normalised payload, so conversation_id (and
    # sessionId) separate conversations that the parent-process fallback would merge.
    monkeypatch.setenv("APOTHEM_HOOK_STATE_DIR", str(tmp_path / "state"))
    assert _record_starts(monkeypatch, {"conversation_id": "convA"}, "cursor") == 1
    assert _record_starts(monkeypatch, {"conversation_id": "convB"}, "cursor") == 1
    # The same conversation's duplicate is the one that is silent.
    assert _record_starts(monkeypatch, {"conversation_id": "convA"}, "cursor") == 0


def test_a_state_directory_that_cannot_be_written_never_suppresses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    blocker = tmp_path / "file"
    blocker.write_text("x", encoding="utf-8")
    monkeypatch.setenv("APOTHEM_HOOK_STATE_DIR", str(blocker / "sub"))
    assert vc.first_session_start({"session_id": "s1"}) is True
    assert vc.first_session_start({"session_id": "s1"}) is True


def test_stale_markers_are_purged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("APOTHEM_HOOK_STATE_DIR", str(tmp_path / "state"))
    assert vc.first_session_start({"session_id": "old"})
    marker = next((tmp_path / "state" / "session-start").glob("*.seen"))
    ancient = marker.stat().st_mtime - (vc._MARKER_MAX_AGE_SECONDS + 60)
    os.utime(marker, (ancient, ancient))
    assert vc.first_session_start({"session_id": "new"})
    assert not marker.exists()


def test_the_default_start_under_a_host_hands_the_handler_the_vendor_spellings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("APOTHEM_HOOK_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("CURSOR_PROJECT_DIR", "/work/app")
    seen: list[dict[str, object]] = []
    payload = {"conversation_id": "c1", "workspace_roots": ["/work/app"]}
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    original = sys.stdin
    vc.run_session_start_once(lambda: seen.append(json.loads(sys.stdin.read())))
    assert seen[0]["session_id"] == "c1"
    assert seen[0]["cwd"] == "/work/app"
    assert sys.stdin is original


def test_the_default_start_off_a_host_is_passed_through_untouched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("APOTHEM_HOOK_STATE_DIR", str(tmp_path / "state"))
    for name in vc.HOST_CONTRACT_BY_ENV:
        monkeypatch.delenv(name, raising=False)
    seen: list[str] = []
    raw = '{"session_id": "s", "x":   1}'
    for _ in range(2):  # no marker is ever consulted, so both runs deliver
        monkeypatch.setattr(sys, "stdin", io.StringIO(raw))
        vc.run_session_start_once(lambda: seen.append(sys.stdin.read()))
    assert seen == [raw, raw]
    assert not (tmp_path / "state" / "session-start").exists()


def test_a_marker_failure_never_suppresses_the_default_start(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CURSOR_PROJECT_DIR", "/work/app")

    def broken(_payload: object) -> bool:
        raise RuntimeError("marker broke")

    monkeypatch.setattr(vc, "first_session_start", broken)
    seen: list[str] = []
    monkeypatch.setattr(sys, "stdin", io.StringIO('{"session_id": "s"}'))
    vc.run_session_start_once(lambda: seen.append(sys.stdin.read()))
    assert seen == ['{"session_id": "s"}']


# --------------------------------------------------------------------------- #
# The dispatcher command line
# --------------------------------------------------------------------------- #


def test_fast_parse_reads_the_contract_flag() -> None:
    fast = dispatch.fast_parse(["--contract", "kiro", "SessionStart"])
    assert fast is not None
    assert fast.contract == "kiro"
    assert fast.event_name == "SessionStart"
    assert dispatch.fast_parse(["SessionStart"]).contract == ""  # type: ignore[union-attr]
    # A flag without a value falls back to argparse, which rejects it.
    assert dispatch.fast_parse(["SessionStart", "--contract"]) is None


def test_parse_args_reads_the_contract_flag() -> None:
    assert dispatch.parse_args(["--contract=kiro", "SessionStart"]).contract == "kiro"
    assert dispatch.parse_args(["SessionStart"]).contract == ""


def test_the_default_command_line_never_imports_the_shim(
    project: Path, tmp_path: Path
) -> None:
    code = (
        f"import sys; sys.path.insert(0, {str(_HOOKS_DIR)!r}); import dispatch; "
        "dispatch.main(['PreToolUse', 'pretooluse-bash']); "
        "print('vendor_contract' in sys.modules)"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env=_env(tmp_path),
        cwd=str(project),
        check=False,
        input="",
    )
    assert result.stdout.strip().splitlines()[-1] == "False"


def _imports_shim(project: Path, tmp_path: Path, argv: str, env: dict[str, str]):
    code = (
        f"import sys; sys.path.insert(0, {str(_HOOKS_DIR)!r}); import dispatch; "
        f"dispatch.main({argv}); print('vendor_contract' in sys.modules)"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env=_env(tmp_path, env),
        cwd=str(project),
        check=False,
        input="",
    )
    return result.stdout.strip().splitlines()[-1]


def test_the_default_session_start_imports_the_shim_only_under_a_host(
    project: Path, tmp_path: Path
) -> None:
    assert _imports_shim(project, tmp_path, "['SessionStart']", {}) == "False"
    hosted = {"CURSOR_PROJECT_DIR": str(project)}
    assert _imports_shim(project, tmp_path, "['SessionStart']", hosted) == "True"
    hosted = {"DEVIN_PROJECT_DIR": str(project)}
    assert _imports_shim(project, tmp_path, "['SessionStart']", hosted) == "True"
    # Only SessionStart takes part; a tool event never does.
    assert (
        _imports_shim(project, tmp_path, "['PreToolUse', 'pretooluse-bash']", hosted)
        == "False"
    )


def test_an_unknown_contract_fails_open(project: Path, tmp_path: Path) -> None:
    result = _run(tmp_path, project, ["--contract", "nope", "SessionStart"], {})
    assert result.returncode == 0
    parsed = json.loads(result.stdout)
    assert "Unknown hook contract" in parsed["hookSpecificOutput"]["additionalContext"]


def test_the_kill_switch_silences_a_contracted_command(
    project: Path, tmp_path: Path
) -> None:
    env = _env(tmp_path)
    env["APOTHEM_HOOKS_DISABLE"] = "1"
    result = subprocess.run(
        [sys.executable, str(_DISPATCH), "--contract", "kiro", "SessionStart"],
        input="{}",
        capture_output=True,
        text=True,
        env=env,
        cwd=str(project),
        check=False,
    )
    assert (result.returncode, result.stdout) == (0, "")


# --------------------------------------------------------------------------- #
# End to end through the real handlers
# --------------------------------------------------------------------------- #

_BASH_PRE = ["PreToolUse", "pretooluse-bash"]


def test_claude_contract_is_byte_identical_to_the_default(
    project: Path, tmp_path: Path
) -> None:
    payload = _git_commit(project, "Bash", "PreToolUse")
    plain = _run(tmp_path, project, _BASH_PRE, payload)
    contracted = _run(tmp_path, project, ["--contract", "claude", *_BASH_PRE], payload)
    assert plain.stdout
    assert plain.stdout == contracted.stdout
    assert plain.returncode == contracted.returncode == 0


@pytest.mark.parametrize(
    ("event", "message"), [("PreCompact", "precompact"), ("PostCompact", "postcompact")]
)
def test_claude_contract_delivers_the_compaction_events_like_the_default(
    project: Path, tmp_path: Path, event: str, message: str
) -> None:
    payload = {"session_id": "cl-c", "hook_event_name": event, "cwd": str(project)}
    plain = _run(tmp_path, project, [event, message], payload)
    contracted = _run(
        tmp_path, project, ["--contract", "claude", event, message], payload
    )
    assert plain.stdout
    assert plain.stdout == contracted.stdout


def test_codebuddy_session_start_is_byte_identical_to_the_default(
    project: Path, tmp_path: Path
) -> None:
    payload = {
        "session_id": "cb-1",
        "hook_event_name": "SessionStart",
        "source": "startup",
        "cwd": str(project),
        "permission_mode": "default",
    }
    plain = _run(tmp_path, project, ["SessionStart"], payload)
    contracted = _run(
        tmp_path, project, ["--contract", "codebuddy", "SessionStart"], payload
    )
    assert plain.stdout
    assert plain.stdout == contracted.stdout
    parsed = json.loads(contracted.stdout)
    assert parsed["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert parsed["hookSpecificOutput"]["additionalContext"]


def test_codebuddy_post_tool_use_runs_the_tracker(
    project: Path, tmp_path: Path
) -> None:
    payload = {
        "session_id": "cb-2",
        "hook_event_name": "PostToolUse",
        "cwd": str(project),
        "tool_name": "Read",
        "tool_input": {},
        "tool_response": "x" * 32,
    }
    args = ["PostToolUse", "posttooluse-proactive-compaction"]
    plain = _run(tmp_path, project, args, payload)
    contracted = _run(tmp_path, project, ["--contract", "codebuddy", *args], payload)
    assert plain.stdout == contracted.stdout
    assert contracted.returncode == 0


def test_codebuddy_pre_tool_use_is_not_delivered(project: Path, tmp_path: Path) -> None:
    # codebuddy.ai documents no additionalContext for PreToolUse, so a guard
    # registered there produces no output.
    result = _run(
        tmp_path,
        project,
        ["--contract", "codebuddy", *_BASH_PRE],
        _git_commit(project, "Bash", "PreToolUse"),
    )
    assert (result.returncode, result.stdout) == (0, "")


def test_kiro_session_start_is_bare_text(project: Path, tmp_path: Path) -> None:
    payload = {
        "hook_event_name": "SessionStart",
        "cwd": str(project),
        "session_id": "k-1",
    }
    result = _run(tmp_path, project, ["--contract", "kiro", "SessionStart"], payload)
    assert result.returncode == 0
    assert result.stdout.strip()
    assert not result.stdout.lstrip().startswith("{")


def test_kiro_tool_events_produce_nothing(project: Path, tmp_path: Path) -> None:
    result = _run(
        tmp_path,
        project,
        ["--contract", "kiro", *_BASH_PRE],
        _git_commit(project, "execute_bash", "PreToolUse"),
    )
    assert (result.returncode, result.stdout) == (0, "")


def test_copilot_camel_case_session_start_is_a_flat_object(
    project: Path, tmp_path: Path
) -> None:
    payload = {"sessionId": "cp-1", "timestamp": 1761600000000, "cwd": str(project)}
    result = _run(tmp_path, project, ["--contract", "copilot", "sessionStart"], payload)
    parsed = json.loads(result.stdout)
    assert set(parsed) == {"additionalContext"}
    assert parsed["additionalContext"]


_START = {
    "session_id": "dup-1",
    "hook_event_name": "SessionStart",
    "source": "startup",
}


def _start_payload(project: Path, **extra: object) -> dict[str, object]:
    return {**_START, "cwd": str(project), "workspace_roots": [str(project)], **extra}


def test_cursor_session_start_is_idempotent_per_session(
    project: Path, tmp_path: Path
) -> None:
    payload = _start_payload(project, hook_event_name="sessionStart")
    args = ["--contract", "cursor", "sessionStart"]
    first = _run(tmp_path, project, args, payload)
    second = _run(tmp_path, project, args, payload)
    assert set(json.loads(first.stdout)) == {"additional_context"}
    assert (second.returncode, second.stdout) == (0, "")


_HOSTS = [
    pytest.param("cursor", "sessionStart", "CURSOR_PROJECT_DIR", id="cursor"),
    pytest.param("cursor", "sessionStart", "CURSOR_VERSION", id="cursor-version"),
    pytest.param("devin", "SessionStart", "DEVIN_PROJECT_DIR", id="devin"),
]


@pytest.mark.parametrize(("contract", "event", "host_var"), _HOSTS)
def test_the_claude_copy_first_silences_the_vendor_copy(
    project: Path, tmp_path: Path, contract: str, event: str, host_var: str
) -> None:
    # Cursor and Devin Local run the hook registered natively and the Claude Code
    # copy they import from ~/.claude/settings.json: the bootstrap reaches the
    # model once, whichever of the two runs first.
    payload = _start_payload(project, hook_event_name=event)
    host = {host_var: str(project)}
    claude_copy = _run(tmp_path, project, ["SessionStart"], payload, host)
    vendor_copy = _run(
        tmp_path, project, ["--contract", contract, event], payload, host
    )
    assert claude_copy.stdout.strip()
    assert (vendor_copy.returncode, vendor_copy.stdout) == (0, "")


@pytest.mark.parametrize(("contract", "event", "host_var"), _HOSTS)
def test_the_vendor_copy_first_silences_the_claude_copy(
    project: Path, tmp_path: Path, contract: str, event: str, host_var: str
) -> None:
    payload = _start_payload(project, hook_event_name=event)
    host = {host_var: str(project)}
    vendor_copy = _run(
        tmp_path, project, ["--contract", contract, event], payload, host
    )
    claude_copy = _run(tmp_path, project, ["SessionStart"], payload, host)
    assert vendor_copy.stdout.strip()
    assert (claude_copy.returncode, claude_copy.stdout) == (0, "")


def test_a_different_session_is_delivered_by_both_copies(
    project: Path, tmp_path: Path
) -> None:
    host = {"CURSOR_PROJECT_DIR": str(project)}
    one = _start_payload(project, hook_event_name="sessionStart", session_id="a")
    two = _start_payload(project, hook_event_name="sessionStart", session_id="b")
    native = ["--contract", "cursor", "sessionStart"]
    assert _run(tmp_path, project, native, one, host).stdout.strip()
    assert _run(tmp_path, project, ["SessionStart"], two, host).stdout.strip()


def test_the_default_session_start_under_a_host_is_the_handlers_own_output(
    project: Path, tmp_path: Path
) -> None:
    # Taking part in the marker changes who speaks, never what is said.
    payload = _start_payload(project)
    bare = _run(tmp_path / "off", project, ["SessionStart"], payload)
    hosted = _run(
        tmp_path / "on",
        project,
        ["SessionStart"],
        payload,
        {"CURSOR_PROJECT_DIR": str(project)},
    )
    assert bare.stdout
    assert bare.stdout == hosted.stdout


def test_default_session_start_is_not_deduplicated_off_a_host(
    project: Path, tmp_path: Path
) -> None:
    payload = {
        "session_id": "cl-1",
        "hook_event_name": "SessionStart",
        "source": "startup",
        "cwd": str(project),
    }
    first = _run(tmp_path, project, ["SessionStart"], payload)
    second = _run(tmp_path, project, ["SessionStart"], payload)
    assert first.stdout
    assert first.stdout == second.stdout


def test_a_devin_session_start_resolves_the_project_from_its_environment(
    project: Path, tmp_path: Path
) -> None:
    # Devin sends no cwd; the project root is DEVIN_PROJECT_DIR. The plan summary
    # in the bootstrap names the suite that lives in that project, even though the
    # process was spawned in a directory that is not it.
    suite = project / ".apothem" / "plans" / "devin-suite-marker"
    suite.mkdir(parents=True)
    (suite / "PROGRESS.md").write_text("## Status: in-progress\n", encoding="utf-8")
    (suite / "PLAN-NOTES.md").write_text("# Notes\n", encoding="utf-8")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    payload = {"session_id": "dv-1", "hook_event_name": "SessionStart"}
    result = subprocess.run(
        [sys.executable, str(_DISPATCH), "--contract", "devin", "SessionStart"],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=_env(tmp_path, {"DEVIN_PROJECT_DIR": str(project)}),
        cwd=str(elsewhere),
        timeout=60,
        check=False,
    )
    assert result.returncode == 0
    assert "devin-suite-marker" in result.stdout


def test_malformed_and_empty_stdin_fail_open(project: Path, tmp_path: Path) -> None:
    for text in ("", "not json", "[1, 2]"):
        result = _run(tmp_path, project, ["--contract", "kiro", "SessionStart"], text)
        assert result.returncode == 0, text
