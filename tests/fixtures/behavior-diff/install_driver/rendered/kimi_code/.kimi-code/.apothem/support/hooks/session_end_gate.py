# SPDX-License-Identifier: MIT

"""Stop handler that gates the session-end protocol to one emission per session.

Why this handler exists. The ``Stop`` hook emitted ``messages/stop.md`` verbatim
on **every** firing. ``Stop`` fires at the end of every assistant turn, not only
at the end of a session, so the full Phase A/B/C session-end mandate was
re-asserted on every turn. Because that text reads as a fresh work order rather
than a status check, each response triggered another firing, and **nothing the
agent did changed what the hook asserted** — the loop had no fixed point. An
operator could only escape it by restarting the harness, since hook
configuration and message bodies are both snapshotted at session start.

The defect was never the protocol's content; it was its cadence. This module is
the dispatch-routed ``Stop`` handler that supplies the missing termination
condition: the protocol is emitted **at most once per session**, and only once
the session is old enough to have accumulated state worth externalizing.
``messages/stop.md`` remains the single source of the protocol text — this
handler decides *when* it is emitted, never *what* it says. That separation
matters: the message file is a cross-reference target bound by
``rules/context-management.md``, ``rules/auto-memory.md``, and the capability
graph, so its path and role are preserved exactly.

What it guarantees.

* **Advisory-only.** It NEVER blocks. The envelope carries the ``Stop``
  ``hookSpecificOutput`` shape or is empty.
* **Terminating.** Once the protocol has been emitted for a session, every
  later ``Stop`` in that session emits nothing. This is the property whose
  absence caused the loop, so it is asserted directly by the test suite.
* **Fast.** One small-file read plus one write (a JSON object keyed by session
  id). No project scan, no engine import on the hot path.
* **Fail-open.** Any exception -> emit nothing, never disrupt session shutdown.
  A gate bug must never cost the operator their session close.

Configuration.

* ``APOTHEM_SESSION_END_MIN_STOPS`` (default ``3``) — how many ``Stop`` firings
  must accrue before the protocol may emit. A session-end checklist delivered on
  the very first turn-end arrives before any state exists to flush; this floor
  delays it to a point where externalization is plausibly meaningful. A
  non-positive or unparseable override falls back to the default, so a typo can
  never silently disable the gate.
* ``APOTHEM_SESSION_END_ENABLED`` (default enabled) — set to ``0``, ``false``,
  ``no``, or ``off`` to silence the protocol entirely. Provided because the
  emission is advisory: an operator who does not want it should be able to turn
  it off without editing plugin files, which is what the loop forced.
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

#: Environment override for the minimum number of ``Stop`` firings before the
#: protocol may emit. Falls back to the default when unset, non-numeric, or
#: non-positive.
MIN_STOPS_ENV: Final[str] = "APOTHEM_SESSION_END_MIN_STOPS"

#: Environment switch that silences the protocol entirely.
ENABLED_ENV: Final[str] = "APOTHEM_SESSION_END_ENABLED"

#: Default floor. Three turn-ends is enough for a session to have produced work
#: worth externalizing, while still reaching the operator well before a typical
#: session closes.
DEFAULT_MIN_STOPS: Final[int] = 3

#: Values that read as "off" for :data:`ENABLED_ENV`. Compared case-folded.
_DISABLED_VALUES: Final[frozenset[str]] = frozenset({"0", "false", "no", "off"})

#: Per-session state lives under a dedicated subdirectory of the OS temp dir —
#: never inside a tracked tree (the hook runs in the operator's harness, not a
#: checkout). Kept separate from the proactive-compaction tracker's directory so
#: neither handler's back-off can reset the other's.
_STATE_DIRNAME: Final[str] = "apothem-session-end"

#: Age past which a per-session state file is purged on the next write. A
#: session's state is only meaningful within one live session; a file untouched
#: for this long belongs to an ended session and would otherwise accumulate in
#: $TMP unbounded. Purge is best-effort and never disturbs the gate.
_STATE_TTL_SECONDS: Final[float] = 24 * 60 * 60

#: Sanitized fallback when a session id is absent or unusable.
_DEFAULT_SESSION_KEY: Final[str] = "_default"

#: Emitted when the protocol fires. ``Stop`` is a member of
#: ``HOOK_SPECIFIC_OUTPUT_EVENTS``, so the envelope uses that shape.
_EVENT_NAME: Final[str] = "Stop"


@dataclass
class SessionState:
    """Mutable per-session gate state.

    ``stops`` counts ``Stop`` firings observed for the session. ``emitted``
    latches to ``True`` the moment the protocol fires and is never cleared, which
    is what makes the gate terminating rather than periodic.
    """

    stops: int = 0
    emitted: bool = False

    def to_dict(self) -> dict[str, object]:
        """Serialize to the on-disk JSON shape."""
        return {"stops": self.stops, "emitted": self.emitted}

    @classmethod
    def from_obj(cls, obj: object) -> SessionState:
        """Reconstruct from a parsed JSON object, tolerating shape drift.

        A garbage or partial object yields a zeroed, un-emitted state: a corrupt
        file degrades to "treat this as a fresh session", which at worst emits
        the protocol once more. It never degrades to repeated emission, because
        each subsequent firing rewrites the latched flag.
        """
        if not isinstance(obj, dict):
            return cls()
        stops = obj.get("stops")
        emitted = obj.get("emitted")
        return cls(
            stops=stops if isinstance(stops, int) and stops >= 0 else 0,
            emitted=emitted is True,
        )


def _positive_int_env(name: str, default: int) -> int:
    """Return a positive integer from environment variable *name*, else *default*."""
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def is_enabled() -> bool:
    """Return False when :data:`ENABLED_ENV` reads as an explicit "off" value."""
    raw = os.environ.get(ENABLED_ENV, "").strip().casefold()
    return raw not in _DISABLED_VALUES if raw else True


def resolve_min_stops() -> int:
    """Resolve the ``Stop``-firing floor from the environment."""
    return _positive_int_env(MIN_STOPS_ENV, DEFAULT_MIN_STOPS)


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
    """Return the state-file path for *session_id* (never inside a checkout)."""
    return _state_dir() / f"{_sanitize_session_key(session_id)}.json"


def _read_state(path: Path) -> SessionState:
    """Load per-session state from *path*, fail-open to a fresh state on error."""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return SessionState()
    try:
        return SessionState.from_obj(json.loads(raw))
    except (json.JSONDecodeError, ValueError):
        return SessionState()


def _write_state(path: Path, state: SessionState) -> None:
    """Persist per-session state to *path* atomically, creating the directory.

    Writes to a sibling temp file and renames it over *path* in one atomic
    ``os.replace`` (mirroring ``apothem.lib.atomic_io`` inline, since this
    standalone hook ships without the ``apothem`` package on plugin-alone
    installs). A crash mid-write leaves the prior state intact — never a
    truncated blob that :func:`_read_state` would read as "never emitted", which
    would re-arm the protocol under the operator.
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
    """Remove state files untouched for longer than ``_STATE_TTL_SECONDS``.

    Best-effort and fail-open: every filesystem error is suppressed, so a purge
    failure never disturbs the gate.
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


def read_protocol_text(context_file: str) -> str:
    """Return the protocol body from *context_file*, or ``""`` when unreadable.

    The text is owned by ``messages/stop.md``, not by this module: the gate
    decides cadence, the message file decides content. An unreadable or empty
    file yields ``""``, which :func:`build_envelope` turns into silence rather
    than an empty advisory.
    """
    if not context_file:
        return ""
    try:
        text = Path(context_file).read_text(encoding="utf-8")
    except OSError:
        return ""
    return text.strip()


def build_envelope(text: str) -> dict[str, object]:
    """Wrap *text* in the ``Stop`` envelope, or return an empty envelope."""
    if not text:
        return {}
    return {
        "hookSpecificOutput": {
            "hookEventName": _EVENT_NAME,
            "additionalContext": text,
        }
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


def evaluate(payload: dict[str, object] | None, context_file: str) -> dict[str, object]:
    """Advance the per-session gate and return the envelope for this firing.

    Pre-condition: *payload* is the harness ``Stop`` stdin object (or ``None``)
    and *context_file* points at the protocol message.

    Post-condition: the session's state file reflects this firing. The protocol
    envelope is returned exactly once per session — on the first firing at or
    above the configured floor — and every later firing in that session returns
    an empty envelope.
    """
    if not is_enabled():
        return {}

    session_id = payload.get("session_id") if isinstance(payload, dict) else None
    path = state_path_for(session_id)

    # Bound $TMP growth: sweep state files from ended sessions before writing
    # this session's. Best-effort — a purge failure never disturbs the gate.
    _purge_stale_state(path.parent)

    state = _read_state(path)
    if state.emitted:
        # Already delivered for this session. This is the terminating branch —
        # the one whose absence turned the hook into a non-convergent loop.
        state.stops += 1
        _write_state(path, state)
        return {}

    state.stops += 1
    if state.stops < resolve_min_stops():
        _write_state(path, state)
        return {}

    envelope = build_envelope(read_protocol_text(context_file))
    # Latch only on an envelope that actually carries the protocol. An
    # unreadable message file must not consume the session's single emission,
    # or a transient read error would silence the protocol for the whole
    # session while looking like a successful delivery.
    if envelope:
        state.emitted = True
    _write_state(path, state)
    return envelope


def main(argv: list[str] | None = None) -> None:
    """Entry point. Advances the gate and emits one envelope; never raises.

    *argv* carries the dispatcher's ``--context-file <path>`` pair. Parsing is
    deliberately minimal — the dispatcher is the only caller and passes a fixed
    shape — and an absent flag degrades to silence rather than an error.

    FAIL-OPEN: any unexpected exception is swallowed and an empty (no-op)
    envelope is written, so a gate bug never disrupts session shutdown.
    """
    try:
        args = list(argv or [])
        context_file = ""
        if "--context-file" in args:
            index = args.index("--context-file")
            if index + 1 < len(args):
                context_file = args[index + 1]
        payload = _read_payload()
        envelope = evaluate(payload, context_file)
        sys.stdout.write(json.dumps(envelope, separators=(",", ":")) + "\n")
    except Exception:  # noqa: BLE001, RUF100 - fail-open boundary: a gate error must never disrupt session shutdown; emit an empty envelope and proceed (BLE001 is the intent marker; RUF100 self-suppresses because ruff's BLE family is not active)
        sys.stdout.write("{}\n")


if __name__ == "__main__":
    main()
