# SPDX-License-Identifier: MIT

"""Per-vendor hook contracts for the dispatcher (``dispatch.py --contract <id>``).

The handlers speak Claude Code's contract: stdin carries ``hook_event_name``,
``tool_name``, ``tool_input``, ``session_id`` and ``cwd``, and stdout is one
envelope whose ``hookSpecificOutput.additionalContext`` is the advice. Other
harnesses run the same kind of command but name events and tools differently
and read the advice from a different place. A contract is one table row that
tells the dispatcher how to translate in both directions, so no handler, guard
or message file changes per vendor:

1. **Event aliases.** The vendor's spelling of an event maps to the canonical
   name in ``events.py`` (``sessionStart`` to ``SessionStart``).
2. **Tool names.** The vendor's tool name maps to the Claude spelling the
   guards test (``Shell``, ``exec``, ``execute_bash`` to ``Bash``). A name
   with no entry passes through unchanged.
3. **Payload keys.** Vendor key spellings (``sessionId``, ``conversation_id``,
   ``toolName``, ``toolArgs``, ``workspace_roots``) fill the Claude keys the
   handlers read.
4. **Output shape.** The handler's envelope is rewritten to the shape the
   vendor reads: the envelope itself (``envelope``), the bare context text
   (``plain``), ``{"additionalContext": ...}`` (``flat``) or
   ``{"additional_context": ...}`` (``snake``).
5. **Delivery.** An event the vendor does not hand to the model produces no
   output and runs no handler, so a hook registered there by mistake costs a
   process start and nothing more.

The dispatcher stays advisory. Every shape carries context only: no shape
emits a permission, a decision, a block or a rewritten tool input.

Sessions. Cursor and Devin Local also import the Claude Code settings file, so
one session start can reach the model twice: once from the vendor's own
registration (``--contract cursor`` or ``--contract devin``, which sets
``dedupe_session_start``) and once from the Claude Code copy in
``~/.claude/settings.json``, which is the default command line. Both copies pass
through :func:`first_session_start`, which keeps one marker per (session, source)
in the per-user hook state directory, so whichever copy runs second is silent. The
default command line takes part only when the process environment names Cursor or
Devin (:data:`HOST_CONTRACT_BY_ENV`, through :func:`run_session_start_once`); under
Claude Code, Codex and Qwen Code it never reads the marker. The marker silences a
repeat for :data:`_DUPLICATE_WINDOW_SECONDS` only, so a later start of the same
session (a second compaction, a resume, a clear) is a real one and delivers. The
key is the normalised ``session_id``, so a vendor that sends ``conversation_id`` or
``sessionId`` shares one marker per conversation, and a payload with no id at all
is never suppressed. The source is part of the key because a session reuses its id
across a compaction, and the bootstrap delivers its recovery context on that
firing; a missing source and ``startup`` are the same first start, because Cursor's
payload has no source and the Claude Code copy may send one. The PostToolUse
counters are not de-duplicated.

Vendor sources (living docs, no immutable id), retrieved 2026-10-28 unless
marked 2026-10-27 (the refuted and confirmed claims of the design note):

* codebuddy: https://www.codebuddy.ai/docs/cli/hooks and /hooks-guide. Claude's
  shape. ``additionalContext`` is documented for SessionStart,
  UserPromptSubmit and PostToolUse; PreToolUse documents only the permission
  fields and ``modifiedInput``.
* devin (Windsurf, Devin Local): https://docs.devin.ai/cli/extensibility/hooks/overview.md.
  Claude's shape. ``additionalContext`` is documented for UserPromptSubmit,
  SessionStart and PostToolUse; tool names are lowercase. The stdin payload has no
  working directory; ``DEVIN_PROJECT_DIR`` is the project root.
* cursor: https://cursor.com/docs/hooks (2026-10-28), /docs/reference/third-party-hooks
  (2026-10-27). camelCase events; sessionStart reads ``{env, additional_context}``.
  The Environment Variables table lists ``CURSOR_PROJECT_DIR``, ``CURSOR_VERSION``
  and the ``CLAUDE_PROJECT_DIR`` alias as always set for a hook command.
* copilot: https://docs.github.com/en/copilot/reference/hooks-reference. A
  camelCase event name selects camelCase stdin and a flat ``additionalContext``;
  the PascalCase spelling selects Claude-shaped stdin.
* kiro: https://kiro.dev/docs/hooks/ and /hooks/types/ (2026-10-27). Plain
  stdout joins the context for SessionStart and UserPromptSubmit only.

TODO(clarify): Cursor's page lists ``additional_context`` for postToolUse, which
the 2026-10-27 refuter did not confirm; the contract delivers SessionStart only.
TODO(clarify): whether Copilot reads ``additionalContext`` from a PascalCase
event's output is unconfirmed (design note section 6).

Standard library only: the hook runtime ships without the ``apothem`` package on
plugin-alone installs.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

__all__ = [
    "CONTRACTS",
    "HOST_CONTRACT_BY_ENV",
    "Contract",
    "first_session_start",
    "get_contract",
    "host_contract_id",
    "normalise_payload",
    "run_contracted",
    "run_session_start_once",
    "shape_output",
]

#: Output shapes. ``envelope`` is the handler's own Claude-shaped output, left
#: byte for byte as written.
ENVELOPE: Final[str] = "envelope"
PLAIN: Final[str] = "plain"
FLAT: Final[str] = "flat"
SNAKE: Final[str] = "snake"

#: How long a SessionStart marker silences a repeat. The two copies of one session
#: start (the vendor's own registration and the Claude Code one it imports) run
#: within a second or two of each other; a start that comes later is a new one.
_DUPLICATE_WINDOW_SECONDS: Final[float] = 10.0
#: Markers older than this are deleted the next time one is written.
_MARKER_MAX_AGE_SECONDS: Final[float] = 3600.0
_MARKER_SCAN_LIMIT: Final[int] = 200

#: The environment variables a vendor sets for the hook commands it runs, mapped to
#: its contract id. They name the host that also runs the Claude Code copy of the
#: SessionStart command, so the default command line can take part in the marker.
#: ``CLAUDE_PROJECT_DIR`` is no signal: Cursor exports it as an alias.
HOST_CONTRACT_BY_ENV: Final[Mapping[str, str]] = {
    "CURSOR_PROJECT_DIR": "cursor",
    "CURSOR_VERSION": "cursor",
    "DEVIN_PROJECT_DIR": "devin",
}


@dataclass(frozen=True)
class Contract:
    """One vendor's hook contract; see the module docstring for the five parts."""

    contract_id: str
    output: str
    delivers: frozenset[str]
    events: Mapping[str, str] = field(default_factory=dict)
    tools: Mapping[str, str] = field(default_factory=dict)
    dedupe_session_start: bool = False
    project_dir_env: str = ""

    def canonical_event(self, name: str) -> str:
        """Return the canonical spelling of the vendor event *name*."""
        return self.events.get(name, name)

    def canonical_tool(self, name: str) -> str:
        """Return the Claude spelling of the vendor tool *name*."""
        return self.tools.get(name, name)


_CLAUDE_TOOLS: Final[dict[str, str]] = {}

#: Devin's built-in tool names are lowercase (docs.devin.ai lifecycle hooks).
_DEVIN_TOOLS: Final[dict[str, str]] = {
    "read": "Read",
    "write": "Write",
    "edit": "Edit",
    "grep": "Grep",
    "glob": "Glob",
    "exec": "Bash",
}

#: Copilot CLI tool names for the camelCase events (hooks reference, CLI tool
#: names for matching). The PascalCase spelling of an event already carries
#: Claude's names, and an unlisted name passes through.
_COPILOT_TOOLS: Final[dict[str, str]] = {
    "bash": "Bash",
    "powershell": "PowerShell",
    "create": "Write",
    "edit": "Edit",
    "view": "Read",
    "glob": "Glob",
    "grep": "Grep",
}

#: Kiro tool ids (kiro.dev hooks and tool-matcher docs).
_KIRO_TOOLS: Final[dict[str, str]] = {
    "execute_bash": "Bash",
    "execute_pwsh": "PowerShell",
    "fs_write": "Write",
    "str_replace": "Edit",
    "read_file": "Read",
    "grep_search": "Grep",
}

#: Cursor matches preToolUse and postToolUse on the tool type (Shell, Read,
#: Write, Grep, Delete, Task, MCP:<tool_name>).
_CURSOR_TOOLS: Final[dict[str, str]] = {"Shell": "Bash"}

_COPILOT_EVENTS: Final[dict[str, str]] = {
    "sessionStart": "SessionStart",
    "preToolUse": "PreToolUse",
    "postToolUse": "PostToolUse",
    "userPromptSubmitted": "UserPromptSubmit",
    "agentStop": "Stop",
    "preCompact": "PreCompact",
    "notification": "Notification",
}

_CURSOR_EVENTS: Final[dict[str, str]] = {
    "sessionStart": "SessionStart",
    "preToolUse": "PreToolUse",
    "postToolUse": "PostToolUse",
    "beforeSubmitPrompt": "UserPromptSubmit",
    "stop": "Stop",
    "preCompact": "PreCompact",
}

_DEVIN_EVENTS: Final[dict[str, str]] = {"PostCompaction": "PostCompact"}

_CLAUDE_SHAPED_DELIVERY: Final[frozenset[str]] = frozenset(
    {"SessionStart", "UserPromptSubmit", "PostToolUse"}
)

CONTRACTS: Final[Mapping[str, Contract]] = {
    "claude": Contract(
        "claude",
        ENVELOPE,
        frozenset(
            {
                "SessionStart",
                "PreCompact",
                "PostCompact",
                "PreToolUse",
                "PostToolUse",
                "UserPromptSubmit",
                "Stop",
                "Notification",
            }
        ),
        tools=_CLAUDE_TOOLS,
    ),
    "codebuddy": Contract("codebuddy", ENVELOPE, _CLAUDE_SHAPED_DELIVERY),
    "devin": Contract(
        "devin",
        ENVELOPE,
        _CLAUDE_SHAPED_DELIVERY,
        events=_DEVIN_EVENTS,
        tools=_DEVIN_TOOLS,
        dedupe_session_start=True,
        project_dir_env="DEVIN_PROJECT_DIR",
    ),
    "cursor": Contract(
        "cursor",
        SNAKE,
        frozenset({"SessionStart"}),
        events=_CURSOR_EVENTS,
        tools=_CURSOR_TOOLS,
        dedupe_session_start=True,
    ),
    "copilot": Contract(
        "copilot",
        FLAT,
        frozenset({"SessionStart", "PostToolUse", "Notification"}),
        events=_COPILOT_EVENTS,
        tools=_COPILOT_TOOLS,
    ),
    "kiro": Contract(
        "kiro",
        PLAIN,
        frozenset({"SessionStart", "UserPromptSubmit"}),
        tools=_KIRO_TOOLS,
    ),
}


def get_contract(contract_id: str) -> Contract:
    """Return the contract named *contract_id*.

    Raises:
        ValueError: When no contract has that id. The dispatcher converts it to
            its fail-open envelope.
    """
    try:
        return CONTRACTS[contract_id]
    except KeyError:
        known = ", ".join(sorted(CONTRACTS))
        raise ValueError(
            f"Unknown hook contract: {contract_id} (known: {known})"
        ) from None


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _first_workspace_root(payload: Mapping[str, object]) -> str:
    for key in ("workspace_roots", "workspaceRoots"):
        roots = payload.get(key)
        if isinstance(roots, list) and roots and isinstance(roots[0], str):
            return roots[0]
    return ""


def _project_dir_from_env(contract: Contract) -> str:
    """Return the project root the vendor exports, for a payload with no ``cwd``.

    Devin's stdin carries no working directory, and ``DEVIN_PROJECT_DIR`` is the
    project root it documents, so the plan, memory and knowledge-base summaries
    resolve against the project and not against wherever Devin spawned the hook.
    """
    name = contract.project_dir_env
    return os.environ.get(name, "").strip() if name else ""


def _tool_args(value: object) -> object:
    """Return Copilot's ``toolArgs``, which arrives as a JSON string or an object."""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return {}
    return value


def normalise_payload(
    contract: Contract, payload: Mapping[str, object], event: str
) -> dict[str, object]:
    """Return *payload* with the Claude keys the handlers read filled in.

    Keys the vendor already spells the Claude way win; the vendor spellings
    only fill a missing key, and every other key passes through untouched.
    """
    out: dict[str, object] = dict(payload)
    out["hook_event_name"] = event
    if not _text(out.get("session_id")):
        for key in ("sessionId", "conversation_id"):
            if _text(payload.get(key)):
                out["session_id"] = payload[key]
                break
    if not _text(out.get("cwd")):
        root = _first_workspace_root(payload) or _project_dir_from_env(contract)
        if root:
            out["cwd"] = root
    raw_tool = _text(out.get("tool_name")) or _text(payload.get("toolName"))
    if raw_tool:
        out["tool_name"] = contract.canonical_tool(raw_tool)
    if "tool_input" not in out and "toolArgs" in payload:
        out["tool_input"] = _tool_args(payload["toolArgs"])
    if "tool_response" not in out:
        for key in ("toolResult", "tool_result", "tool_output"):
            if key in payload:
                out["tool_response"] = payload[key]
                break
    return out


def _context_of(captured: str) -> str:
    """Return the model-facing text of the handler's output, or ``""``.

    The advice is the envelope's ``hookSpecificOutput.additionalContext``. A
    ``systemMessage`` is addressed to the operator and is not context.
    """
    text = captured.strip()
    if not text:
        return ""
    try:
        parsed = json.loads(text)
    except ValueError:
        return text
    if not isinstance(parsed, dict):
        return ""
    specific = parsed.get("hookSpecificOutput")
    context = specific.get("additionalContext") if isinstance(specific, dict) else None
    return context.strip() if isinstance(context, str) else ""


def shape_output(contract: Contract, event: str, captured: str) -> str:
    """Return the text to write to stdout for the handler output *captured*.

    The ``envelope`` shape returns *captured* unchanged. The other shapes carry
    the advice only, and return ``""`` (no output) when there is none, so a
    silent guard stays silent on every vendor.
    """
    shape = contract.output
    if shape == ENVELOPE:
        return captured
    context = _context_of(captured)
    if not context:
        return ""
    if shape == PLAIN:
        return context + "\n"
    key = "additionalContext" if shape == FLAT else "additional_context"
    return json.dumps({key: context}, separators=(",", ":")) + "\n"


def _purge_old_markers(directory: Path) -> None:
    """Delete session markers past their age limit; best effort and bounded."""
    cutoff = time.time() - _MARKER_MAX_AGE_SECONDS
    with contextlib.suppress(OSError):
        for index, child in enumerate(directory.iterdir()):
            if index >= _MARKER_SCAN_LIMIT:
                break
            if child.suffix == ".seen" and child.stat().st_mtime < cutoff:
                child.unlink()


def _marker_is_stale(marker: Path) -> bool:
    """Return True when *marker* is older than the duplicate window (or gone)."""
    try:
        return time.time() - marker.stat().st_mtime > _DUPLICATE_WINDOW_SECONDS
    except OSError:
        return True


def first_session_start(payload: Mapping[str, object] | None) -> bool:
    """Return True unless this (session, source) start was delivered a moment ago.

    *payload* is the normalised one (see :func:`normalise_payload`), so a vendor
    that spells the id ``conversation_id`` or ``sessionId`` still keys the
    marker. The marker is kept in the per-user hook state directory and is the
    same whichever registration runs, the vendor's own or the Claude Code copy
    it imports, so the second of two copies is silent. It binds for
    :data:`_DUPLICATE_WINDOW_SECONDS` only; a later start of the same session is
    a new one. A payload with no session id cannot be told apart from another
    session's, so it always delivers. Any failure to record returns True: a
    missing marker costs one repeated advisory, and a suppressed session start
    would cost the whole bootstrap.
    """
    from state_dir import hook_state_dir, session_key

    data = payload or {}
    session = _text(data.get("session_id"))
    if not session:
        return True
    # Cursor's sessionStart carries no source, and the Claude Code copy may send
    # "startup": both are the first start of the session, so they share a key.
    reason = _text(data.get("source"))
    source = "start" if reason in {"", "startup"} else session_key(reason)
    name = f"{session_key(session)}--{source}.seen"
    try:
        directory = hook_state_dir("session-start")
    except OSError:
        return True
    marker = directory / name
    for _attempt in range(2):
        try:
            descriptor = os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            if not _marker_is_stale(marker):
                return False
            with contextlib.suppress(OSError):
                marker.unlink()
            continue
        except OSError:
            return True
        os.close(descriptor)
        _purge_old_markers(directory)
        return True
    # A concurrent start replaced the stale marker first; it is the one that delivers.
    return False


def host_contract_id(environ: Mapping[str, str] | None = None) -> str:
    """Return the contract id of the vendor whose hook environment this is, or ``""``."""
    env = os.environ if environ is None else environ
    for name, contract_id in HOST_CONTRACT_BY_ENV.items():
        if env.get(name, "").strip():
            return contract_id
    return ""


def _failure_envelope(event: str, message: str) -> str:
    """Return the handler-shaped failure output the dispatcher would have written."""
    from events import HOOK_SPECIFIC_OUTPUT_EVENTS

    text = f"Hook execution failure: {message}"
    if event in HOOK_SPECIFIC_OUTPUT_EVENTS:
        envelope: dict[str, object] = {
            "hookSpecificOutput": {"hookEventName": event, "additionalContext": text}
        }
    else:
        envelope = {"systemMessage": text}
    return json.dumps(envelope, separators=(",", ":")) + "\n"


def _write(text: str) -> None:
    if not text:
        return
    buffer = getattr(sys.stdout, "buffer", None)
    if buffer is None:
        sys.stdout.write(text)
        return
    sys.stdout.flush()
    buffer.write(text.encode("utf-8"))
    buffer.flush()


def _read_stdin() -> str:
    try:
        if sys.stdin.isatty():
            return ""
        return sys.stdin.read()
    except (OSError, ValueError):
        return ""


def _parse(raw: str) -> dict[str, object] | None:
    if not raw.strip():
        return None
    try:
        parsed = json.loads(raw)
    except ValueError:
        return None
    return parsed if isinstance(parsed, dict) else None


def run_contracted(
    contract_id: str, event_name: str, run: Callable[[str], None]
) -> None:
    """Run the handler *run* under the contract named *contract_id*.

    Reads the vendor payload once, hands the handler a Claude-shaped copy on
    ``sys.stdin``, captures what it writes to ``sys.stdout`` and writes it back
    in the vendor's shape. *run* receives the canonical event name. Raises
    ``ValueError`` for an unknown contract; a handler error becomes a shaped
    failure message, so the command still exits cleanly.
    """
    contract = get_contract(contract_id)
    event = contract.canonical_event(event_name)
    raw = _read_stdin()
    payload = _parse(raw)
    if event not in contract.delivers:
        return
    normalised = (
        normalise_payload(contract, payload, event) if payload is not None else None
    )
    if (
        contract.dedupe_session_start
        and event == "SessionStart"
        and not first_session_start(normalised)
    ):
        return
    try:
        text = json.dumps(normalised) if normalised is not None else raw
    except (TypeError, ValueError):
        text = raw
    captured = io.StringIO()
    failure = ""
    saved = sys.stdin
    sys.stdin = io.StringIO(text)
    try:
        with contextlib.redirect_stdout(captured):
            try:
                run(event)
            except Exception as exc:  # noqa: BLE001, RUF100 - fail-open boundary: a handler error becomes a failure message, never a traceback (BLE001 is the intent marker; RUF100 self-suppresses because ruff's BLE family is not active)
                failure = _failure_envelope(event, str(exc))
    finally:
        sys.stdin = saved
    _write(shape_output(contract, event, failure or captured.getvalue()))


def run_session_start_once(run: Callable[[], None]) -> None:
    """Run the default SessionStart handler *run* unless this start was just delivered.

    The default command line is what the Claude Code adapter writes to
    ``~/.claude/settings.json`` and what Cursor and Devin Local import from it.
    Under either host (:func:`host_contract_id`) the vendor's own registration
    delivers the same start, so the pair share one marker (see
    :func:`first_session_start`) and the second to run is silent. The payload is
    read once and handed to *run* on ``sys.stdin`` with the vendor's spellings
    filled in (the session id, and the working directory a Devin payload lacks);
    the output is the handler's own, unchanged. Anything unexpected runs *run*.
    """
    raw = _read_stdin()
    text = raw
    try:
        host = host_contract_id()
        payload = _parse(raw)
        if host and payload is not None:
            normalised = normalise_payload(get_contract(host), payload, "SessionStart")
            if not first_session_start(normalised):
                return
            text = json.dumps(normalised)
    except Exception:  # noqa: BLE001, RUF100 - fail-open boundary: a marker or payload problem runs the bootstrap, never suppresses it (BLE001 is the intent marker; RUF100 self-suppresses because ruff's BLE family is not active)
        text = raw
    saved = sys.stdin
    sys.stdin = io.StringIO(text)
    try:
        run()
    finally:
        sys.stdin = saved
