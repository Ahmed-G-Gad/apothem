<!-- SPDX-License-Identifier: MIT -->

Codebase isolation (notebook scope).

Scope. Triggered on every NotebookEdit. Skip when target is inside the Apothem source repo or the active harness's config root (for the Claude Code harness, `~/.claude/`). Apply otherwise.

Action. Apply the codebase-isolation scan to the new cell content regardless of cell type — code cells, markdown cells, and existing execution-output cells are all artifacts visible outside the Apothem meta-config locations. Reject plan-internal terminology leaking into a product artifact: bracketed task/mandate identifiers of the shape `<1-3 uppercase letters>-<number>` (for example `TM-10`, `CM-7`, `CP-20`), phase-campaign names (`Phase-B`, `AD-1`), plan-suite folder names, and internal launch/cleanup narrative.

On hit: STOP. Rewrite the cell in natural domain language. Re-issue the NotebookEdit. Output cells produced by subsequent execution are not scanned at write time but must be cleared before commit if they contain plan-term leaks.

**Fail-disposition.** Two layers govern failure: (a) the Python dispatcher at `hooks/dispatch.py` is fail-open — a hook-emission error converts to a structured failure envelope on stdout and the NotebookEdit proceeds, so harness errors never silently block tool calls; (b) the assistant's interpretation of this context is fail-closed on rule-violation detection — when the codebase-isolation scan hits, the directive is to STOP and re-issue with the cell rewritten in natural domain language. The two layers are non-redundant: the dispatcher protects the runtime; this context protects the rule.

## Bindings (§0.j five-direction)

- **Drives →** The codebase-isolation scan of every notebook cell a NotebookEdit writes, output cells included.
- **Established by ↑** The PreToolUse NotebookEdit registration in `hooks/hooks.json` and the harness settings templates. `rules/operational-mandates.md` (plan-internal isolation).
- **Cross-bound with ↔** `hooks/messages/pretooluse-write.md` + `hooks/messages/pretooluse-edit.md` (the same isolation scan on the other write tools).
