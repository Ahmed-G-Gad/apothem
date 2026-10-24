<!-- SPDX-License-Identifier: MIT -->

## Mode: `--quick` (Lightweight Plan-Local Write)

`--quick` is the lightweight path codified by D3 — `/plan-spec` accepts the project-local plan-write surface that would otherwise have justified a separate `/plan` command. Forge mode (default, no `--quick`) and `--quick` mode are mutually exclusive: one per invocation. Forge mode produces a spec-grade `_spec/spec.md` after multi-phase elicitation; `--quick` mode produces a single project-local lightweight plan file in seconds.

### Behavior

1. **Resolve the current project root.** Walk upward from `pwd` to the nearest `.git/` parent; that ancestor is the project root. If no `.git/` exists anywhere up to the filesystem root, halt with structured inquiry per `rules/interactive-questions.md` §3 — `question`: `No .git directory found above the working directory. How should the lightweight plan-spec write proceed?`; `header`: `No .git found`; `multiSelect: false`; option set:
   - `Use this directory`:
     rationale: Treat the current `pwd` as the project root; the plan file lands at `<pwd>/.apothem/plans/<filename>.md`.
     recommendation: acceptable
     default-pointer: `Let me cd first` — safer because the operator may have invoked from a parent directory.
   - `Let me cd first (Recommended)`:
     rationale: Cancel and let the operator navigate to the actual project root, then re-invoke.
     recommendation: recommended — cites class 6 observed-state: most projects keep `.git/` at a deeper subtree than `pwd`; cd-then-retry preserves operator intent without silent assumption.
     default-pointer: `Let me cd first` — safe because cancellation is reversible.
   - `Create a new project here`:
     rationale: Run `git init` at `pwd` and proceed with the plan-write at the freshly-initialized project root.
     recommendation: acceptable
     default-pointer: `Let me cd first` — `git init` is reversible (`rm -rf .git`) but creates filesystem state the operator may not have intended.
   - `Cancel`:
     rationale: Abort the `/plan-spec --quick` invocation entirely; no filesystem effect.
     recommendation: acceptable
     default-pointer: `Let me cd first` — cancel is fully reversible.
2. **Refuse global-ecosystem paths.** If the resolved project root is any harness config root (e.g., `~/.claude/` on the claude_code harness) or any other global-ecosystem location (`~/.config/`, `/etc/`, vendored language-runtime trees), halt with an explicit refusal — `--quick` writes are project-local by design; global locations require explicit operator action through a separate path (`/plan-generate` for plan-suite work; direct file authoring for global-config work).
3. **Ensure `<project-root>/.apothem/plans/` exists.** Create the directory if absent. Verify `<project-root>/.gitignore` carries the canonical snippet (`.apothem/plans/` ignore plus a header comment naming the rationale); append the snippet with a header comment if absent.
4. **Compose the destination filename.** The pattern is `<YYYY-MM-DD>--<kebab-slug>.md` — `YYYY-MM-DD` is today's UTC date and `<kebab-slug>` is the operator-supplied slug, validated as kebab-case (`^[a-z0-9]+(-[a-z0-9]+)*$`).
5. **Write the plan file with frontmatter.** Required fields: `name` (the slug), `created` (ISO-8601 timestamp), `project` (resolved project-root absolute path), `status` (`draft`), `tags` (array from `--tag` invocations; empty array if none). Validate the frontmatter inline against this field list (the JSON Schema at `src/apothem/schemas/plan.schema.json` is a forward-reference at this phase; inline validation against this field list is authoritative until the schema lands).
6. **Banner-exempt.** Do NOT inject the authorship banner — plan files are exempt per the `.apothem/**` exception class at `src/apothem/schemas/header-exceptions.txt`.
7. **Print metadata-only output.** Emit four lines: absolute destination path, resolved project root, chosen filename, one-line confirmation. Do NOT echo the plan body, Forge appendices, or any pipeline state — `--quick` is a single-shot write.

### Mutual Exclusivity

`--quick` is mutually exclusive with `--refine-existing` and with every six-phase Forge output (`_spec/spec.md`, `_inputs/forge.md`, the five appendices, the Handoff Manifest). When `--quick` is supplied, the Forge workflow at `## Workflow — Six Transformation Phases` does NOT execute; the command writes the single plan file and exits. When neither `--quick` nor a Forge-mode flag is supplied, the default Forge workflow executes per the six-phase protocol below.
