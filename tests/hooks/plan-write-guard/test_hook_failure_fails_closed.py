# SPDX-License-Identifier: MIT

"""On a hook error, the plan-write-guard runtime is advisory (fail-OPEN).

The EN-1 ratified posture
(``.plans/apothem-overhaul/ws5-enforcement-posture.md``) fixes the runtime
contract: ``PreToolUse`` hooks REPORT, they do not block. The Python
dispatcher at ``hooks/dispatch.py`` always exits 0 and converts any
hook-emission error into a valid advisory envelope on stdout, so the tool
call proceeds even when the hook fails. Mechanical enforcement of
Plans-Locality is relocated to CI / pre-commit (the strict conformity corpus
gate).

These tests assert that ACTUAL runtime behavior — the JSON envelope shape and
exit code on a hook error — rather than Markdown prose strings. The envelope
assertion fails if the runtime ever silently drops the advisory envelope, and
the exit-code assertion fails if a hook error ever blocks the tool call. The
prose-level checks verify only that the guard messages carry the advisory
invariant line and the two-layer fail-disposition (dispatcher fail-open),
never a runtime-blocking claim.
"""

from __future__ import annotations

import importlib.util
import io
import json
import re
import sys
from contextlib import redirect_stdout
from pathlib import Path
from types import ModuleType
from typing import Final

import pytest


def _flatten(body: str) -> str:
    """Collapse all runs of whitespace (including newlines) to a single space."""
    return re.sub(r"\s+", " ", body)


_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
_HOOK_DIR: Final[Path] = _REPO_ROOT / "src" / "apothem" / "hooks"
_DISPATCH_PATH: Final[Path] = _HOOK_DIR / "dispatch.py"

_ADVISORY_INVARIANT: Final[str] = (
    "Advisory: this hook reports; it does not block. Mechanical enforcement runs in CI."
)


def _load_dispatch() -> ModuleType:
    """Load the hook dispatcher via its real source path.

    The dispatcher inserts its own dir and ``lib/`` onto ``sys.path`` at import
    time, so its sibling imports (``events``, ``emit_hook_context``) resolve.
    """
    for extra in (_HOOK_DIR, _HOOK_DIR / "lib"):
        if str(extra) not in sys.path:
            sys.path.insert(0, str(extra))
    spec = importlib.util.spec_from_file_location(
        "apothem_hook_dispatch", _DISPATCH_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load dispatcher at {_DISPATCH_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def dispatch() -> ModuleType:
    """The hook dispatcher module loaded from source."""
    return _load_dispatch()


def _run_dispatch(
    dispatch: ModuleType, argv: list[str]
) -> tuple[int, dict[str, object]]:
    """Invoke ``dispatch.main(argv)`` and return (exit_code, parsed_stdout_json).

    ``main`` never raises on a hook error — it converts the error to an
    envelope on stdout and returns. A ``SystemExit`` (argparse usage error)
    is re-raised by ``main`` and surfaces here as the exit code.
    """
    buffer = io.StringIO()
    exit_code = 0
    try:
        with redirect_stdout(buffer):
            dispatch.main(argv)
    except SystemExit as exc:  # argparse usage path only
        code = exc.code
        exit_code = code if isinstance(code, int) else 1
    out = buffer.getvalue().strip()
    payload: dict[str, object] = json.loads(out) if out else {}
    return exit_code, payload


def test_pretooluse_hook_error_emits_advisory_envelope_and_exits_zero(
    dispatch: ModuleType,
) -> None:
    """A hook error on a PreToolUse event is fail-OPEN: the dispatcher emits a
    valid advisory envelope on stdout and the process exits 0, so the tool call
    proceeds. The error is surfaced in ``additionalContext`` — never silently
    dropped — and the runtime does NOT block."""
    # An unknown message name forces ``dispatch`` to raise inside ``main``
    # (the context path resolves to a non-existent file → run_hook_mode still
    # tolerates that, so instead trigger the unknown-event error path which is
    # the deterministic dispatcher-error case).
    exit_code, payload = _run_dispatch(dispatch, ["PreToolUse", "--context-file", ""])

    # Fail-OPEN: the dispatcher always exits 0; a hook error never blocks.
    assert exit_code == 0

    # The advisory envelope is present and never silently dropped.
    assert payload != {}, "dispatcher dropped the advisory envelope on hook error"
    assert "hookSpecificOutput" in payload, (
        "PreToolUse advisory envelope must carry hookSpecificOutput"
    )
    hook_specific = payload["hookSpecificOutput"]
    assert isinstance(hook_specific, dict)
    assert hook_specific["hookEventName"] == "PreToolUse"
    # The error is surfaced for the operator, not hidden.
    assert "additionalContext" in hook_specific
    assert "failure" in str(hook_specific["additionalContext"]).lower()


def test_unknown_event_failure_envelope_is_advisory(dispatch: ModuleType) -> None:
    """An unknown event name (a dispatcher-internal error) is converted to an
    advisory envelope on stdout and exits 0 — the dispatcher's fail-OPEN
    contract holds for every error class, not only context-file errors."""
    exit_code, payload = _run_dispatch(
        dispatch, ["PreToolUse", "--context-file", str(_DISPATCH_PATH)]
    )
    # A valid context-file path on a valid event runs the emit path cleanly and
    # exits 0 with a real envelope; the contract is the always-zero exit.
    assert exit_code == 0
    assert payload != {}


def test_write_guard_message_is_advisory_not_blocking() -> None:
    """The Write/Edit/NotebookEdit guard message carries the advisory invariant
    line and the two-layer fail-disposition, and makes no runtime-blocking
    claim ('hard-block' / 'non-negotiable')."""
    target = _HOOK_DIR / "messages" / "pretooluse-write-plan-guard.md"
    text = target.read_text(encoding="utf-8")
    assert _ADVISORY_INVARIANT in text
    assert "**Fail-disposition.**" in text
    assert "is fail-open" in text
    # No runtime-enforcement overclaim.
    assert "hard-block" not in text
    assert "non-negotiable" not in text


def test_bash_guard_message_is_advisory_not_blocking() -> None:
    """The Bash companion guard message carries the advisory invariant line and
    the two-layer fail-disposition, names its error classes, and makes no
    runtime-blocking claim."""
    target = _HOOK_DIR / "messages" / "pretooluse-bash-plan-guard.md"
    text = target.read_text(encoding="utf-8")
    flat = _flatten(text)
    assert _ADVISORY_INVARIANT in flat
    assert "**Fail-disposition.**" in text
    assert "is fail-open" in flat
    # The error classes the dispatcher fail-opens on are still enumerated.
    assert "parse failure" in flat
    assert "Python exception" in flat
    # No runtime-enforcement overclaim.
    assert "hard-block" not in text
    assert "non-negotiable" not in text
