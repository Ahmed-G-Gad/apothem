# SPDX-License-Identifier: MIT

"""Unit tests for the ``chaos_pass`` envelope parsing helpers."""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_DEV = _REPO_ROOT / "scripts" / "dev"
if str(_SCRIPTS_DEV) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DEV))

from chaos_pass import (  # noqa: E402
    _extract_envelope,
    _is_gate_verdict,
    _is_valid_envelope,
)


def test_is_valid_envelope_accepts_hook_specific_output() -> None:
    assert _is_valid_envelope({"hookSpecificOutput": {"hookEventName": "X"}})


def test_is_gate_verdict_accepts_allow_and_block() -> None:
    """A conformity-gate report counts as a valid verdict on exit 0 and exit 2."""
    assert _is_gate_verdict({"orchestrator": "conformity-gate", "passed": True}, 0)
    assert _is_gate_verdict({"orchestrator": "conformity-gate", "passed": False}, 2)


def test_is_gate_verdict_rejects_other_exit_codes() -> None:
    """Exit codes other than allow (0) / block (2) are not gate verdicts."""
    envelope = {"orchestrator": "conformity-gate"}
    assert not _is_gate_verdict(envelope, 1)
    assert not _is_gate_verdict(envelope, 127)


def test_is_gate_verdict_rejects_non_gate_envelope() -> None:
    """A context-envelope or a None payload is not a gate verdict."""
    assert not _is_gate_verdict({"hookSpecificOutput": {}}, 0)
    assert not _is_gate_verdict({"orchestrator": "something-else"}, 0)
    assert not _is_gate_verdict(None, 0)


def test_is_valid_envelope_accepts_system_message() -> None:
    assert _is_valid_envelope({"systemMessage": "hello"})


def test_is_valid_envelope_rejects_foreign_keys() -> None:
    assert not _is_valid_envelope({"unrelated": True})


def test_is_valid_envelope_rejects_non_dict() -> None:
    assert not _is_valid_envelope(None)
    assert not _is_valid_envelope([])  # type: ignore[arg-type]
    assert not _is_valid_envelope("string")  # type: ignore[arg-type]


def test_extract_envelope_parses_clean_json() -> None:
    out = _extract_envelope('{"systemMessage": "ok"}')

    assert out == {"systemMessage": "ok"}


def test_extract_envelope_returns_none_for_empty() -> None:
    assert _extract_envelope("") is None
    assert _extract_envelope("   \n  ") is None


def test_extract_envelope_returns_none_for_plain_text() -> None:
    assert _extract_envelope("just a line of prose") is None


def test_extract_envelope_falls_back_on_prefixed_noise() -> None:
    noisy = 'WARN: preamble leaked\n{"systemMessage": "clean"}'

    out = _extract_envelope(noisy)

    assert out == {"systemMessage": "clean"}


def test_extract_envelope_falls_back_on_hook_specific_key() -> None:
    noisy = 'garbled prefix xyz {"hookSpecificOutput": {"hookEventName": "PreToolUse"}}'

    out = _extract_envelope(noisy)

    assert out is not None
    assert out["hookSpecificOutput"] == {"hookEventName": "PreToolUse"}


def test_extract_envelope_returns_none_when_json_is_malformed() -> None:
    assert _extract_envelope('{"systemMessage":') is None


def test_extract_envelope_ignores_non_dict_json() -> None:
    assert _extract_envelope("[1, 2, 3]") is None
    assert _extract_envelope('"just a string"') is None
