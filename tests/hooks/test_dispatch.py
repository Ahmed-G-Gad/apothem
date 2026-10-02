# SPDX-License-Identifier: MIT

"""Fail-open contract for the hook dispatcher (``hooks.dispatch``).

Harness deployments invoke the dispatcher as the single entry point for every
hook event. It must route each event to its handler and, on any fault — an
unknown event, a missing ``--event-name``, or an argument-parse error — convert
that fault to a structured failure envelope on stdout rather than raise into the
harness, so a dispatcher error surfaces as a message and never silently blocks
the tool call. These tests pin the argument parsing, the event routing, and the
fail-open envelope on both the rich and the stdlib-fallback stdout paths.
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


def _mock_tty_stdin(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace ``sys.stdin`` with an empty stream that reports as a TTY.

    Used by the SessionStart smoke tests so the hook code path treats
    stdin as terminal-attached (no JSON payload to parse) and skips the
    stdin-read branch deterministically.
    """
    stream = io.StringIO("")
    stream.isatty = lambda: True  # type: ignore[method-assign]
    monkeypatch.setattr(sys, "stdin", stream)


class TestParseArgs:
    """Command-line argument parsing.

    Covers the event name being required and the remaining defaults.
    """

    def test_event_name_required(self) -> None:
        with pytest.raises(SystemExit):
            dispatch.parse_args([])

    def test_defaults(self) -> None:
        args = dispatch.parse_args(["--event-name", "Stop"])

        assert args.event_name == "Stop"
        assert args.context_file == ""
        assert args.quiet is False


class TestDispatch:
    """Routing an event to its handler.

    Covers the two raising cases — an unknown event, and a non-session event
    arriving without context — against the envelope-emitting session events.
    """

    def test_unknown_event_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown event"):
            dispatch.dispatch("FakeEvent", "", False)

    def test_non_session_event_without_context_raises(self) -> None:
        with pytest.raises(ValueError, match="context-file required"):
            dispatch.dispatch("Stop", "", False)

    def test_session_start_emits_envelope(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _mock_tty_stdin(monkeypatch)

        dispatch.dispatch("SessionStart", "", False)

        envelope = json.loads(capsys.readouterr().out)
        assert envelope["hookSpecificOutput"]["hookEventName"] == "SessionStart"

    def test_stop_event_with_context_emits_envelope(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Stop still emits the Stop-shaped envelope carrying the message body.

        Stop routes through ``session_end_gate``, which is opt-in and rations the
        protocol to one emission per session, so the gate is enabled and the
        floor lowered to 1 to exercise the emitting path here; the rationing
        itself is covered in ``test_session_end_gate.py``. The per-user hook
        state directory is redirected at ``tmp_path`` so the latch written by
        this run never silences a later one.
        """
        import session_end_gate as seg
        import state_dir

        _mock_tty_stdin(monkeypatch)
        monkeypatch.setenv(state_dir.OVERRIDE_ENV, str(tmp_path / "state"))
        monkeypatch.setenv(seg.MIN_STOPS_ENV, "1")
        monkeypatch.setenv(seg.ENABLED_ENV, "1")
        ctx = tmp_path / "stop.md"
        ctx.write_text("Stop body.", encoding="utf-8")

        dispatch.dispatch("Stop", str(ctx), False)

        envelope = json.loads(capsys.readouterr().out)
        assert envelope["hookSpecificOutput"]["hookEventName"] == "Stop"
        assert "Stop body." in envelope["hookSpecificOutput"]["additionalContext"]


class TestMain:
    """Process-level entry point behaviour.

    Covers the fail-open contract: a failure envelope on an unknown event, a
    quiet session start, an envelope even when the event is missing, and
    recovery of the event name when argument parsing itself fails — so the
    dispatcher always emits valid output.
    """

    def test_main_emits_failure_envelope_on_unknown_event(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _mock_tty_stdin(monkeypatch)

        dispatch.main(["--event-name", "BogusEvent"])

        envelope = json.loads(capsys.readouterr().out)
        assert "Hook execution failure" in envelope["systemMessage"]

    def test_main_session_start_quiet(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _mock_tty_stdin(monkeypatch)

        dispatch.main(["--event-name", "SessionStart", "--quiet"])

        assert capsys.readouterr().out == ""

    def test_main_missing_event_emits_envelope(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _mock_tty_stdin(monkeypatch)

        # A malformed invocation (missing event) must NOT surface argparse's
        # non-zero SystemExit to the harness — main converts it to a valid
        # failure envelope on stdout and returns (process exits 0).
        dispatch.main([])

        envelope = json.loads(capsys.readouterr().out)
        assert envelope

    def test_main_recovers_event_name_on_argparse_error(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _mock_tty_stdin(monkeypatch)

        # A valid event positional plus an unrecognized flag makes argparse
        # exit non-zero before the event name is bound in the success path.
        # main must still name the event in the failure envelope rather than
        # losing it to "UnknownEvent".
        dispatch.main(["PreToolUse", "--no-such-flag"])

        envelope = json.loads(capsys.readouterr().out)
        assert envelope["hookSpecificOutput"]["hookEventName"] == "PreToolUse"


class TestEmitFailure:
    """``_emit_failure`` always writes one valid JSON envelope, never raises."""

    def test_rich_path_hookspecificoutput(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # emit_hook_context is importable here, so the rich writer is used.
        dispatch._emit_failure("PreToolUse", "boom")
        envelope = json.loads(capsys.readouterr().out)
        assert "failure: boom" in envelope["hookSpecificOutput"]["additionalContext"]
        assert envelope["hookSpecificOutput"]["hookEventName"] == "PreToolUse"

    def test_rich_path_systemmessage_event(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        dispatch._emit_failure("PreCompact", "boom")
        envelope = json.loads(capsys.readouterr().out)
        assert "failure: boom" in envelope["systemMessage"]

    def test_fallback_path_when_rich_writer_unimportable(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # Force ``from emit_hook_context import ...`` to fail so the self-
        # contained fallback envelope is exercised.
        monkeypatch.setitem(sys.modules, "emit_hook_context", None)
        dispatch._emit_failure("PreToolUse", "boom")
        out = capsys.readouterr().out
        assert out.count("\n") == 1
        envelope = json.loads(out)
        assert (
            envelope["hookSpecificOutput"]["additionalContext"]
            == "Hook bootstrap failure: boom"
        )

    def test_fallback_path_systemmessage_event(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setitem(sys.modules, "emit_hook_context", None)
        dispatch._emit_failure("PostCompact", "boom")
        envelope = json.loads(capsys.readouterr().out)
        assert envelope["systemMessage"] == "Hook bootstrap failure: boom"

    def test_fallback_path_is_valid_json_with_breaking_chars(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setitem(sys.modules, "emit_hook_context", None)
        nasty = 'broke on "{\\n}" \t control \x00'
        dispatch._emit_failure("PreToolUse", nasty)
        envelope = json.loads(capsys.readouterr().out)
        assert nasty in envelope["hookSpecificOutput"]["additionalContext"]
