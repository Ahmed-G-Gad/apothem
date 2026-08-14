# SPDX-License-Identifier: MIT

"""Tests for `hooks.session_end_gate`.

Covers the per-session Stop gate: silence below the firing floor, exactly one
emission at or above it, and — the property whose absence caused the defect —
permanent silence for the rest of the session afterwards. Also covers the
envelope shape (``hookSpecificOutput`` with ``hookEventName: Stop``, never a
block/decision), the env-var floor override and kill switch, the rule that an
unreadable message file must not consume the session's single emission,
fail-open on missing / garbage session_id and corrupt state, and the dispatch
routing.

The headline test is ``TestTermination::test_many_stops_emit_exactly_once``: it
replays the shape that produced the original loop (a long run of Stop firings)
and pins the emission count at one. Before the gate, that count was unbounded.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_HOOKS_DIR = Path(__file__).resolve().parents[2] / "src" / "apothem" / "hooks"
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

import dispatch  # noqa: E402
import session_end_gate as seg  # noqa: E402

_PROTOCOL = "Session-end protocol.\n\nPhase A - externalize.\n"


@pytest.fixture(autouse=True)
def _isolate_state(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Redirect the OS temp dir to a per-test tmp_path so state never leaks.

    The gate derives its state directory from ``tempfile.gettempdir()``; pointing
    that at ``tmp_path`` isolates every test's state and guarantees no write
    lands in the repository tree.
    """
    monkeypatch.setattr(seg.tempfile, "gettempdir", lambda: str(tmp_path))


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure the gate's env vars start unset so defaults apply unless set."""
    monkeypatch.delenv(seg.MIN_STOPS_ENV, raising=False)
    monkeypatch.delenv(seg.ENABLED_ENV, raising=False)


@pytest.fixture
def message(tmp_path: Path) -> str:
    """Write a stand-in protocol message and return its path."""
    path = tmp_path / "stop.md"
    path.write_text(_PROTOCOL, encoding="utf-8")
    return str(path)


def _payload(session_id: object = "sess-1") -> dict[str, object]:
    """Build a Stop stdin payload with a session id."""
    return {"session_id": session_id, "hook_event_name": "Stop"}


def _run(message: str, count: int, session_id: object = "sess-1") -> list[dict]:
    """Fire the gate *count* times and return every envelope produced."""
    return [seg.evaluate(_payload(session_id), message) for _ in range(count)]


class TestFloor:
    def test_below_floor_is_silent(self, message: str) -> None:
        envelopes = _run(message, seg.DEFAULT_MIN_STOPS - 1)
        assert envelopes == [{}] * (seg.DEFAULT_MIN_STOPS - 1)

    def test_emits_on_reaching_the_floor(self, message: str) -> None:
        envelopes = _run(message, seg.DEFAULT_MIN_STOPS)
        assert envelopes[-1] != {}

    def test_floor_is_env_overridable(
        self, message: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(seg.MIN_STOPS_ENV, "1")
        assert seg.evaluate(_payload(), message) != {}

    @pytest.mark.parametrize("raw", ["0", "-4", "abc", ""])
    def test_unusable_floor_override_falls_back_to_default(
        self, raw: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(seg.MIN_STOPS_ENV, raw)
        assert seg.resolve_min_stops() == seg.DEFAULT_MIN_STOPS


class TestTermination:
    """The defect this module exists to prevent: emission that never stops."""

    def test_many_stops_emit_exactly_once(self, message: str) -> None:
        envelopes = _run(message, seg.DEFAULT_MIN_STOPS + 25)
        emitted = [env for env in envelopes if env]
        assert len(emitted) == 1

    def test_silent_immediately_after_emitting(self, message: str) -> None:
        _run(message, seg.DEFAULT_MIN_STOPS)
        assert seg.evaluate(_payload(), message) == {}

    def test_emitted_flag_latches_on_disk(self, message: str) -> None:
        _run(message, seg.DEFAULT_MIN_STOPS)
        state = seg._read_state(seg.state_path_for("sess-1"))
        assert state.emitted is True


class TestEnvelope:
    def test_uses_stop_hook_specific_shape(self, message: str) -> None:
        envelope = _run(message, seg.DEFAULT_MIN_STOPS)[-1]
        assert envelope == {
            "hookSpecificOutput": {
                "hookEventName": "Stop",
                "additionalContext": _PROTOCOL.strip(),
            }
        }

    def test_never_carries_a_block_decision(self, message: str) -> None:
        envelope = _run(message, seg.DEFAULT_MIN_STOPS)[-1]
        assert "decision" not in envelope
        assert "permissionDecision" not in json.dumps(envelope)

    def test_body_comes_from_the_message_file(self, tmp_path: Path) -> None:
        path = tmp_path / "stop.md"
        path.write_text("BODY FROM FILE", encoding="utf-8")
        envelope = _run(str(path), seg.DEFAULT_MIN_STOPS)[-1]
        assert envelope["hookSpecificOutput"]["additionalContext"] == "BODY FROM FILE"


class TestKillSwitch:
    @pytest.mark.parametrize("raw", ["0", "false", "FALSE", "no", "off", "Off"])
    def test_disabled_values_silence_the_protocol(
        self, message: str, raw: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(seg.ENABLED_ENV, raw)
        assert _run(message, seg.DEFAULT_MIN_STOPS + 5) == [{}] * (
            seg.DEFAULT_MIN_STOPS + 5
        )

    @pytest.mark.parametrize("raw", ["1", "true", "yes", "anything"])
    def test_other_values_leave_it_enabled(
        self, raw: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(seg.ENABLED_ENV, raw)
        assert seg.is_enabled() is True


class TestUnreadableMessage:
    """A read failure must not burn the session's one emission."""

    def test_missing_file_is_silent(self, tmp_path: Path) -> None:
        missing = str(tmp_path / "absent.md")
        assert _run(missing, seg.DEFAULT_MIN_STOPS) == [{}] * seg.DEFAULT_MIN_STOPS

    def test_missing_file_does_not_latch_emitted(self, tmp_path: Path) -> None:
        _run(str(tmp_path / "absent.md"), seg.DEFAULT_MIN_STOPS)
        state = seg._read_state(seg.state_path_for("sess-1"))
        assert state.emitted is False

    def test_protocol_still_delivered_once_the_file_returns(
        self, tmp_path: Path
    ) -> None:
        path = tmp_path / "stop.md"
        _run(str(path), seg.DEFAULT_MIN_STOPS)
        path.write_text(_PROTOCOL, encoding="utf-8")
        assert seg.evaluate(_payload(), str(path)) != {}

    def test_empty_file_is_silent(self, tmp_path: Path) -> None:
        path = tmp_path / "stop.md"
        path.write_text("   \n\n", encoding="utf-8")
        assert _run(str(path), seg.DEFAULT_MIN_STOPS) == [{}] * seg.DEFAULT_MIN_STOPS


class TestSessionIsolation:
    def test_distinct_sessions_gate_independently(self, message: str) -> None:
        _run(message, seg.DEFAULT_MIN_STOPS, session_id="sess-a")
        envelopes = _run(message, seg.DEFAULT_MIN_STOPS, session_id="sess-b")
        assert envelopes[-1] != {}

    @pytest.mark.parametrize("session_id", [None, 42, "", "   ", {"a": 1}])
    def test_unusable_session_id_falls_back_without_raising(
        self, message: str, session_id: object
    ) -> None:
        assert seg.evaluate(_payload(session_id), message) == {}

    def test_traversal_in_session_id_stays_inside_state_dir(self) -> None:
        path = seg.state_path_for("../../escape")
        assert path.parent == seg._state_dir()


class TestFailOpen:
    def test_corrupt_state_file_degrades_to_fresh(self, message: str) -> None:
        path = seg.state_path_for("sess-1")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{not json", encoding="utf-8")
        assert seg.evaluate(_payload(), message) == {}

    def test_none_payload_is_handled(self, message: str) -> None:
        assert seg.evaluate(None, message) == {}

    def test_main_emits_valid_json_when_evaluate_raises(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        def _boom(*_args: object, **_kwargs: object) -> dict[str, object]:
            raise RuntimeError("gate exploded")

        monkeypatch.setattr(seg, "evaluate", _boom)
        seg.main(["--context-file", "whatever"])
        assert json.loads(capsys.readouterr().out) == {}

    def test_main_without_context_flag_is_silent(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        seg.main([])
        assert json.loads(capsys.readouterr().out) == {}


class TestDispatchRouting:
    def test_stop_with_stop_basename_routes_to_the_gate(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        seen: list[str] = []
        monkeypatch.setattr(
            dispatch, "_run_session_end_gate", lambda ctx, _quiet: seen.append(ctx)
        )
        ctx = str(tmp_path / "stop.md")
        dispatch.dispatch("Stop", ctx, quiet=False)
        assert seen == [ctx]

    def test_stop_with_other_basename_still_emits_verbatim(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        routed: list[str] = []
        monkeypatch.setattr(
            dispatch, "_run_emit", lambda _e, ctx, _q: routed.append(ctx)
        )
        ctx = str(tmp_path / "some-other-context.md")
        dispatch.dispatch("Stop", ctx, quiet=False)
        assert routed == [ctx]

    def test_route_matches_with_and_without_suffix(self) -> None:
        assert dispatch._is_session_end_route("/x/y/stop.md") is True
        assert dispatch._is_session_end_route("stop") is True
        assert dispatch._is_session_end_route("/x/y/precompact.md") is False
