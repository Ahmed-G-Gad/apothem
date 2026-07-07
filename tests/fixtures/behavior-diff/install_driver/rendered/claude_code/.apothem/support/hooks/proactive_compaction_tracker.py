# SPDX-License-Identifier: MIT

"""PostToolUse handler that mechanically operationalizes the CM-19 proactive-
compaction triggers.

Why this handler exists. The compaction-trigger catalog
(``rules/context-management-protocol.md`` §2 — ~18 tool calls since the last
externalization, a large cumulative emission, a heavy-read run) was
agent-discipline only: nothing *measured* per-session activity, so the
"compact before context fills" advisory fired solely on the agent's own
vigilance. The harness ``PreCompact`` event fires only once compaction has
already been initiated — too late to be proactive. This module is the
dispatch-routed ``PostToolUse`` handler that closes that gap: it keys off the
``session_id`` in the hook stdin payload, maintains a tiny per-session counter
file, and once a threshold from the §2 catalog is crossed it surfaces a concise
proactive-compaction advisory (externalize state + compact now) and then resets
the counter so the advisory does not fire on every subsequent tool call.

What it guarantees.

* **Advisory-only.** It NEVER blocks. A PostToolUse hook cannot block the tool
  call that already ran; the envelope only ever carries a ``systemMessage`` plus
  ``additionalContext`` nudge, or is empty.
* **Fast.** A single small-file read + write (a JSON counter object keyed by
  session id). No project scan, no engine import on the hot path.
* **Fail-open.** Any exception -> emit nothing (an empty envelope), never
  disrupt the session. A tracker bug must never cost the operator a tool call.
* **Low-noise / anti-spam.** It emits at most once per threshold window: when a
  threshold crosses, the per-session counters reset (back-off), so the next
  advisory is at least another full window away.

Configuration. Two thresholds, each overridable by an environment variable
(falling back to a default grounded in the §2 catalog):

* ``APOTHEM_PROACTIVE_COMPACTION_TOOL_THRESHOLD`` (default ``18``) — tool calls
  since the last advisory; mirrors the §2 "~18 tool calls" trigger.
* ``APOTHEM_PROACTIVE_COMPACTION_OUTPUT_THRESHOLD`` (default ``20000``) —
  cumulative tool-output bytes since the last advisory; a mechanical proxy for
  the §2 "large cumulative emission" / heavy-read triggers (~20 KB ≈ the
  500-line emission band the catalog names).

A non-positive or unparseable override falls back to the default, so a typo in
the environment can never disable or zero-out the tracker silently.
"""

from __future__ import annotations

import contextlib
import json
import os
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Final

#: Environment overrides for the two thresholds. Each falls back to its default
#: when unset, non-numeric, or non-positive.
TOOL_THRESHOLD_ENV: Final[str] = "APOTHEM_PROACTIVE_COMPACTION_TOOL_THRESHOLD"
OUTPUT_THRESHOLD_ENV: Final[str] = "APOTHEM_PROACTIVE_COMPACTION_OUTPUT_THRESHOLD"

#: Default thresholds, grounded in the §2 compaction-trigger catalog.
#: ``18`` mirrors the "~18 tool calls" trigger; ``20000`` bytes is a mechanical
#: proxy for the "500-line emission" / heavy-read band (~20 KB).
DEFAULT_TOOL_THRESHOLD: Final[int] = 18
DEFAULT_OUTPUT_THRESHOLD: Final[int] = 20_000

#: Minimum number of tool calls that must accumulate before the cumulative-output
#: threshold may fire. Without this floor a single tool output at or above the
#: output threshold would cross on its very next call, so N consecutive large
#: outputs each raise their own advisory — defeating the once-per-window back-off.
#: The floor makes the output threshold mean "a large emission spread across a
#: run", not "one big response". A window's first large output still counts, but
#: it cannot trigger until at least this many calls have accrued since the last
#: advisory.
_MIN_CALLS_FOR_OUTPUT_TRIGGER: Final[int] = 3

#: Per-session state lives under a dedicated subdirectory of the OS temp dir —
#: never inside the repository's tracked tree (the hook runs in the operator's
#: harness, not the checkout). The subdirectory keeps the counter files grouped
#: and easy to purge.
_STATE_DIRNAME: Final[str] = "apothem-proactive-compaction"

#: Age past which a per-session counter file is considered stale and purged on
#: the next write. A session's counters are only meaningful within one live
#: session; a file untouched for this long belongs to an ended session and would
#: otherwise accumulate in $TMP unbounded. 24 hours is far longer than any live
#: session yet bounds the directory's growth. Purge is best-effort: a failure to
#: remove a stale file never disturbs the tracker (fail-open).
_STATE_TTL_SECONDS: Final[float] = 24 * 60 * 60

#: Sanitized fallback when a session id is absent or unusable. A shared key is
#: acceptable here: the tracker is advisory, and a missing id only means the
#: counters are not partitioned per session for that (rare) case.
_DEFAULT_SESSION_KEY: Final[str] = "_default"


@dataclass(frozen=True)
class Thresholds:
    """Resolved tool-call and output-byte thresholds for one invocation."""

    tool_calls: int
    output_bytes: int


@dataclass
class SessionState:
    """Mutable per-session counters since the last advisory.

    ``tool_calls`` counts PostToolUse firings; ``output_bytes`` accumulates the
    estimated size of each tool's output. Both reset to zero when an advisory
    fires (the anti-spam back-off).
    """

    tool_calls: int = 0
    output_bytes: int = 0

    def to_dict(self) -> dict[str, int]:
        """Serialize to the on-disk JSON shape."""
        return {"tool_calls": self.tool_calls, "output_bytes": self.output_bytes}

    @classmethod
    def from_obj(cls, obj: object) -> SessionState:
        """Reconstruct from a parsed JSON object, tolerating shape drift.

        A garbage or partial object yields zeroed counters (fail-open): a
        corrupt state file degrades to "start counting again", never a crash.
        """
        if not isinstance(obj, dict):
            return cls()
        tool_calls = obj.get("tool_calls")
        output_bytes = obj.get("output_bytes")
        return cls(
            tool_calls=tool_calls
            if isinstance(tool_calls, int) and tool_calls >= 0
            else 0,
            output_bytes=(
                output_bytes
                if isinstance(output_bytes, int) and output_bytes >= 0
                else 0
            ),
        )


def _positive_int_env(name: str, default: int) -> int:
    """Return a positive integer from environment variable *name*, else *default*.

    A non-positive or unparseable value falls back to *default* so a typo can
    never silently disable or zero-out the threshold.
    """
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def resolve_thresholds() -> Thresholds:
    """Resolve both thresholds from the environment with grounded defaults."""
    return Thresholds(
        tool_calls=_positive_int_env(TOOL_THRESHOLD_ENV, DEFAULT_TOOL_THRESHOLD),
        output_bytes=_positive_int_env(OUTPUT_THRESHOLD_ENV, DEFAULT_OUTPUT_THRESHOLD),
    )


def _sanitize_session_key(session_id: object) -> str:
    """Map an arbitrary session id to a safe, bounded filename stem.

    Keeps only ``[A-Za-z0-9._-]`` (path-traversal-safe), bounds the length, and
    falls back to a shared default key when the id is absent, non-string, or
    sanitizes to empty. This guarantees the state path stays inside the state
    directory regardless of payload contents.
    """
    if not isinstance(session_id, str) or not session_id.strip():
        return _DEFAULT_SESSION_KEY
    allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
    cleaned = "".join(ch for ch in session_id if ch in allowed)
    cleaned = cleaned.strip("._-")
    if not cleaned:
        return _DEFAULT_SESSION_KEY
    return cleaned[:120]


def _state_dir() -> Path:
    """Return the per-session state directory under the OS temp dir."""
    return Path(tempfile.gettempdir()) / _STATE_DIRNAME


def state_path_for(session_id: object) -> Path:
    """Return the counter-file path for *session_id* (never inside the repo)."""
    return _state_dir() / f"{_sanitize_session_key(session_id)}.json"


def _read_state(path: Path) -> SessionState:
    """Load per-session counters from *path*, fail-open to zero on any error."""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return SessionState()
    try:
        return SessionState.from_obj(json.loads(raw))
    except (json.JSONDecodeError, ValueError):
        return SessionState()


def _write_state(path: Path, state: SessionState) -> None:
    """Persist per-session counters to *path* atomically, creating the dir.

    Writes to a sibling temp file and renames it over *path* in one atomic
    ``os.replace`` (mirroring ``apothem.lib.atomic_io`` inline, since this
    standalone hook ships without the ``apothem`` package on plugin-alone
    installs). A crash mid-write leaves the prior counter file intact — never a
    truncated JSON blob that ``_read_state`` would silently treat as zeroed and
    that would reset the window under the operator.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(state.to_dict(), separators=(",", ":")) + "\n").encode(
        "utf-8"
    )
    handle, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(handle, "wb") as tmp_file:
            tmp_file.write(payload)
            tmp_file.flush()
            os.fsync(tmp_file.fileno())
        os.replace(tmp_path, path)  # noqa: PTH105 — same-filesystem atomic rename
    finally:
        with contextlib.suppress(FileNotFoundError):
            tmp_path.unlink()


def _purge_stale_state(state_dir: Path, *, now: float | None = None) -> None:
    """Remove counter files untouched for longer than ``_STATE_TTL_SECONDS``.

    Best-effort and fail-open: every filesystem error is suppressed, so a purge
    failure never disturbs the advisory. Bounds the state directory's growth so
    an ended session's counter file does not accumulate in $TMP unbounded.
    """
    cutoff = (time.time() if now is None else now) - _STATE_TTL_SECONDS
    try:
        entries = list(state_dir.glob("*.json"))
    except OSError:
        return
    for entry in entries:
        with contextlib.suppress(OSError):
            if entry.stat().st_mtime < cutoff:
                entry.unlink()


def estimate_output_bytes(payload: dict[str, object] | None) -> int:
    """Estimate the byte size of a PostToolUse tool result from the payload.

    The harness PostToolUse stdin carries ``tool_response`` (the tool's output).
    Its shape varies by tool, so the estimate serializes whatever is present to
    a JSON string and measures its UTF-8 length — a stable, tool-agnostic proxy
    for "how much did this tool emit". An absent or unserializable response
    contributes zero (fail-open).
    """
    if not payload:
        return 0
    response = payload.get("tool_response")
    if response is None:
        return 0
    try:
        if isinstance(response, str):
            text = response
        else:
            text = json.dumps(response, separators=(",", ":"), default=str)
    except (TypeError, ValueError):
        return 0
    return len(text.encode("utf-8"))


def _advisory_text() -> str:
    """Return the proactive-compaction advisory body."""
    return (
        "Apothem proactive-compaction advisory (CM-19): activity since the last "
        "checkpoint has crossed a context-rot threshold. Externalize in-conversation "
        "state to durable files now, then compact:\n"
        "  1. Update the PROGRESS.md Resumption Contract (phase, task, next action, "
        "convention anchors, critical-files manifest); record session decisions in "
        "PLAN-NOTES.md. With no active suite, externalize to a scratch file under the "
        "active harness's config root.\n"
        "  2. Compact (or start a fresh session) so context stays lean per the "
        "blind-execution invariant — every turn must remain executable from durable "
        "files alone.\n"
        "This is advisory; it does not block. The counter has reset, so the next "
        "advisory is at least another full window away."
    )


def build_envelope(state: SessionState, thresholds: Thresholds) -> dict[str, object]:
    """Map current counters to a hook-output envelope.

    Returns the advisory envelope when either threshold is crossed (the caller
    has already reset the counters on the crossing path), or an empty envelope
    when below both thresholds (the silent, low-noise default).

    The output threshold is additionally gated on the tool-call floor
    (``_MIN_CALLS_FOR_OUTPUT_TRIGGER``): a single large tool response cannot
    cross on its own next call, so N consecutive large outputs raise at most one
    advisory per window rather than one per output. The tool-call threshold is
    unaffected — it already implies a multi-call window.
    """
    output_crossed = (
        state.output_bytes >= thresholds.output_bytes
        and state.tool_calls >= _MIN_CALLS_FOR_OUTPUT_TRIGGER
    )
    crossed = state.tool_calls >= thresholds.tool_calls or output_crossed
    if not crossed:
        return {}
    text = _advisory_text()
    return {
        "systemMessage": text,
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": text,
        },
    }


def _read_payload() -> dict[str, object] | None:
    """Read and parse the hook's stdin JSON payload, fail-open on any error."""
    try:
        if sys.stdin.isatty():
            return None
        raw = sys.stdin.read()
    except OSError:
        return None
    if not raw or not raw.strip():
        return None
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return None
    return parsed if isinstance(parsed, dict) else None


def evaluate(payload: dict[str, object] | None) -> dict[str, object]:
    """Increment the per-session counters and return the advisory envelope.

    Pre-condition: *payload* is the harness PostToolUse stdin object (or
    ``None``). Post-condition: the per-session counter file reflects this tool
    call; when a threshold crosses, the counters are reset to zero and the
    advisory envelope is returned; otherwise an empty envelope is returned and
    the counters carry forward.
    """
    session_id = payload.get("session_id") if isinstance(payload, dict) else None
    path = state_path_for(session_id)
    thresholds = resolve_thresholds()

    # Bound $TMP growth: sweep counter files from ended sessions before writing
    # this session's. Best-effort — a purge failure never disturbs the advisory.
    _purge_stale_state(path.parent)

    state = _read_state(path)
    state.tool_calls += 1
    state.output_bytes += estimate_output_bytes(payload)

    envelope = build_envelope(state, thresholds)
    if envelope:
        # Threshold crossed: reset the window so the advisory does not fire on
        # the next tool call (anti-spam back-off).
        _write_state(path, SessionState())
    else:
        _write_state(path, state)
    return envelope


def main(argv: list[str] | None = None) -> None:
    """Entry point. Tracks activity and emits one envelope; never raises.

    The ``argv`` parameter is accepted for signature parity with the sibling
    dispatch handlers (the dispatcher calls ``main([])``); this handler reads no
    flags, so it is intentionally unused.

    FAIL-OPEN: any unexpected exception is swallowed and an empty (no-op)
    envelope is written, so a tracker bug never disrupts the session.
    """
    try:
        payload = _read_payload()
        envelope = evaluate(payload)
        sys.stdout.write(json.dumps(envelope, separators=(",", ":")) + "\n")
    except Exception:  # noqa: BLE001, RUF100 - fail-open boundary: a tracker error must never disrupt the session; emit an empty envelope and proceed (BLE001 is the intent marker; RUF100 self-suppresses because ruff's BLE family is not active)
        sys.stdout.write("{}\n")


if __name__ == "__main__":
    main()
