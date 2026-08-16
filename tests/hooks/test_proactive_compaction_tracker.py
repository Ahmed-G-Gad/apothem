# SPDX-License-Identifier: MIT

"""Tests for `hooks.proactive_compaction_tracker`.

Covers the per-session PostToolUse activity tracker: the counter increments per
tool call, the advisory fires once a threshold crosses then backs off (anti-spam
reset), the advisory envelope shape (systemMessage + additionalContext, never a
block/decision), the env-var threshold overrides, fail-open on missing / garbage
session_id and corrupt state, and the dispatch routing.
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest

_HOOKS_DIR = Path(__file__).resolve().parents[2] / "src" / "apothem" / "hooks"
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

import dispatch  # noqa: E402
import proactive_compaction_tracker as pct  # noqa: E402


@pytest.fixture(autouse=True)
def _isolate_state(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Redirect the OS temp dir to a per-test tmp_path so state never leaks.

    The tracker derives its state directory from ``tempfile.gettempdir()``;
    pointing that at ``tmp_path`` isolates every test's counters and guarantees
    no write lands in the repository tree.
    """
    monkeypatch.setattr(pct.tempfile, "gettempdir", lambda: str(tmp_path))


@pytest.fixture(autouse=True)
def _clear_threshold_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure threshold env vars start unset so defaults apply unless a test sets them."""
    monkeypatch.delenv(pct.TOOL_THRESHOLD_ENV, raising=False)
    monkeypatch.delenv(pct.OUTPUT_THRESHOLD_ENV, raising=False)


def _payload(
    session_id: object = "sess-1", *, output: object = ""
) -> dict[str, object]:
    """Build a PostToolUse stdin payload with a session id and tool response."""
    return {
        "session_id": session_id,
        "hook_event_name": "PostToolUse",
        "tool_name": "Read",
        "tool_response": output,
    }


class TestCounterIncrement:
    """Accumulating the per-session activity counter.

    Covers that a single call below the threshold stays silent, that the count
    persists across calls, and that distinct sessions count independently so one
    session cannot trip another's advisory.
    """

    def test_single_call_below_threshold_is_silent(self) -> None:
        envelope = pct.evaluate(_payload())
        assert envelope == {}

    def test_counter_persists_across_calls(self) -> None:
        for _ in range(3):
            pct.evaluate(_payload())
        state = pct._read_state(pct.state_path_for("sess-1"))
        assert state.tool_calls == 3

    def test_distinct_sessions_count_independently(self) -> None:
        pct.evaluate(_payload("sess-a"))
        pct.evaluate(_payload("sess-a"))
        pct.evaluate(_payload("sess-b"))
        assert pct._read_state(pct.state_path_for("sess-a")).tool_calls == 2
        assert pct._read_state(pct.state_path_for("sess-b")).tool_calls == 1


class TestThresholdFires:
    """Firing and backing off the compaction advisory.

    Covers both trigger paths — the tool-call threshold and the output-byte
    threshold above its call floor — and the back-off that holds the advisory to
    one per window even under consecutive large outputs. Also covers that firing
    resets the output counter, not just the call counter.
    """

    def test_tool_threshold_fires_once_then_backs_off(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(pct.TOOL_THRESHOLD_ENV, "3")
        # Two calls below threshold: silent.
        assert pct.evaluate(_payload()) == {}
        assert pct.evaluate(_payload()) == {}
        # Third call crosses the threshold: advisory fires.
        fired = pct.evaluate(_payload())
        assert "systemMessage" in fired
        assert "proactive-compaction" in fired["systemMessage"]
        # Back-off: counters reset, so the next call is silent again.
        assert pct.evaluate(_payload()) == {}
        assert pct._read_state(pct.state_path_for("sess-1")).tool_calls == 1

    def test_output_threshold_fires_after_call_floor(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(pct.OUTPUT_THRESHOLD_ENV, "100")
        monkeypatch.setenv(pct.TOOL_THRESHOLD_ENV, "9999")  # keep tool path inert
        # The cumulative-output threshold is gated on the tool-call floor: a
        # single over-threshold output cannot fire on its own next call, so the
        # calls below the floor stay silent even though each is over threshold.
        for _ in range(pct._MIN_CALLS_FOR_OUTPUT_TRIGGER - 1):
            assert pct.evaluate(_payload(output="x" * 200)) == {}
        # The call that reaches the floor (output already over threshold) fires.
        fired = pct.evaluate(_payload(output="x" * 200))
        assert "systemMessage" in fired

    def test_consecutive_large_outputs_back_off_to_one_advisory_per_window(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Regression for the back-off defeat: before the call-floor gate, every
        # single over-threshold output raised its own advisory. Two full windows
        # of consecutive large outputs must now yield exactly one advisory each.
        monkeypatch.setenv(pct.OUTPUT_THRESHOLD_ENV, "100")
        monkeypatch.setenv(pct.TOOL_THRESHOLD_ENV, "9999")
        floor = pct._MIN_CALLS_FOR_OUTPUT_TRIGGER
        fires = sum(
            "systemMessage" in pct.evaluate(_payload(output="x" * 200))
            for _ in range(2 * floor)
        )
        assert fires == 2

    def test_advisory_resets_output_counter_too(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(pct.OUTPUT_THRESHOLD_ENV, "100")
        monkeypatch.setenv(pct.TOOL_THRESHOLD_ENV, "9999")
        # Reach the call floor so the output threshold actually fires, then the
        # window — output bytes included — resets as the anti-spam back-off.
        for _ in range(pct._MIN_CALLS_FOR_OUTPUT_TRIGGER):
            pct.evaluate(_payload(output="x" * 200))
        state = pct._read_state(pct.state_path_for("sess-1"))
        assert state.output_bytes == 0


class TestAdvisoryShape:
    """Shape of the emitted advisory envelope.

    Covers that the advisory carries both the system message and the additional
    context, and that it never blocks — the tracker advises, it does not gate.
    """

    def test_advisory_carries_systemmessage_and_additional_context(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(pct.TOOL_THRESHOLD_ENV, "1")
        fired = pct.evaluate(_payload())
        assert isinstance(fired["systemMessage"], str)
        hook_out = fired["hookSpecificOutput"]
        assert isinstance(hook_out, dict)
        assert hook_out["hookEventName"] == "PostToolUse"
        assert isinstance(hook_out["additionalContext"], str)

    def test_advisory_never_blocks(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # A PostToolUse hook must never carry a block/decision control field.
        # Only the advisory-bearing keys are present; no decision/permission key.
        monkeypatch.setenv(pct.TOOL_THRESHOLD_ENV, "1")
        fired = pct.evaluate(_payload())
        assert "decision" not in fired
        assert "permissionDecision" not in fired
        assert set(fired) == {"systemMessage", "hookSpecificOutput"}


class TestEnvOverride:
    """Threshold override from the environment.

    Covers the unset default, a valid override applying, and an invalid override
    falling back to the default rather than raising.
    """

    def test_default_when_unset(self) -> None:
        thresholds = pct.resolve_thresholds()
        assert thresholds.tool_calls == pct.DEFAULT_TOOL_THRESHOLD
        assert thresholds.output_bytes == pct.DEFAULT_OUTPUT_THRESHOLD

    def test_valid_override_applies(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(pct.TOOL_THRESHOLD_ENV, "5")
        monkeypatch.setenv(pct.OUTPUT_THRESHOLD_ENV, "1234")
        thresholds = pct.resolve_thresholds()
        assert thresholds.tool_calls == 5
        assert thresholds.output_bytes == 1234

    @pytest.mark.parametrize("bad", ["0", "-4", "abc", "", "  "])
    def test_invalid_override_falls_back_to_default(
        self, monkeypatch: pytest.MonkeyPatch, bad: str
    ) -> None:
        monkeypatch.setenv(pct.TOOL_THRESHOLD_ENV, bad)
        assert pct.resolve_thresholds().tool_calls == pct.DEFAULT_TOOL_THRESHOLD


class TestFailOpen:
    """Fail-open behaviour on malformed or hostile input.

    Covers a missing session id counting under the default key, a garbage
    session id not crashing, a none payload counting under the default key, a
    corrupt state file degrading to zero, and the path-containment guard that
    keeps a crafted session id from escaping the state directory.
    """

    def test_missing_session_id_uses_default_key_and_counts(self) -> None:
        envelope = pct.evaluate({"tool_response": ""})
        assert envelope == {}
        path = pct.state_path_for(None)
        assert pct._read_state(path).tool_calls == 1

    def test_garbage_session_id_does_not_crash(self) -> None:
        # Non-string, path-traversal-shaped, and empty ids all sanitize safely.
        for bad in (12345, {"x": 1}, "../../etc/passwd", "   ", "////"):
            envelope = pct.evaluate(_payload(bad))
            assert envelope == {}

    def test_none_payload_counts_under_default_key(self) -> None:
        envelope = pct.evaluate(None)
        assert envelope == {}

    def test_corrupt_state_file_degrades_to_zero(self) -> None:
        path = pct.state_path_for("sess-1")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{ not json", encoding="utf-8")
        # A corrupt file is treated as zeroed counters; this call starts fresh.
        pct.evaluate(_payload())
        assert pct._read_state(path).tool_calls == 1

    def test_state_path_stays_inside_state_dir(self, tmp_path: Path) -> None:
        # A traversal-shaped id must not escape the state directory.
        resolved = pct.state_path_for("../../../escape").resolve()
        state_dir = (tmp_path / pct._STATE_DIRNAME).resolve()
        assert state_dir in resolved.parents


class TestAtomicWriteAndPurge:
    """Durability and cleanup of the on-disk counter state.

    Covers that the write is atomic and leaves no temporary residue, that the
    purge removes stale counter files and is a no-op on a missing directory, and
    that evaluation purges stale state as it runs.
    """

    def test_write_is_atomic_and_leaves_no_temp_residue(self) -> None:
        path = pct.state_path_for("sess-1")
        pct._write_state(path, pct.SessionState(tool_calls=4, output_bytes=99))
        assert pct._read_state(path).tool_calls == 4
        # No ``.tmp`` sibling residue after a successful atomic write.
        residue = list(path.parent.glob("*.tmp"))
        assert residue == []

    def test_purge_removes_stale_counter_files(self, tmp_path: Path) -> None:
        import os

        state_dir = pct._state_dir()
        state_dir.mkdir(parents=True, exist_ok=True)
        fresh = state_dir / "fresh.json"
        stale = state_dir / "stale.json"
        fresh.write_text("{}", encoding="utf-8")
        stale.write_text("{}", encoding="utf-8")
        # Age ``stale`` past the TTL; keep ``fresh`` recent.
        old = 1_000.0
        os.utime(stale, (old, old))
        pct._purge_stale_state(state_dir, now=old + pct._STATE_TTL_SECONDS + 10)
        assert not stale.exists()
        assert fresh.exists()

    def test_purge_missing_dir_is_noop(self, tmp_path: Path) -> None:
        # A purge against an absent directory never raises (fail-open).
        pct._purge_stale_state(tmp_path / "absent")

    def test_evaluate_purges_stale_state(self) -> None:
        import os

        state_dir = pct._state_dir()
        state_dir.mkdir(parents=True, exist_ok=True)
        stale = state_dir / "ended-session.json"
        stale.write_text("{}", encoding="utf-8")
        old = 1_000.0
        os.utime(stale, (old, old))
        # A live evaluate() sweeps ended-session files older than the TTL.
        # (mtime is far in the past relative to now, so it is well past TTL.)
        pct.evaluate(_payload("live-session"))
        assert not stale.exists()


class TestEstimateOutputBytes:
    """Measuring the size of a tool response.

    Covers a string response measured as UTF-8 bytes, a dict response measured
    after serialisation, and the two zero cases: an absent response and a none
    payload.
    """

    def test_string_response_measured_in_utf8_bytes(self) -> None:
        assert pct.estimate_output_bytes(_payload(output="abc")) == 3

    def test_dict_response_serialized(self) -> None:
        size = pct.estimate_output_bytes(_payload(output={"k": "v" * 50}))
        assert size > 50

    def test_absent_response_is_zero(self) -> None:
        assert pct.estimate_output_bytes({"session_id": "x"}) == 0

    def test_none_payload_is_zero(self) -> None:
        assert pct.estimate_output_bytes(None) == 0


class TestMain:
    """Process-level entry point behaviour.

    Covers the empty envelope below the threshold, the advisory at the
    threshold, and that a TTY stdin never raises — the hook must not crash when
    it is invoked outside a pipe.
    """

    def _feed_stdin(self, monkeypatch: pytest.MonkeyPatch, payload: object) -> None:
        stream = io.StringIO(json.dumps(payload))
        stream.isatty = lambda: False  # type: ignore[method-assign]
        monkeypatch.setattr(sys, "stdin", stream)

    def test_main_emits_empty_envelope_below_threshold(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._feed_stdin(monkeypatch, _payload())
        pct.main([])
        assert json.loads(capsys.readouterr().out) == {}

    def test_main_emits_advisory_at_threshold(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setenv(pct.TOOL_THRESHOLD_ENV, "1")
        self._feed_stdin(monkeypatch, _payload())
        pct.main([])
        envelope = json.loads(capsys.readouterr().out)
        assert "systemMessage" in envelope

    def test_main_never_raises_on_tty_stdin(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        stream = io.StringIO("")
        stream.isatty = lambda: True  # type: ignore[method-assign]
        monkeypatch.setattr(sys, "stdin", stream)
        pct.main([])
        assert json.loads(capsys.readouterr().out) == {}


class TestDispatchRouting:
    """Routing from the shared dispatcher into this tracker.

    Covers that the route predicate matches on the basename, that a
    post-tool-use event reaches the tracker, and that it stays silent below the
    threshold.
    """

    def _feed_stdin(self, monkeypatch: pytest.MonkeyPatch, payload: object) -> None:
        stream = io.StringIO(json.dumps(payload))
        stream.isatty = lambda: False  # type: ignore[method-assign]
        monkeypatch.setattr(sys, "stdin", stream)

    def test_route_predicate_matches_basename(self) -> None:
        assert dispatch._is_proactive_compaction_route(
            "posttooluse-proactive-compaction"
        )
        assert dispatch._is_proactive_compaction_route(
            "/abs/path/posttooluse-proactive-compaction.md"
        )
        assert not dispatch._is_proactive_compaction_route("precompact")
        assert not dispatch._is_proactive_compaction_route("")

    def test_dispatch_routes_posttooluse_to_tracker(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setenv(pct.TOOL_THRESHOLD_ENV, "1")
        self._feed_stdin(monkeypatch, _payload())
        dispatch.dispatch("PostToolUse", "posttooluse-proactive-compaction", False)
        envelope = json.loads(capsys.readouterr().out)
        assert "systemMessage" in envelope

    def test_dispatch_posttooluse_below_threshold_silent(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._feed_stdin(monkeypatch, _payload())
        dispatch.dispatch("PostToolUse", "posttooluse-proactive-compaction", False)
        assert json.loads(capsys.readouterr().out) == {}
