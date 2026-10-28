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
   guards test (``Shell``, ``RunCommand``, ``exec``, ``execute_bash`` to
   ``Bash``). A name with no entry passes through unchanged.
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

Sessions. A vendor that also imports the Claude Code settings file
(``dedupe_session_start``) can run Apothem's SessionStart command twice for one
session. :func:`first_session_start` keeps one marker per (contract, session,
source) in the per-user hook state directory and the second run is silent. The
source is part of the key because a session reuses its id across a compaction,
and the bootstrap delivers its recovery context on that firing. The marker is
consulted only for contract-routed commands: the default command line, which
Claude Code, Codex and Qwen Code run, never reads it.

Vendor sources (living docs, no immutable id), retrieved 2026-10-28 unless
marked 2026-10-27 (the refuted and confirmed claims of the design note):

* codebuddy: https://www.codebuddy.ai/docs/cli/hooks and /hooks-guide. Claude's
  shape. ``additionalContext`` is documented for SessionStart,
  UserPromptSubmit and PostToolUse; PreToolUse documents only the permission
  fields and ``modifiedInput``.
* devin (Windsurf, Devin Local): https://docs.devin.ai/cli/extensibility/hooks/overview.md.
  Claude's shape. ``additionalContext`` is documented for UserPromptSubmit,
  SessionStart and PostToolUse; tool names are lowercase.
* cursor: https://cursor.com/docs/hooks (2026-10-28), /docs/reference/third-party-hooks
  (2026-10-27). camelCase events; sessionStart reads ``{env, additional_context}``.
* copilot: https://docs.github.com/en/copilot/reference/hooks-reference. A
  camelCase event name selects camelCase stdin and a flat ``additionalContext``;
  the PascalCase spelling selects Claude-shaped stdin.
* kiro: https://kiro.dev/docs/hooks/ and /hooks/types/ (2026-10-27). Plain
  stdout joins the context for SessionStart and UserPromptSubmit only.
* trae: https://docs.trae.ai/ide/hook-configuration-reference (2026-10-27).
  Plain text is context for SessionStart and UserPromptSubmit; the tool events
  read ``hookSpecificOutput.additionalContext``.

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
    "Contract",
    "first_session_start",
    "get_contract",
    "normalise_payload",
    "run_contracted",
    "shape_output",
]

#: Output shapes. ``envelope`` is the handler's own Claude-shaped output, left
#: byte for byte as written.
ENVELOPE: Final[str] = "envelope"
PLAIN: Final[str] = "plain"
FLAT: Final[str] = "flat"
SNAKE: Final[str] = "snake"

_MARKER_MAX_AGE_SECONDS: Final[float] = 7 * 24 * 3600.0
_MARKER_SCAN_LIMIT: Final[int] = 200


@dataclass(frozen=True)
class Contract:
    """One vendor's hook contract; see the module docstring for the five parts."""

    contract_id: str
    output: str
    delivers: frozenset[str]
    events: Mapping[str, str] = field(default_factory=dict)
    tools: Mapping[str, str] = field(default_factory=dict)
    output_by_event: Mapping[str, str] = field(default_factory=dict)
    dedupe_session_start: bool = False

    def canonical_event(self, name: str) -> str:
        """Return the canonical spelling of the vendor event *name*."""
        return self.events.get(name, name)

    def canonical_tool(self, name: str) -> str:
        """Return the Claude spelling of the vendor tool *name*."""
        return self.tools.get(name, name)

    def shape_for(self, event: str) -> str:
        """Return the output shape this vendor reads for canonical *event*."""
        return self.output_by_event.get(event, self.output)


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

#: Trae reports standardized tool names; its shell tool is RunCommand.
_TRAE_TOOLS: Final[dict[str, str]] = {"RunCommand": "Bash"}

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
    "trae": Contract(
        "trae",
        ENVELOPE,
        frozenset({"SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse"}),
        tools=_TRAE_TOOLS,
        output_by_event={"SessionStart": PLAIN, "UserPromptSubmit": PLAIN},
        dedupe_session_start=True,
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
        root = _first_workspace_root(payload)
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
    shape = contract.shape_for(event)
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


def first_session_start(contract_id: str, payload: Mapping[str, object] | None) -> bool:
    """Return True the first time this (contract, session, source) starts.

    Records the start in the per-user hook state directory. Any failure to
    record returns True: a missing marker costs one repeated advisory, and a
    suppressed session start would cost the whole bootstrap.
    """
    from state_dir import hook_state_dir, session_key

    data = payload or {}
    source = session_key(data.get("source")) if _text(data.get("source")) else "start"
    name = f"{contract_id}--{session_key(data.get('session_id'))}--{source}.seen"
    try:
        directory = hook_state_dir("session-start")
    except OSError:
        return True
    try:
        descriptor = os.open(
            directory / name, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600
        )
    except FileExistsError:
        return False
    except OSError:
        return True
    os.close(descriptor)
    _purge_old_markers(directory)
    return True


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
    if (
        contract.dedupe_session_start
        and event == "SessionStart"
        and not first_session_start(contract.contract_id, payload)
    ):
        return
    try:
        text = (
            json.dumps(normalise_payload(contract, payload, event))
            if payload is not None
            else raw
        )
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
