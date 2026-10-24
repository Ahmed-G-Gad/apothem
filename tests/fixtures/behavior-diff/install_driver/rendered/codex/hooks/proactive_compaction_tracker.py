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

Signal. The primary signal is the measured context size: the newest assistant
``usage`` record in the transcript tail (input + cache-read + cache-creation
tokens). With ``APOTHEM_CONTEXT_WINDOW_TOKENS`` (or Claude Code's
``CLAUDE_CODE_AUTO_COMPACT_WINDOW``) set, the tracker asks the agent to save
state at 50% of the window and to compact at 75%; without a known window it uses
120K and 250K tokens. A sharp drop in the measured size marks a compaction and
restarts the two-advisory budget. Claude Code runs this hook in the background
(``async``), so it never delays a tool result.

Fallback. When no context size is measurable (a harness without a transcript,
or no usage record yet) the tracker counts activity instead, with two
thresholds, each overridable by an environment variable (falling back to a
default grounded in the §2 catalog):

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

_LIB_DIR: Final[Path] = Path(__file__).resolve().parent / "lib"
if str(_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(_LIB_DIR))

from state_dir import hook_state_dir, session_key  # noqa: E402

#: Environment overrides for the two thresholds. Each falls back to its default
#: when unset, non-numeric, or non-positive.
TOOL_THRESHOLD_ENV: Final[str] = "APOTHEM_PROACTIVE_COMPACTION_TOOL_THRESHOLD"
#: On/off switch for the whole tracker. Default on; ``0``, ``false``, ``no`` or
#: ``off`` (case-folded) silence it without editing installed hook configuration.
ENABLED_ENV: Final[str] = "APOTHEM_PROACTIVE_COMPACTION_ENABLED"
_DISABLED_VALUES: Final[frozenset[str]] = frozenset({"0", "false", "no", "off"})
#: Advisories allowed per compaction cycle (per session when the context size is
#: not measurable). Without a cap the tracker re-fires for the life of the
#: session and has no fixed point: complying (writing PROGRESS.md) does not
#: change what it asserts next time. Two advisories ("save state", then "compact
#: now") bound the cost; a measured compaction restarts the budget.
MAX_ADVISORIES_PER_SESSION: Final[int] = 2
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

#: Per-session state lives in the per-user hook state directory
#: (``hooks/lib/state_dir.py``): never inside a checkout, never in a directory
#: shared by every user on the host.
_STATE_DIRNAME: Final[str] = "proactive-compaction"

#: Age past which a per-session counter file is considered stale and purged on
#: the next write. A session's counters are only meaningful within one live
#: session; a file untouched for this long belongs to an ended session and would
#: otherwise accumulate unbounded. 24 hours is far longer than any live
#: session yet bounds the directory's growth. Purge is best-effort: a failure to
#: remove a stale file never disturbs the tracker (fail-open).
_STATE_TTL_SECONDS: Final[float] = 24 * 60 * 60


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
    fires (the anti-spam back-off). ``context_tokens`` is the last measured
    context size (0 when unmeasured); a sharp drop marks a compaction.
    """

    tool_calls: int = 0
    output_bytes: int = 0
    advisories: int = 0
    context_tokens: int = 0

    def to_dict(self) -> dict[str, int]:
        """Serialize to the on-disk JSON shape."""
        return {
            "tool_calls": self.tool_calls,
            "output_bytes": self.output_bytes,
            "advisories": self.advisories,
            "context_tokens": self.context_tokens,
        }

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
        advisories = obj.get("advisories")
        context_tokens = obj.get("context_tokens")
        return cls(
            context_tokens=context_tokens
            if isinstance(context_tokens, int) and context_tokens >= 0
            else 0,
            advisories=advisories
            if isinstance(advisories, int) and advisories >= 0
            else 0,
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


def is_enabled() -> bool:
    """Return False when :data:`ENABLED_ENV` reads as an explicit "off" value."""
    raw = os.environ.get(ENABLED_ENV, "").strip().casefold()
    return raw not in _DISABLED_VALUES if raw else True


def state_path_for(session_id: object) -> Path:
    """Return the counter-file path for *session_id* (per-user, never in a checkout)."""
    return hook_state_dir(_STATE_DIRNAME) / f"{session_key(session_id)}.json"


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
    an ended session's counter file does not accumulate unbounded.
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


#: How much of the transcript's end is scanned for the latest usage record. One
#: assistant line is a few KB; the tail covers many turns while keeping the read
#: constant-time however long the session grows.
_TRANSCRIPT_TAIL_BYTES: Final[int] = 256 * 1024
#: Usage fields whose sum is the prompt the model last saw: the context size.
_CONTEXT_USAGE_FIELDS: Final[tuple[str, ...]] = (
    "input_tokens",
    "cache_read_input_tokens",
    "cache_creation_input_tokens",
)
#: Context-window size override, in tokens. Falls back to Claude Code's own
#: auto-compact window variable when that is set; otherwise the window is unknown
#: and the policy decides on absolute size alone.
CONTEXT_WINDOW_ENV: Final[str] = "APOTHEM_CONTEXT_WINDOW_TOKENS"
_HARNESS_WINDOW_ENV: Final[str] = "CLAUDE_CODE_AUTO_COMPACT_WINDOW"
#: A measured context below this share of the last one means the conversation
#: was compacted (or cleared): the advisory budget starts over.
_COMPACTION_DROP_RATIO: Final[float] = 0.5
#: Context-fill policy (the maintainer's choice). With a known window: save state
#: at half full, compact at three quarters. Without one, absolute sizes: quality
#: degrades with prompt length whatever the window, and 120K / 250K tokens sit
#: below the auto-compaction point of the common 200K window and well inside a
#: 1M one.
_SAVE_STATE_FRACTION: Final[float] = 0.50
_COMPACT_NOW_FRACTION: Final[float] = 0.75
_SAVE_STATE_TOKENS: Final[int] = 120_000
_COMPACT_NOW_TOKENS: Final[int] = 250_000


def context_tokens(payload: dict[str, object] | None) -> int | None:
    """Return the session's current context size in tokens, or ``None``.

    Reads the newest main-thread assistant ``usage`` record from the tail of the
    payload's ``transcript_path``: input plus cache-read plus cache-creation
    tokens is exactly the prompt the model last received. A harness without a
    transcript, a transcript with no usage yet, or any read error yields
    ``None`` and the caller falls back to activity counting.
    """
    path = payload.get("transcript_path") if payload else None
    if not isinstance(path, str) or not path:
        return None
    try:
        with open(path, "rb") as handle:  # noqa: PTH123 - binary tail read
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - _TRANSCRIPT_TAIL_BYTES))
            tail = handle.read()
    except OSError:
        return None
    for line in reversed(tail.splitlines()):
        if b'"usage"' not in line or b'"isSidechain":true' in line:
            continue
        try:
            record = json.loads(line)
        except ValueError:
            continue  # the first line of the tail is usually cut mid-record
        message = record.get("message") if isinstance(record, dict) else None
        usage = message.get("usage") if isinstance(message, dict) else None
        if not isinstance(usage, dict):
            continue
        total = sum(
            value
            for field in _CONTEXT_USAGE_FIELDS
            if isinstance(value := usage.get(field), int)
        )
        if total > 0:
            return total
    return None


def context_window() -> int | None:
    """Return the context-window size from the environment, or ``None``."""
    for name in (CONTEXT_WINDOW_ENV, _HARNESS_WINDOW_ENV):
        value = _positive_int_env(name, 0)
        if value > 0:
            return value
    return None


def advisory_level(tokens: int, window: int | None, advisories_sent: int) -> int | None:
    """Decide whether this tool call should raise a context advisory.

    Args:
        tokens: The measured context size in tokens (always > 0 here).
        window: The context-window size in tokens, or ``None`` when unknown.
        advisories_sent: Advisories already raised since the last compaction
            (0 or 1; the caller stops calling after
            ``MAX_ADVISORIES_PER_SESSION``).

    Returns:
        The 1-based advisory to raise now (1 = "externalize state",
        2 = "compact now"), or ``None`` to stay silent.
    """
    if window:
        compact_now = tokens >= window * _COMPACT_NOW_FRACTION
        save_state = tokens >= window * _SAVE_STATE_FRACTION
    else:
        compact_now = tokens >= _COMPACT_NOW_TOKENS
        save_state = tokens >= _SAVE_STATE_TOKENS
    # A session resumed already large may skip straight to level 2.
    if compact_now:
        return 2
    if save_state and advisories_sent == 0:
        return 1
    return None


def _advisory_text(
    level: int = 1, tokens: int | None = None, window: int | None = None
) -> str:
    """Return the model-facing advisory: the step the model can take itself."""
    if tokens is None:
        measured = "Activity since the last checkpoint is high"
    elif window:
        measured = f"Context is about {tokens:,} tokens ({tokens * 100 // window}% of the window)"
    else:
        measured = f"Context is about {tokens:,} tokens"
    # The model is told only what it can do itself; compacting the conversation
    # is the operator's action and lives in the operator note.
    urgency = (
        " Do this before the next step: the operator has been told the session is long."
        if level >= 2
        else ""
    )
    return (
        f"Apothem proactive-compaction advisory: {measured}. Externalize "
        "in-conversation state to durable files now: update the active plan's "
        "PROGRESS.md Resumption Contract (phase, task, next action, critical files) "
        "and record decisions in PLAN-NOTES.md; with no active suite, write a short "
        f"plan under <project-root>/.apothem/plans/.{urgency} Advisory only."
    )


def _operator_text(level: int = 1, tokens: int | None = None) -> str:
    """Return the operator-facing note: compaction is the operator's action."""
    size = f" (about {tokens:,} tokens of context)" if tokens else ""
    if level >= 2:
        return (
            f"Apothem: this session is long{size}. Compact or start a fresh session "
            "once the current step is saved."
        )
    return (
        f"Apothem: this session is growing{size}; the agent is saving state to files."
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
    return {
        "systemMessage": _operator_text(),
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": _advisory_text(),
        },
    }


def _read_payload() -> dict[str, object] | None:
    """Read and parse the hook's stdin JSON payload, fail-open on any error."""
    try:
        if sys.stdin.isatty():
            return None
        raw = sys.stdin.read()
    except (OSError, ValueError):
        # ValueError covers a read from an already-closed stdin. Matches
        # lib/stdin_json.read_stdin_json; catching only OSError let that case
        # crash a hook whose whole contract is to fail open.
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
    if not is_enabled():
        return {}
    session_id = payload.get("session_id") if isinstance(payload, dict) else None
    path = state_path_for(session_id)
    thresholds = resolve_thresholds()

    # Bound the state directory's growth: sweep counter files from ended sessions before writing
    # this session's. Best-effort — a purge failure never disturbs the advisory.
    _purge_stale_state(path.parent)

    state = _read_state(path)
    tokens = context_tokens(payload)
    if tokens is not None:
        if (
            state.context_tokens
            and tokens < state.context_tokens * _COMPACTION_DROP_RATIO
        ):
            # The context shrank sharply: compacted or cleared. Start over.
            state = SessionState()
        state.context_tokens = tokens
        if state.advisories >= MAX_ADVISORIES_PER_SESSION:
            _write_state(path, state)
            return {}
        window = context_window()
        level = advisory_level(tokens, window, state.advisories)
        if level is not None:
            # "Compact now" ends the cycle's budget, so it is never repeated.
            state.advisories = max(state.advisories + 1, level)
        _write_state(path, state)
        if level is None:
            return {}
        return {
            "systemMessage": _operator_text(level, tokens),
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": _advisory_text(level, tokens, window),
            },
        }

    # No measurable context (no transcript, or no usage record yet): fall back
    # to counting activity since the last advisory.
    if state.advisories >= MAX_ADVISORIES_PER_SESSION:
        return {}
    state.tool_calls += 1
    state.output_bytes += estimate_output_bytes(payload)

    envelope = build_envelope(state, thresholds)
    if envelope:
        # Threshold crossed: reset the window so the advisory does not fire on
        # the next tool call (anti-spam back-off), and count it against the
        # per-session cap.
        _write_state(path, SessionState(advisories=state.advisories + 1))
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
