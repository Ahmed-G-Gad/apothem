<!-- SPDX-License-Identifier: MIT -->

Plans-Discipline write guard for Write / Edit / NotebookEdit tool calls.

> Advisory: this hook reports; it does not block. Mechanical enforcement runs in CI.

This guard surfaces the Plans-Locality discipline: planning artifacts live at
the sole canonical project-local plans tree `<project-root>/.apothem/plans/` —
never at the active harness's config root and never at any other global
location. A legacy `<project-root>/.plans/` tree is no longer canonical;
operators upgrade it via `apothem migrate-workspace`. It reports a write that
would land a plan outside the canonical tree and recommends a redirection; the
operator decides. Mechanical enforcement of Plans-Locality runs in CI and
pre-commit via the strict conformity corpus gate (`no_global_plans_grep`), not
at this tool call.

**Scope.** Fires when a write-capable tool call (Write, Edit, NotebookEdit)
targets a path under one of the protected plans-discipline regions, OR targets
a non-canonical plans path with plan-shaped content. Enforces the
foundational Plans-Locality mandate: planning artifacts live at the sole
canonical project-local plans tree `<project-root>/.apothem/plans/`, never at
the active harness's config root and never at any other global location (per
`CLAUDE.md` Plans Discipline and the suite-locality and operator-authorship
contract).

**Decision predicate.**

1. Resolve the **target path** to its absolute form.
2. Resolve the **current project root** by walking from the working directory
   to the nearest enclosing `.git/` directory; when no enclosing repo exists,
   the current working directory is the project root.
3. Apply the verdict matrix below.

In the conditions below, the **canonical project-local plans tree** is the sole
location `<project-root>/.apothem/plans/` (the shared Apothem working
directory's plans child). A legacy `<project-root>/.plans/` tree is no longer
canonical and is redirect-recommended to `.apothem/plans/`. A **global plans
location** is a `.plans/` OR `.apothem/plans/` directory under a root that is
NOT the resolved project root (a harness-config root such as `~/.claude/`, the
user home such as `~/.apothem/plans/`, or any other non-project location).

| Case | Condition | Verdict |
|------|-----------|---------|
| **Project-local (allow)** | Target path is under the resolved project's canonical plans tree `<project-root>/.apothem/plans/` | **Allow** — the canonical project-local plans location |
| **Legacy-local (redirect-recommended)** | Target path is under the resolved project's legacy `<project-root>/.plans/` tree | **Redirect-recommended** — surface a structured inquiry recommending redirection to `<project-root>/.apothem/plans/` (run `apothem migrate-workspace` to upgrade the legacy tree) |
| **Recursion-self (allow)** | Resolved project root IS the Apothem source repo itself (case-insensitive on Windows; for Claude Code users that working tree is `~/.claude/`) AND target path is under the apothem-source-repo canonical plans tree `.apothem/plans/` | **Allow** — the working tree IS the Apothem source repo; its own plans tree is the canonical destination for this project |
| **Redirect-required** | Target path is under a global plans location (a harness-config-root `.plans/` or `.apothem/plans/` directory — e.g., `~/.claude/.plans/`, `~/.claude/<anything>/.plans/`, `~/.apothem/plans/` — for the Claude Code harness) AND project root is NOT the Apothem source repo | **Redirect-required** — surface a structured inquiry recommending redirection to the project-local plans tree |
| **Soft-flag** | Target path is in another global-ecosystem location (`~/Desktop`, `~/Downloads`, `~/Documents`, `~/`, OR any path outside the resolved project root) AND filename matches `*plan*.md`, `*notes*.md`, `*draft*.md` (case-insensitive) OR proposed content carries plan-shaped frontmatter (`name:`, `phases:`, `master-plan:`, `phase-id:`) | **Soft-flag** — surface a structured inquiry proposing redirection |
| **Allow** | Any other write | **Allow** unchanged |

**Action — redirect-required path.**

Invoke the structured-inquiry channel using the canonical Plans-Locality option-set at `rules/interactive-questions-canonical-shapes.md` §5.9.1 (the 2-option redirect-required variant). Substitute the actual rejected path and resolved project root at invocation time. The recommended option redirects the write to the canonical project-local plans tree `<project-root>/.apothem/plans/`; the operator decides.

Recursion-self case: when the resolved project root IS the Apothem source repo itself (for Claude Code users that working tree is `~/.claude/`), the write IS canonical. Pass through silently with no structured inquiry. The recursion case is the ONLY allowed write path under the apothem-source-repo plans tree `.apothem/plans/`.

**Action — soft-flag path.**

Invoke the structured-inquiry channel using the canonical Plans-Locality option-set at `rules/interactive-questions-canonical-shapes.md` §5.9.2 (soft-flag 3-option variant). Substitute the actual flagged path at invocation time.

**Fail-disposition.** Two layers govern failure. (a) The Python dispatcher at
`hooks/dispatch.py` is fail-open: a hook error (project-root resolution failure,
path normalization exception, Python exception inside the predicate) converts to
a structured failure envelope on stdout and the write proceeds, so a harness
error never silently blocks the tool call. (b) The assistant's interpretation of
this context is fail-closed on a detected verdict: when the predicate returns
redirect-required or soft-flag, the directive is to surface the redirection via
the structured-inquiry channel and let the operator decide before re-issuing the
write. The two layers are non-redundant: the dispatcher protects the runtime,
this context protects the Plans-Locality discipline. The Plans-Locality
invariant itself is enforced mechanically in CI and pre-commit via the strict
conformity corpus gate (`no_global_plans_grep`).
