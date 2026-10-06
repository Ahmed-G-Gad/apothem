<!-- SPDX-License-Identifier: MIT -->

Session-start conformity posture.

**Working-trace surface.** The most-recent plan suite's PROGRESS.md Resumption Contract is the authoritative pickup point. Read its Watch Items and Blockers sections before any substantive action. The Critical Files Manifest is the deterministic next-session bootstrap order — read those files first, in that order.

**Unresolved-inquiry enumeration.** Before emitting any artifact of meaningful scope, walk the active suite for unresolved `<USER-CONFIRM:…>` placeholders and any `unresolved-inquiries:` arrays in prior phase reports' fifteen-bar gate attestation blocks. Surface every one — do not silently re-invent the answer. Required-category placeholders (identity / scope / security / public-surface naming) block emission until resolved through the canonical inquiry channel; optional-category placeholders fall back to the recommended option per the option-annotation discipline and record the fallback as a finding.

**Host-discovery freshness.** Convention discovery (formatter, linter, test framework, CI provider, branch strategy, commit-message convention) runs on-demand per the host-discovery rule, not at session start. The session-start posture only declares that discovery is the path; the actual walk fires when the first artifact-emission decision needs it.

**Pre-emission gate awareness.** Every host-project artifact emission of meaningful scope passes through the fifteen-bar pre-emission gate before it leaves the agent's hands. The gate's mechanical bars (M2, M5, M7, M8, M10, M13, M15) are operationalized as PreToolUse hooks at `apothem/conformity/*_grep.py` orchestrated by `apothem/conformity/gate.py`; the reasoned bars (M1, M3, M6, M9, M11, M12, M14) are evaluated by the operating agent and recorded in the attestation block.

**Trivial-vs-non-trivial threshold.** The threshold separating trivial from non-trivial work — non-trivial work triggers the agile sprint apparatus, the per-sub-phase reporting, and the full pre-emission gate — is the line-count + scope hybrid: a change is trivial when it is a single-file edit of ≤ 5 lines AND introduces no public-API surface change AND no behavioral shift. Anything else is non-trivial. Project-scope CLAUDE.md may override per host discipline.

**Fail-disposition.** Fail-open at every layer. The Python dispatcher at `hooks/dispatch.py` converts any exception in `session_start_bootstrap.main()` to a structured failure envelope on stdout (per the dispatcher's `_emit_failure` contract); the session itself proceeds. A bootstrap-script error degrades the operator's session-start summary but never blocks the session — there is no recovery path that would benefit from blocking. If the operator notices a missing posture block, the recovery is to re-invoke the bootstrap manually or inspect `hooks/session_start_bootstrap.py` for the diagnostic stack trace.

## Bindings (§0.j five-direction)

- **Drives →** The session-start posture: read the active suite's pickup point first, surface every unresolved inquiry before emitting, and route emissions through the pre-emission gate. `hooks/session_start_bootstrap.py` (the handler the dispatcher routes this event to).
- **Established by ↑** The SessionStart registration in `hooks/hooks.json` and the harness settings templates. `rules/context-management.md` (the blind bootstrap this posture opens). `rules/pre-emission-gate.md` (the gate every emission passes).
- **Cross-bound with ↔** `hooks/messages/stop.md` (the session's closing counterpart). `hooks/messages/postcompact.md` (the same bootstrap, re-run after compaction).
