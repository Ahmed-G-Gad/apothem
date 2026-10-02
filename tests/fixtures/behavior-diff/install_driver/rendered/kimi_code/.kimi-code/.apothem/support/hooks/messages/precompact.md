<!-- SPDX-License-Identifier: MIT -->

Pre-compaction protocol (CM-24 §2.3). Externalize all in-conversation state BEFORE the harness compresses context.

With an active plan suite — execute IN ORDER (all mandatory):

1. Verify PROGRESS.md Resumption Contract reflects current state — phase, task, next action, convention anchors, critical-files manifest. Update any stale fields.
2. Verify every decision made this session is recorded in PLAN-NOTES.md § Resolved Decisions.
3. Verify Phase Output Registry reflects every artifact produced this phase with verified status (and actual path).
4. Identify any state that exists ONLY in conversation (not in any durable file). Externalize now — task state → PROGRESS.md, decisions → PLAN-NOTES.md, working notes → scratch file under the active suite's `_inputs/` directory (or the active harness's config root when no suite is active).

No active suite: externalize accumulated session decisions and working notes to a scratch file under the active harness's config root.

Gate. If externalization is incomplete, complete it BEFORE compaction proceeds — compaction with state still in conversation loses that state.

## Bindings (§0.j five-direction)

- **Drives →** The externalization of every in-conversation state to durable files before the harness compresses context.
- **Established by ↑** The PreCompact registration in `hooks/hooks.json` and the harness settings templates.
- **Cross-bound with ↔** `rules/context-management.md` + `rules/context-management-protocol.md` (the compaction discipline this context runs). `hooks/messages/postcompact.md` (restores what this context externalized). `hooks/messages/posttooluse-proactive-compaction.md` (the tracker whose advisory recommends this externalization before compacting).
