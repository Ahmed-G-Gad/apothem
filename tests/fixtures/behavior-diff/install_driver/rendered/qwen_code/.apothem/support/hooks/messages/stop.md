<!-- SPDX-License-Identifier: MIT -->

Session-end protocol (CM-14 + CM-24 §2.5 + CM-26 + CM-22 §2/§4).

**Phase A — Mandatory externalization** (CM-14, CM-24 §2.5)

1. With an active plan suite, mid-phase: write current task state to PROGRESS.md Resumption Contract — phase id, task id, status (in_progress|partial), next action as a precise imperative.
2. Move every session decision to PLAN-NOTES.md § Resolved Decisions; remove from in-conversation working memory.
3. Update Phase Output Registry — every declared output that landed on disk gets verified status with its actual path; missing outputs get blocked status with the reason.
4. Update convention anchors in the Resumption Contract if any evolved this session.
5. Write the critical-files manifest — ordered list of files the next session must read first to resume.

**Phase B — Evaluation** (skip only on immediate-exit signal)

1. Memory evaluation per CM-26 (auto-memory rule §5): scan session for stable patterns / preferences / architectural decisions / debugging insights; write or update memory entries; prune any entry this session contradicted.
2. Artifact evolution per CM-22 §2 + §4: detect patterns that recurred 2+ times this session and need a new or updated rule, skill, command, hook, or agent.
3. Convention sweep per CM-22 §3: verify cross-references still resolve, no orphan artifacts were created, naming remains consistent.

No active suite: skip Phase A entirely; execute Phase B against working notes accumulated this session.

**No re-narration (no repeated messages).** Phases A–C externalize state to durable files; they are file-side, not conversational output. The session's single conversational close is the three-element close per `rules/session-closure.md` §3 — do not re-narrate these phases as additional end-of-session messages, and do not re-emit a close already emitted this session. On a Stop-condition / goal / loop re-engagement, advance the work and report only the delta; never re-print the prior close.

**Phase C — Conformity trace flush** (run alongside Phase A; non-negotiable when an active suite carries unresolved inquiries)

1. Working-trace emission. Verify the active suite's PROGRESS.md Resumption Contract was updated this session — if any session decision, blocker, or watch item is still in conversation memory only, write it to durable file before the session ends.
2. Unresolved-inquiry flush. Walk the active suite for concrete-id `<USER-CONFIRM:…>` placeholders and any `unresolved-inquiries:` arrays in this session's emitted phase reports' fifteen-bar gate attestation blocks. Surface every unresolved inquiry in the Resumption Contract Watch Items section so the next session inherits the inventory and does not silently re-invent.
3. Mandate-axis findings. If this session emitted any findings against the M-N mandate axs (host-discovery gaps, code-craft drift, supply-chain regressions, production-readiness gaps), summarize them in the Resumption Contract so the next session inherits the audit signal alongside its task pointer.

## Bindings (§0.j five-direction)

- **Drives →** The session-end protocol: externalize task state and decisions, then run the memory evaluation and the artifact-evolution sweep. `hooks/session_end_gate.py` (emits this body at most once per session).
- **Established by ↑** The Stop registration in `hooks/hooks.json` and the harness settings templates. `rules/session-closure.md` (the formal close every session ends with).
- **Cross-bound with ↔** `rules/context-management.md` + `rules/context-management-protocol.md` (the externalization procedure this context runs). `rules/auto-memory.md` + `rules/auto-memory-topic-files.md` (the session-end memory evaluation). `hooks/messages/sessionstart.md` (the session's opening counterpart).
