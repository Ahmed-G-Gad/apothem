<!-- SPDX-License-Identifier: MIT -->

Proactive-compaction tracker for PostToolUse tool calls.

> Advisory: this hook reports; it never blocks. A PostToolUse hook cannot block the tool call that already ran.

This handler mechanically operationalizes the CM-19 proactive-compaction
triggers (`rules/context-management-protocol.md` §2): the ~18-tool-call window
and the large-cumulative-emission band. The dispatcher routes this message
basename to the per-session activity tracker (`hooks/proactive_compaction_tracker.py`)
rather than emitting this static context — the tracker maintains lightweight
per-session counters keyed off the `session_id` field of the hook stdin payload
and surfaces a concise proactive-compaction advisory once a threshold crosses,
then resets the counters (anti-spam back-off) so it does not fire on every
subsequent tool call.

**Scope.** Fires on every PostToolUse tool call (empty matcher — all tools).
Per session, it tracks the tool-call count and a cumulative tool-output-size
estimate since the last advisory.

**Thresholds (configurable).**

- `APOTHEM_PROACTIVE_COMPACTION_TOOL_THRESHOLD` (default `18`) — tool calls
  since the last advisory; mirrors the §2 "~18 tool calls" trigger.
- `APOTHEM_PROACTIVE_COMPACTION_OUTPUT_THRESHOLD` (default `20000`) — cumulative
  tool-output bytes since the last advisory; a mechanical proxy for the §2
  "500-line emission" / heavy-read band (~20 KB). A non-positive or
  unparseable override falls back to the default, so a typo can never silently
  disable the tracker.

**Advisory shape.** When a threshold crosses, the tracker emits a
`systemMessage` that suggests compaction to the operator, plus
`additionalContext` asking the assistant to externalize in-conversation state
(PROGRESS.md Resumption Contract + PLAN-NOTES.md, or a scratch file under the
active harness's config root when no suite is active). Compaction stays the
operator's call. The advisory fires at most twice per session, and
`APOTHEM_PROACTIVE_COMPACTION_ENABLED=0` silences it.

**State.** Per-session counters live in the per-user hook state directory
(`<state-dir>/proactive-compaction/<session>.json`, mode `0700`; the directory
resolution order is in the hooks reference) — never inside the repository's
tracked tree. A missing, empty, or corrupt counter file degrades to
"start counting again", never a crash.

**Fail-disposition.** Fail-open at every layer. The Python dispatcher at
`hooks/dispatch.py` converts any handler error to a structured failure envelope
on stdout; the tracker's own `main` swallows every exception and emits an empty
envelope. A tracker fault therefore costs nothing — never a blocked or stalled
tool call.

## Bindings (§0.j five-direction)

- **Drives →** `hooks/proactive_compaction_tracker.py` (the dispatcher routes this basename to the per-session tracker, which emits the advisory once a threshold crosses).
- **Established by ↑** The PostToolUse registration in `hooks/hooks.json` and the harness settings templates. `rules/context-management-protocol.md` §2 (the proactive-compaction triggers the tracker measures).
- **Cross-bound with ↔** `hooks/messages/precompact.md` (the externalization the advisory recommends before compacting).
