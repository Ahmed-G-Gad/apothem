<!-- SPDX-License-Identifier: MIT -->

Codebase isolation (Edit scope).

Scope. Triggered on every Edit. Skip when target is inside the Apothem source repo or the active harness's config root (for the Claude Code harness, `~/.claude/`). Apply otherwise.

Action. Scan ONLY the `new_string` (Edit is partial; pre-existing violations elsewhere in the file are out of scope unless this Edit touches them) for plan-internal terminology leaking into a product artifact: bracketed task/mandate identifiers of the shape `<1-3 uppercase letters>-<number>` (for example `TM-10`, `CM-7`, `CP-20`), phase-campaign names (`Phase-B`, `AD-1`), plan-suite folder names, and internal launch/cleanup narrative.

On hit: STOP. Rewrite `new_string` in natural domain language. Re-issue the Edit.

Always-on rule body budget. When the Edit target matches `rules/*.md` and the file's frontmatter declares `alwaysApply: true` AND `pathFilter:` empty, the post-Edit body's substantive-token count must satisfy the 500-token ceiling per `rules/token-budget-discipline.md`. The conformity-gate orchestrator runs `conformity/always_on_budget_grep.py` and reports `over_budget` when the ceiling is exceeded. On `over_budget: true`: STOP, decompose along a path-filtered seam into a companion sub-rule, trim the parent body, re-issue.

Scratch-convention path check.

Trigger. Every Edit.

Action. Examine the target `file_path` against the scratch-convention discipline at `rules/context-management-scratch.md` §1 (scratch-file naming + closed-purpose vocabulary) and §2 (Plan-Workflow Directories + suite-locality invariant). REJECT an Edit whose target violates the closed-purpose vocabulary, the disjoint-vocabulary rule, or the suite-locality invariant; ACCEPT otherwise. On a REJECT: STOP and re-issue the Edit at the corrected target per the rule's recovery clause.

Non-matching paths: no action. The scratch-convention check is scoped to the `_inputs/` and `_spec/` directory patterns defined at `rules/context-management-scratch.md` §1–§2 and does not interact with other path classes.

**Fail-disposition.** Two layers govern failure. (a) The Python dispatcher at `hooks/dispatch.py` is fail-open: a hook-emission error converts to a structured failure envelope on stdout and the Edit proceeds, so a harness error never silently blocks the tool call. (b) The assistant's interpretation of this context is fail-closed on a detected violation: when the codebase-isolation scan, an over-budget body, or a scratch-path REJECT class is hit, the directive is to STOP and re-issue the Edit corrected. The two layers are non-redundant: the dispatcher protects the runtime, this context protects the rule. Mechanical enforcement runs in CI and pre-commit via the strict conformity corpus gate.
