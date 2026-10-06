# SPDX-License-Identifier: MIT

"""Tests for `hooks.askuserquestion_validator`.

Covers the call-time `(Recommended)`-marker validator: well-formed payloads
pass, lowercase / non-canonical / misplaced / double / destructive markers are
findings, the missing-marker nudge fires (never blocks), the strict opt-in
escalates well-formedness findings to a deny while leaving the nudge advisory,
and malformed input fails open.
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

import askuserquestion_validator as aqv  # noqa: E402
import dispatch  # noqa: E402


def _payload(*questions: dict[str, object]) -> dict[str, object]:
    """Wrap questions in the harness PreToolUse tool-input envelope."""
    return {
        "tool_name": "AskUserQuestion",
        "tool_input": {"questions": list(questions)},
    }


def _question(*labels: str, multi_select: bool = False) -> dict[str, object]:
    """Build one question dict from option labels."""
    return {
        "header": "Test",
        "question": "Which option?",
        "multiSelect": multi_select,
        "options": [{"label": lab} for lab in labels],
    }


def _kinds(result: aqv.ValidationResult) -> set[str]:
    return {f.kind for f in result.findings}


class TestWellFormed:
    """Option sets the validator accepts unchanged.

    Covers a single recommended marker, a zero-marker multi-select, a
    multi-select carrying several recommendations, and the single substantive
    option that draws no nudge because there is nothing to choose between.
    """

    def test_single_recommended_passes(self) -> None:
        result = aqv.validate_payload(
            _payload(_question("Accept (Recommended)", "Reject"))
        )
        assert result.findings == []

    def test_zero_marker_multiselect_passes(self) -> None:
        # multiSelect: true with no markers is compliant (no nudge, no finding).
        result = aqv.validate_payload(
            _payload(_question("A", "B", "C", multi_select=True))
        )
        assert result.findings == []

    def test_multiselect_multiple_recommended_passes(self) -> None:
        result = aqv.validate_payload(
            _payload(
                _question(
                    "Alpha (Recommended)",
                    "Beta (Recommended)",
                    "Gamma",
                    multi_select=True,
                )
            )
        )
        assert result.findings == []

    def test_single_substantive_option_no_nudge(self) -> None:
        # One substantive option + the implicit Other: no nudge (needs >= 2).
        result = aqv.validate_payload(_payload(_question("Proceed", "Other")))
        assert result.findings == []


class TestWellFormednessFindings:
    """Marker shapes the validator rejects.

    Covers the malformed marker spellings — lowercase, bracketed, abbreviated,
    and an extra internal space — plus the two semantic violations: a double
    marker on a single-select, and a marker on a destructive option.
    """

    def test_lowercase_marker_is_finding(self) -> None:
        result = aqv.validate_payload(
            _payload(_question("Accept (recommended)", "Reject"))
        )
        assert "non-canonical-postfix-case" in _kinds(result)
        assert result.wellformedness_findings

    def test_bracketed_marker_is_finding(self) -> None:
        result = aqv.validate_payload(
            _payload(_question("Accept [Recommended]", "Reject"))
        )
        assert "non-canonical-postfix-form" in _kinds(result)

    def test_abbreviated_marker_is_finding(self) -> None:
        result = aqv.validate_payload(_payload(_question("Accept (Rec)", "Reject")))
        assert "non-canonical-postfix-form" in _kinds(result)

    def test_double_marker_single_select_is_finding(self) -> None:
        result = aqv.validate_payload(
            _payload(_question("Accept (Recommended)", "Defer (Recommended)"))
        )
        assert "single-select-multi-recommended" in _kinds(result)

    def test_marker_on_destructive_is_finding(self) -> None:
        result = aqv.validate_payload(
            _payload(_question("Delete file (Recommended)", "Keep"))
        )
        assert "recommended-on-destructive" in _kinds(result)

    def test_extra_internal_space_is_not_canonical(self) -> None:
        # "( Recommended )" is a non-canonical tail form, not the canonical
        # " (Recommended)" postfix.
        result = aqv.validate_payload(
            _payload(_question("Accept ( Recommended )", "Reject"))
        )
        assert "non-canonical-postfix-form" in _kinds(result)


class TestNudge:
    """The advisory nudge toward naming a recommendation.

    Covers the two-option set with no marker drawing a nudge, and the implicit
    ``Other`` option being skipped so it never counts toward the choice.
    """

    def test_missing_marker_two_options_nudges(self) -> None:
        result = aqv.validate_payload(_payload(_question("Patch", "Rewrite")))
        assert "no-recommended-marker" in _kinds(result)
        assert result.nudges
        # The nudge is never a well-formedness finding.
        assert not result.wellformedness_findings

    def test_nudge_skips_implicit_other(self) -> None:
        # "Other" is the implicit escape hatch, not a substantive option; with
        # only one substantive option remaining, no nudge fires.
        result = aqv.validate_payload(_payload(_question("Proceed", "Other")))
        assert "no-recommended-marker" not in _kinds(result)


class TestEnvelope:
    """Shape of the emitted hook envelope.

    Covers the clean payload yielding an empty envelope, the advisory mode
    emitting additional context rather than blocking, strict mode denying on a
    well-formedness finding, and strict mode deliberately not blocking when only
    a nudge is present.
    """

    def test_clean_payload_empty_envelope(self) -> None:
        result = aqv.validate_payload(
            _payload(_question("Accept (Recommended)", "Reject"))
        )
        assert aqv.build_envelope(result, strict=False) == {}
        assert aqv.build_envelope(result, strict=True) == {}

    def test_advisory_emits_additional_context_not_block(self) -> None:
        result = aqv.validate_payload(
            _payload(_question("Accept (recommended)", "Reject"))
        )
        envelope = aqv.build_envelope(result, strict=False)
        specific = envelope["hookSpecificOutput"]
        assert specific["hookEventName"] == "PreToolUse"
        assert specific["additionalContext"]
        assert "permissionDecision" not in specific
        assert "decision" not in envelope

    def test_strict_blocks_wellformedness(self) -> None:
        result = aqv.validate_payload(
            _payload(_question("Accept (recommended)", "Reject"))
        )
        envelope = aqv.build_envelope(result, strict=True)
        specific = envelope["hookSpecificOutput"]
        assert specific["permissionDecision"] == "deny"
        assert "recommended" in specific["permissionDecisionReason"].lower()
        assert "decision" not in envelope

    def test_strict_does_not_block_nudge_only(self) -> None:
        # A pure-nudge result (missing marker) must NOT block even under strict.
        result = aqv.validate_payload(_payload(_question("Patch", "Rewrite")))
        envelope = aqv.build_envelope(result, strict=True)
        assert "decision" not in envelope
        specific = envelope["hookSpecificOutput"]
        assert "permissionDecision" not in specific
        assert specific["additionalContext"]


class TestStrictDetection:
    """Resolving the strict-versus-advisory posture.

    Covers both enabling routes — the flag and the environment variable —
    against the advisory default.
    """

    def test_strict_flag_enables(self) -> None:
        assert aqv.strict_enabled(["--strict"]) is True

    def test_strict_env_enables(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(aqv.STRICT_ENV, "1")
        assert aqv.strict_enabled([]) is True

    def test_default_is_advisory(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv(aqv.STRICT_ENV, raising=False)
        assert aqv.strict_enabled([]) is False


class TestFailOpen:
    """Fail-open behaviour on malformed input.

    Covers a none payload, a missing tool input, a non-list questions field, an
    option lacking a label, and garbage on stdin — each yielding an empty or
    allow result rather than raising, so a malformed payload never blocks the
    tool call.
    """

    def test_none_payload_empty_result(self) -> None:
        assert aqv.validate_payload(None).findings == []

    def test_missing_tool_input_empty_result(self) -> None:
        assert aqv.validate_payload({"tool_name": "AskUserQuestion"}).findings == []

    def test_questions_not_a_list_empty_result(self) -> None:
        payload = {"tool_input": {"questions": "not-a-list"}}
        assert aqv.validate_payload(payload).findings == []

    def test_option_without_label_tolerated(self) -> None:
        payload = {
            "tool_input": {
                "questions": [{"multiSelect": False, "options": [{}, {"label": "B"}]}]
            }
        }
        # Should not raise; one labelled option => no nudge (< 2 substantive).
        result = aqv.validate_payload(payload)
        assert isinstance(result, aqv.ValidationResult)

    def test_main_emits_allow_envelope_on_garbage_stdin(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        stream = io.StringIO("not json {{{")
        stream.isatty = lambda: False  # type: ignore[method-assign]
        monkeypatch.setattr(sys, "stdin", stream)
        aqv.main([])
        envelope = json.loads(capsys.readouterr().out)
        # Unparseable payload => empty (allow) envelope, never a crash.
        assert envelope == {}


class TestMainStdin:
    """Process-level entry point behaviour over stdin.

    Covers the advisory additional context and the strict deny.
    """

    @staticmethod
    def _feed_stdin(
        monkeypatch: pytest.MonkeyPatch, payload: dict[str, object]
    ) -> None:
        stream = io.StringIO(json.dumps(payload))
        stream.isatty = lambda: False  # type: ignore[method-assign]
        monkeypatch.setattr(sys, "stdin", stream)

    def test_main_advisory_additional_context(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.delenv(aqv.STRICT_ENV, raising=False)
        self._feed_stdin(
            monkeypatch, _payload(_question("Accept (recommended)", "Reject"))
        )
        aqv.main([])
        envelope = json.loads(capsys.readouterr().out)
        assert envelope["hookSpecificOutput"]["additionalContext"]

    def test_main_strict_block(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._feed_stdin(
            monkeypatch, _payload(_question("Accept (recommended)", "Reject"))
        )
        aqv.main(["--strict"])
        envelope = json.loads(capsys.readouterr().out)
        assert envelope["hookSpecificOutput"]["permissionDecision"] == "deny"


class TestDispatchRouting:
    """Routing from the shared dispatcher into this validator.

    Covers that the route predicate matches on the basename and rejects other
    events, that the question event reaches the validator, and that a clean
    payload yields an empty envelope.
    """

    def test_route_predicate_matches_basename(self) -> None:
        assert dispatch._is_askuserquestion_route(
            "pretooluse-askuserquestion-recommended"
        )
        assert dispatch._is_askuserquestion_route(
            "/abs/path/pretooluse-askuserquestion-recommended.md"
        )

    def test_route_predicate_rejects_other(self) -> None:
        assert not dispatch._is_askuserquestion_route("pretooluse-write")
        assert not dispatch._is_askuserquestion_route("")

    def test_dispatch_routes_askuserquestion(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.delenv(aqv.STRICT_ENV, raising=False)
        stream = io.StringIO(
            json.dumps(_payload(_question("Accept (recommended)", "Reject")))
        )
        stream.isatty = lambda: False  # type: ignore[method-assign]
        monkeypatch.setattr(sys, "stdin", stream)
        dispatch.dispatch("PreToolUse", "pretooluse-askuserquestion-recommended", False)
        envelope = json.loads(capsys.readouterr().out)
        assert envelope["hookSpecificOutput"]["additionalContext"]

    def test_dispatch_clean_payload_empty_envelope(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        stream = io.StringIO(
            json.dumps(_payload(_question("Accept (Recommended)", "Reject")))
        )
        stream.isatty = lambda: False  # type: ignore[method-assign]
        monkeypatch.setattr(sys, "stdin", stream)
        dispatch.dispatch("PreToolUse", "pretooluse-askuserquestion-recommended", False)
        envelope = json.loads(capsys.readouterr().out)
        assert envelope == {}
