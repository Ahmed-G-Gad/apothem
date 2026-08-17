<!-- SPDX-License-Identifier: MIT -->

Post-compaction Blind Bootstrap (CM-24 §6.2). Restore working state from durable files; conversation context is now compressed.

Read sequence — execute IN ORDER:

1. MEMORY.md (project tier, then global) and every topic file referenced in the project index.
2. With an active plan suite: PROGRESS.md Resumption Contract — phase/task status, next action, convention anchors, blockers, watch items, critical-files manifest.
3. Each file in the critical-files manifest, in the listed order. Skip any path already covered by a Resumption Contract snapshot to avoid redundant context spend.
4. The active phase file (`phases/NN-topic/PHASE.md`) — scope, tasks, inputs, outputs, verification criteria.
5. Adopt the convention anchors verbatim from the Resumption Contract; do NOT re-derive them from the preamble.
6. Verify alignment. The user's most recent request must be fully addressable from the loaded state. If it references files, decisions, or context NOT in the loaded set, read those files BEFORE proceeding. If the request contradicts loaded state, surface the contradiction to the user — never silently override durable state.

No active suite: step 1, then re-read any files referenced in the user's most recent request, then step 6.
