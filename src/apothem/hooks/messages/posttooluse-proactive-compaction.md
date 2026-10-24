<!-- SPDX-License-Identifier: MIT -->

Proactive-compaction tracker for PostToolUse tool calls.

> Advisory: this hook reports; it never blocks. A PostToolUse hook cannot block the tool call that already ran.

This handler mechanically operationalizes the proactive-compaction triggers
(`rules/context-management-protocol.md` §2). The dispatcher routes this message
basename to the per-session tracker (`hooks/proactive_compaction_tracker.py`)
rather than emitting this static context. Claude Code runs it in the background
(`async`), so it never delays a tool result; its advisory arrives on the next
turn.

**Signal.** The tracker reads the newest main-thread assistant `usage` record
from the tail of the payload's `transcript_path`: input plus cache-read plus
cache-creation tokens is the context the model last received. A sharp drop in
that size marks a compaction and restarts the advisory budget.

**Policy.** With `APOTHEM_CONTEXT_WINDOW_TOKENS` (or Claude Code's
`CLAUDE_CODE_AUTO_COMPACT_WINDOW`) set, the first advisory fires at 50% of the
window and the second at 75%; without a known window, at 120,000 and 250,000
tokens. A session resumed already past the second mark gets the second advisory
directly, and that one ends the cycle's budget.

**Fallback.** When no context size is measurable (a harness without a
transcript, or no usage record yet) the tracker counts activity since the last
advisory instead:

- `APOTHEM_PROACTIVE_COMPACTION_TOOL_THRESHOLD` (default `18`) — tool calls
  since the last advisory; mirrors the "~18 tool calls" trigger.
- `APOTHEM_PROACTIVE_COMPACTION_OUTPUT_THRESHOLD` (default `20000`) — cumulative
  tool-output bytes since the last advisory, counted only after three calls. A
  non-positive or unparseable override falls back to the default, so a typo can
  never silently disable the tracker.

**Advisory shape.** The tracker emits a `systemMessage` for the operator (the
session is growing; at the second mark, compact or start a fresh session) plus
`additionalContext` asking the assistant to externalize in-conversation state
(the active plan's PROGRESS.md Resumption Contract and PLAN-NOTES.md, or a short
plan under `<project-root>/.apothem/plans/` when no suite is active). Compaction
stays the operator's call, so the assistant-facing text never asks the assistant
to compact. At most two advisories fire per compaction cycle, and
`APOTHEM_PROACTIVE_COMPACTION_ENABLED=0` silences them.

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
