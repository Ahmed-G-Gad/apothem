<!-- SPDX-License-Identifier: MIT -->

Codebase isolation + frontmatter compliance.

Scope. Triggered on every Write. Skip the codebase-isolation scan when `target` is inside the Apothem source repo or the active harness's config root (for the Claude Code harness, `~/.claude/`) — those locations are the ecosystem meta-config and are allowed to reference plan terms. Apply the scan otherwise.

Codebase-isolation scan. Reject content that leaks plan-internal terminology into a product artifact: bracketed task/mandate identifiers of the shape `<1-3 uppercase letters>-<number>` (for example `TM-10`, `CM-7`, `CP-20`), phase-campaign names (`Phase-B`, `AD-1`), plan-suite folder names, and internal launch/cleanup narrative. On hit: STOP. Rewrite the offending passage in natural domain language and re-issue the Write — do not silently strip the term, since the surrounding sentence binds to the term and breaks when the term is excised without restructuring.

Frontmatter compliance. `rules/*.md` requires a `description` field. `skills/*/SKILL.md`, `agents/*.md`, and `commands/*.md` require both `name` and `description` fields. Each field must be a non-empty string. On missing or empty fields: STOP, add them, re-issue.

Always-on rule body budget. When the Write target matches `rules/*.md` and the file's frontmatter declares `alwaysApply: true` AND `pathFilter:` empty, the substantive-token count of the body must satisfy the 500-token ceiling per `rules/token-budget-discipline.md`. The conformity-gate orchestrator runs `conformity/always_on_budget_grep.py` and reports the per-file count plus an `over_budget` flag. On `over_budget: true`: STOP, decompose along a path-filtered seam (companion sub-rule pattern; precedents at `rules/context-management.md` ↔ `rules/context-management-scratch.md`), trim the parent body, re-issue.

Scratch-convention path check.

Trigger. Every Write.

Action. Examine the target `file_path` against the scratch-convention discipline at `rules/context-management-scratch.md` §1 (scratch-file naming + closed-purpose vocabulary) and §2 (Plan-Workflow Directories + suite-locality invariant). REJECT a Write whose target violates the closed-purpose vocabulary, the disjoint-vocabulary rule, or the suite-locality invariant; ACCEPT otherwise. On a REJECT: STOP and re-issue the Write at the corrected target per the rule's recovery clause.

Non-matching paths (anything that is not a scratch or prose path): no action. The scratch-convention check is scoped to the `_inputs/` and `_spec/` directory patterns defined at `rules/context-management-scratch.md` §1–§2 and does not interact with other path classes.

**Fail-disposition.** Two layers govern failure. (a) The Python dispatcher at `hooks/dispatch.py` is fail-open: a hook-emission error converts to a structured failure envelope on stdout and the Write proceeds, so a harness error never silently blocks the tool call. (b) The assistant's interpretation of this context is fail-closed on a detected violation: when the codebase-isolation scan, a frontmatter gap, an over-budget body, or a scratch-path REJECT class is hit, the directive is to STOP and re-issue the Write corrected. The two layers are non-redundant: the dispatcher protects the runtime, this context protects the rule. Mechanical enforcement runs in CI and pre-commit via the strict conformity corpus gate.

## Bindings (§0.j five-direction)

- **Drives →** The codebase-isolation scan, the frontmatter and always-on budget checks, and the scratch path check on every Write. `conformity/always_on_budget_grep.py` (the budget measurement it relies on).
- **Established by ↑** The PreToolUse Write registration in `hooks/hooks.json` and the harness settings templates. `rules/operational-mandates.md` (plan-internal isolation). `rules/token-budget-discipline.md` (the always-on budget).
- **Cross-bound with ↔** `rules/context-management-scratch.md` (cites this context as the real-time check of its scratch path-shape rules on Write). `hooks/messages/pretooluse-edit.md` + `hooks/messages/pretooluse-notebookedit.md` (the same isolation scan on the other write tools).
