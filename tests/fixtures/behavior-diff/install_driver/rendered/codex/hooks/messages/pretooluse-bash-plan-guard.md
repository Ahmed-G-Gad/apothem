<!-- SPDX-License-Identifier: MIT -->

Plans-Discipline write guard for Bash tool calls (companion to
`pretooluse-write-plan-guard.md`).

> Advisory: this hook reports; it does not block. Mechanical enforcement runs in CI.

This guard surfaces the Plans-Locality discipline at the shell-redirection
surface so a shell-redirected write does not bypass the Write-route guard. It
reports a redirection that would land a plan outside the sole canonical
project-local plans tree `<project-root>/.apothem/plans/` and recommends a
redirection; the operator decides. A legacy `<project-root>/.plans/` tree is no
longer canonical and is redirect-recommended to `.apothem/plans/` (operators
upgrade it via `apothem migrate-workspace`). Mechanical enforcement of
Plans-Locality runs in CI and pre-commit via the strict conformity corpus gate
(`no_global_plans_grep`), not at this tool call.

**Scope.** Fires on every PreToolUse Bash event. Scans the Bash command
string for **output-redirection patterns** that would write a file
under a global plans directory (a `.plans/` or `.apothem/plans/` directory
under a non-project root — such as `~/.claude/.plans/` or `~/.apothem/plans/`
for users on the Claude Code harness) or any other global-ecosystem path with
plan-shaped content. Applies the same redirect-required / soft-flag / allow verdict matrix
that the Write / Edit / NotebookEdit guard applies, projected onto the
shell-redirection surface. Surfaces the foundational Plans-Locality
mandate (`CLAUDE.md` Plans Discipline; spec `_spec/spec.md` §3 +
§5.5.1) at the Bash tool-call surface so shell-redirected writes do not
bypass the Write-route guard.

**Output-redirection patterns inspected.**

| Pattern class | Examples |
|---------------|----------|
| **POSIX redirect** | `cmd > path` · `cmd >> path` · `cmd 2> path` · `cmd 2>> path` · `cmd &> path` · `cmd >\| path` |
| **Heredoc emission** | `cat > path <<EOF` · `cat >> path <<'EOF'` · `tee path <<EOF` (with or without `-a`) |
| **`tee` invocations** | `cmd \| tee path` · `cmd \| tee -a path` · `cmd \| tee path1 path2` |
| **File-creation utilities** | `touch path` · `cp src path` · `mv src path` · `install -m … src path` |
| **Editor-pipe** | `printf '...' > path` · `echo '...' > path` · `python -c '...' > path` |
| **PowerShell analogs** | `Out-File -FilePath path` · `Set-Content -Path path` · `Add-Content -Path path` · `... > path` (PowerShell pipeline redirect) |

The scanner extracts every `path` argument from these patterns and
applies the same path-classification predicate as
`pretooluse-write-plan-guard.md`:

1. Resolve every extracted path to its absolute form (relative paths are
   resolved against the Bash command's working directory, falling back to
   the tool-call's `cwd` field when present).
2. Resolve the **current project root** by walking from the working
   directory to the nearest enclosing `.git/` directory; when no
   enclosing repo exists, the working directory is the project root.
3. Apply the verdict matrix (recursion-self allow / redirect-required /
   soft-flag / allow-otherwise) per the table in
   `pretooluse-write-plan-guard.md`.

**Action — redirect-required path.**

Invoke the structured-inquiry channel using the canonical Plans-Locality option-set at `rules/interactive-questions-canonical-shapes.md` §5.9.1 (the 2-option redirect-required variant; Bash-tool label form: `rewrite-redirect-to-project-plans` / `cancel`). Substitute the actual rejected path and resolved project root at invocation time. The recommended option redirects the shell-redirected write to the canonical project-local plans tree `<project-root>/.apothem/plans/`; the operator decides.

Recursion-self case: when the resolved project root IS the Apothem source repo itself (for Claude Code users this is `~/.claude/`), the redirection IS canonical. Pass through silently. The recursion case is the ONLY allowed shell-redirect path under the apothem-source-repo plans tree `.apothem/plans/`.

**Action — soft-flag path.**

Invoke the structured-inquiry channel using the canonical Plans-Locality option-set at `rules/interactive-questions-canonical-shapes.md` §5.9.2 (soft-flag 3-option variant; Bash-tool label form: `rewrite-redirect-to-project-plans` / `run-as-proposed` / `cancel`). Substitute the actual flagged path at invocation time.

**Action — allow path.**

When every extracted path is allow-class (the canonical project-local plans
tree `<project-root>/.apothem/plans/`, or any non-plan-shaped path outside the
protected classes, or no redirection at all), pass through silently. The vast
majority of Bash commands fall into this class.

**Heuristic robustness.**

- Quoted paths are unwrapped (`> "path with spaces.md"` → `path with spaces.md`).
- Variable expansions are best-effort (`> $HOME/.plans/x.md` resolves
  `$HOME` against the tool-call's environment block when present;
  otherwise treated as a soft-flag candidate pending operator review).
- Glob patterns are inspected as literal paths (a redirect target is a
  single file, not a glob expansion site).
- Subshell-piped commands (`(cmd1; cmd2) > path`) are inspected at the
  outer redirect.
- Multi-statement commands separated by `;` / `&&` / `||` are inspected
  per-statement.

**Fail-disposition.** Two layers govern failure. (a) The Python dispatcher at
`hooks/dispatch.py` is fail-open: a hook error (parse failure on the Bash
command, path normalization exception, project-root resolution failure, Python
exception inside the predicate) converts to a structured failure envelope on
stdout and the Bash call proceeds, so a harness error never silently blocks the
tool call. (b) The assistant's interpretation of this context is fail-closed on
a detected verdict: when the scan returns redirect-required or soft-flag, the
directive is to surface the redirection via the structured-inquiry channel and
let the operator decide before re-issuing the command. The two layers are
non-redundant: the dispatcher protects the runtime, this context protects the
Plans-Locality discipline. The Plans-Locality invariant itself is enforced
mechanically in CI and pre-commit via the strict conformity corpus gate
(`no_global_plans_grep`).

## Bindings (§0.j five-direction)

- **Drives →** The redirect recommendation for a shell redirection that would land a plan outside `<project-root>/.apothem/plans/`.
- **Established by ↑** The PreToolUse Bash registration in `hooks/hooks.json` and the harness settings templates. The Plans Discipline section of `AGENTS.md`. `conformity/no_global_plans_grep.py` (the CI-side enforcement this guard surfaces early).
- **Cross-bound with ↔** `rules/interactive-questions-canonical-shapes.md` (the Plans-Discipline write-guard option sets this guard renders). `hooks/messages/pretooluse-write-plan-guard.md` (the same guard on the file-write tools). `hooks/messages/pretooluse-bash.md` (the other Bash-surface guard).
