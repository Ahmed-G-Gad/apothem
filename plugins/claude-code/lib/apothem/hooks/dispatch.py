# SPDX-License-Identifier: MIT

"""Unified Python entrypoint for supported harness hook events.

Routes `SessionStart` to `session_start_bootstrap.main()` and all other
whitelisted events to `emit_hook_context.main()` (hook mode).

Contract: always exits 0. Any uncaught exception is converted to a valid
failure envelope on stdout so the hook runtime never sees a raw traceback.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Final

_HOOK_DIR: Final[Path] = Path(__file__).resolve().parent
_LIB_DIR: Final[Path] = _HOOK_DIR / "lib"
for _path in (_HOOK_DIR, _LIB_DIR):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

# Both event sets come from the single source of truth at
# ``hooks/lib/events.py``. ``_VALID_EVENTS`` is the dispatcher
# whitelist; ``_HOOK_SPECIFIC_EVENTS`` is the envelope-schema
# subset used by the failure-fallback path so it remains usable
# even when ``emit_hook_context`` itself fails to import.
from events import (
    HOOK_SPECIFIC_OUTPUT_EVENTS as _HOOK_SPECIFIC_EVENTS,
)
from events import (
    SUPPORTED_EVENTS as _VALID_EVENTS,
)


def _emit_failure(event_name: str, message: str) -> None:
    """Emit a failure envelope. Prefers ``emit_hook_context``'s rich writer;
    falls back to a self-contained envelope when that module is unimportable
    (e.g., its module-load itself raises). Always writes valid JSON to stdout
    and never raises."""
    try:
        from emit_hook_context import emit_failure_envelope as _rich

        _rich(event_name, message)
        return
    except Exception:  # noqa: BLE001, RUF100 - outermost dispatcher boundary; falls back to JSON envelope below (BLE001 is the validator's required intent-marker; RUF100 self-suppresses because ruff's BLE family is not active)
        pass
    import json as _json

    name = event_name or "UnknownEvent"
    text = f"Hook bootstrap failure: {message}"
    payload: dict[str, object]
    if name in _HOOK_SPECIFIC_EVENTS:
        payload = {
            "hookSpecificOutput": {
                "hookEventName": name,
                "additionalContext": text,
            }
        }
    else:
        payload = {"systemMessage": text}
    sys.stdout.write(_json.dumps(payload, separators=(",", ":")) + "\n")


_MESSAGES_DIR: Final[Path] = _HOOK_DIR / "messages"

# The ``AskUserQuestion`` validator is a dispatch-routed ``PreToolUse`` handler
# that inspects the live tool payload (an option-marker well-formedness check at
# call time) rather than emitting a static Markdown context. It is selected by
# its message basename so the same positional invocation shape the other
# PreToolUse guards use (``PreToolUse pretooluse-askuserquestion-recommended``)
# routes here. The basename is matched on the ``--context-file`` tail so the
# routing is independent of where the message file lives on disk.
_ASKUSERQUESTION_MESSAGE_BASENAME: Final[str] = "pretooluse-askuserquestion-recommended"

# The proactive-compaction tracker is a dispatch-routed ``PostToolUse`` handler
# that maintains per-session activity counters and surfaces a proactive-
# compaction advisory once a CM-19 threshold is crossed. It is selected by its
# message basename so the same positional invocation shape the other handlers
# use (``PostToolUse posttooluse-proactive-compaction``) routes here; the
# basename is matched on the ``--context-file`` tail, independent of where the
# message file lives on disk.
_PROACTIVE_COMPACTION_MESSAGE_BASENAME: Final[str] = "posttooluse-proactive-compaction"

# The session-end gate is a dispatch-routed ``Stop`` handler that decides
# *whether* this firing emits the session-end protocol. ``Stop`` fires at every
# turn end, so emitting ``stop.md`` verbatim each time re-asserted the whole
# mandate on every turn and never converged. The gate keeps the message file as
# the single source of the protocol text and adds the missing termination
# condition (at most one emission per session). Selected by message basename,
# matched on the ``--context-file`` tail, so the route holds wherever the message
# file lives on disk.
_SESSION_END_MESSAGE_BASENAME: Final[str] = "stop"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse dispatch CLI arguments.

    Two invocation shapes are accepted:

    1. **Short positional form** (preferred — settings.json invocations):
       ``apothem-hook <Event> [<message-name>]``. ``<message-name>`` is
       the bare basename of a Markdown fixture under
       ``apothem.hooks.messages`` (e.g., ``pretooluse-write``); the ``.md``
       suffix is added automatically.
    2. **Flag form**: an alternate invocation shape accepted alongside
       the positional form:
       ``--event-name <Event> --context-file <path>``.

    When the positional form is used, ``<message-name>`` resolves to
    ``<apothem-hooks-package-dir>/messages/<name>.md`` so the file is
    located regardless of where the dispatcher lives on disk (a source
    checkout or a materialized ``apothem/hooks/`` tree under a harness
    root).
    """
    parser = argparse.ArgumentParser(prog="apothem-hook")
    parser.add_argument("event_positional", nargs="?", default=None)
    parser.add_argument("message_name_positional", nargs="?", default=None)
    parser.add_argument("--event-name", "-e", default=None)
    parser.add_argument("--context-file", "-c", default="")
    parser.add_argument("--quiet", "-q", action="store_true")
    args = parser.parse_args(argv)
    if args.event_positional and not args.event_name:
        args.event_name = args.event_positional
    if args.message_name_positional and not args.context_file:
        args.context_file = str(_MESSAGES_DIR / f"{args.message_name_positional}.md")
    if not args.event_name:
        parser.error("event name is required (positional or --event-name)")
    return args


def _run_session_start(quiet: bool) -> None:
    """Invoke the session-start bootstrap.

    Fail-disposition: fail-open. Bootstrap is a context-emission helper;
    a failure here degrades the operator's session-start summary but must
    never block the session itself. Errors propagate to ``main`` and are
    converted to a failure envelope on stdout.
    """
    import session_start_bootstrap as ssb

    forwarded: list[str] = ["--quiet"] if quiet else []
    ssb.main(forwarded)


def _route_matches(context_file: str, basename: str) -> bool:
    """Return True when *context_file*'s basename stem equals *basename*.

    Matched on the ``--context-file`` basename (with or without the ``.md``
    suffix) so a route holds whether the dispatcher is invoked with the
    positional message name or an absolute message-file path resolved by
    :func:`parse_args`. Shared by every message-basename route selector so the
    match logic lives in one place.
    """
    if not context_file:
        return False
    name = Path(context_file).name
    stem = name[:-3] if name.endswith(".md") else name
    return stem == basename


def _is_askuserquestion_route(context_file: str) -> bool:
    """Return True when the message basename selects the AskUserQuestion guard."""
    return _route_matches(context_file, _ASKUSERQUESTION_MESSAGE_BASENAME)


def _run_askuserquestion_guard(quiet: bool) -> None:
    """Invoke the call-time AskUserQuestion option-marker validator.

    Fail-disposition: fail-open. The validator inspects the live tool payload
    for ``(Recommended)``-marker well-formedness and emits an advisory
    ``systemMessage`` (default) or a blocking ``decision`` envelope (strict
    opt-in). Its own ``main`` swallows every exception and emits an allow
    envelope, so a validator bug never blocks the operator's question. ``quiet``
    suppresses no output here: a block decision must always reach the harness.
    """
    import askuserquestion_validator as aqv

    aqv.main([])


def _is_proactive_compaction_route(context_file: str) -> bool:
    """Return True when the message basename selects the proactive-compaction tracker."""
    return _route_matches(context_file, _PROACTIVE_COMPACTION_MESSAGE_BASENAME)


def _run_proactive_compaction_tracker(quiet: bool) -> None:
    """Invoke the per-session proactive-compaction activity tracker.

    Fail-disposition: fail-open. The tracker maintains per-session activity
    counters and emits an advisory ``systemMessage`` once a CM-19 threshold is
    crossed; it NEVER blocks (a PostToolUse hook cannot block the tool call that
    already ran). Its own ``main`` swallows every exception and emits an empty
    envelope, so a tracker bug never disrupts the session. ``quiet`` is unused:
    the tracker is already low-noise (silent below threshold), and its advisory
    must always reach the harness when a threshold crosses.
    """
    import proactive_compaction_tracker as pct

    pct.main([])


def _is_session_end_route(context_file: str) -> bool:
    """Return True when the message basename selects the session-end gate."""
    return _route_matches(context_file, _SESSION_END_MESSAGE_BASENAME)


def _run_session_end_gate(context_file: str, quiet: bool) -> None:
    """Invoke the per-session gate that rations the session-end protocol.

    Fail-disposition: fail-open. The gate reads the protocol body from
    *context_file* and emits it at most once per session; it NEVER blocks
    (session shutdown must not depend on an advisory). Its own ``main`` swallows
    every exception and emits an empty envelope, so a gate bug costs the
    operator nothing. ``quiet`` is unused: the gate is already silent by default
    and emits at most one advisory for the whole session.
    """
    import session_end_gate as seg

    seg.main(["--context-file", context_file])


def _run_emit(event_name: str, context_file: str, quiet: bool) -> None:
    """Invoke emit_hook_context in hook mode.

    Fail-disposition: fail-open. Hook-context emission is advisory; a
    failure here degrades the contextual nudge but must never block the
    underlying tool call (PreToolUse) or session shutdown (Stop).
    Errors propagate to ``main`` and are converted to a failure envelope.
    """
    import emit_hook_context as ehc

    argv = [
        "--hook-event-name",
        event_name,
        "--context-file",
        context_file,
    ]
    if quiet:
        argv.append("--quiet")
    ehc.main(argv)


def dispatch(event_name: str, context_file: str, quiet: bool) -> None:
    """Route `event_name` to the correct hook script."""
    if event_name not in _VALID_EVENTS:
        raise ValueError(f"Unknown event: {event_name}")

    if event_name == "SessionStart":
        _run_session_start(quiet)
        return

    # PreToolUse with the AskUserQuestion message basename routes to the live
    # payload validator rather than emitting a static Markdown context.
    if event_name == "PreToolUse" and _is_askuserquestion_route(context_file):
        _run_askuserquestion_guard(quiet)
        return

    # PostToolUse with the proactive-compaction message basename routes to the
    # per-session activity tracker rather than emitting a static Markdown
    # context.
    if event_name == "PostToolUse" and _is_proactive_compaction_route(context_file):
        _run_proactive_compaction_tracker(quiet)
        return

    # Stop with the session-end message basename routes to the per-session gate,
    # which emits the same Markdown context but at most once per session rather
    # than on every turn end.
    if event_name == "Stop" and _is_session_end_route(context_file):
        _run_session_end_gate(context_file, quiet)
        return

    if not context_file:
        raise ValueError(f"--context-file required for event '{event_name}'")

    _run_emit(event_name, context_file, quiet)


def _best_effort_event_name(argv: list[str] | None) -> str:
    """Recover the event name from *argv* without enforcing the full grammar.

    A malformed invocation makes the strict :func:`parse_args` raise
    ``SystemExit`` before the event name is bound, which would leave the failure
    envelope naming ``UnknownEvent``. This lenient pre-parse extracts the event
    name (the first positional or ``--event-name`` / ``-e`` value) where one is
    present so the envelope names the event. Returns ``""`` when no event name
    is recoverable. Never raises: argparse's own ``SystemExit`` (e.g. a missing
    option-argument) is caught and degrades to ``""``.
    """
    try:
        lenient = argparse.ArgumentParser(add_help=False)
        lenient.add_argument("event_positional", nargs="?", default=None)
        lenient.add_argument("--event-name", "-e", default=None)
        namespace, _ = lenient.parse_known_args(argv)
    except SystemExit:
        return ""
    return namespace.event_name or namespace.event_positional or ""


def main(argv: list[str] | None = None) -> None:
    """Entry point. Emits a failure envelope on any error; never raises non-zero.

    A malformed invocation makes ``argparse`` raise ``SystemExit`` with a
    non-zero code. The hook contract is that the harness never sees a raw
    non-zero exit or traceback — only a valid JSON envelope — so an argparse
    *error* exit is converted to a failure envelope and the process exits 0. A
    clean ``--help`` / ``--version`` exit (code 0 or ``None``) passes through.

    The event name is recovered best-effort before the strict parse so a parse
    *error* still names the event in the failure envelope rather than
    ``UnknownEvent``.
    """
    event_name = _best_effort_event_name(argv)
    try:
        args = parse_args(argv)
        event_name = args.event_name
        dispatch(event_name, args.context_file, args.quiet)
    except SystemExit as exc:
        if exc.code in (0, None):
            raise
        _emit_failure(event_name, f"invalid hook invocation (argparse exit {exc.code})")
    except Exception as exc:
        _emit_failure(event_name, str(exc))


if __name__ == "__main__":
    main()
