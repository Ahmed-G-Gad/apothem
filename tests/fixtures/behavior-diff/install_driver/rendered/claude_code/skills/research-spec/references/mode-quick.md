<!-- SPDX-License-Identifier: MIT -->

## Mode: `--quick` (Lightweight Research Brief)

`--quick` is the lightweight path: `/research-spec` writes a single project-local research brief in seconds, bypassing the full framing workflow. Default mode (invocation without `--quick`) and `--quick` mode are mutually exclusive per invocation.

### Behavior

1. **Resolve the current project root.** Walk upward from `pwd` to the nearest `.git/` parent; that ancestor is the project root. When no `.git/` is found on the path to the filesystem root, halt with structured inquiry per `rules/interactive-questions.md` §3 (`question`: how to proceed; options `Use this directory` / `Let me cd first (Recommended)` / `Create a new project here` / `Cancel`, each carrying the three-segment body).
2. **Refuse global-ecosystem paths.** When the resolved root is any harness's config root (e.g., `~/.claude/` for the claude_code harness) or any other global-ecosystem location (`~/.config/`, `/etc/`, vendored language-runtime trees), halt with an explicit refusal — `--quick` writes are project-local by design.
3. **Ensure `<project-root>/.apothem/plans/` exists.** Create the directory when absent. Verify `<project-root>/.gitignore` carries the canonical `.apothem/plans/` ignore snippet; append the snippet with a header comment when absent.
4. **Compose the destination filename.** The pattern is `<YYYY-MM-DD>--<kebab-slug>.md` where `YYYY-MM-DD` is today's UTC date and `<kebab-slug>` is the operator-supplied slug validated as kebab-case (`^[a-z0-9]+(-[a-z0-9]+)*$`).
5. **Write the lightweight research brief.** Frontmatter required fields: `name` (the slug), `created` (ISO-8601 timestamp), `project` (the resolved project root absolute path), `status` (`draft`), `tags` (array from `--tag` invocations; empty array when none supplied). Body carries the question, one or more falsifiable hypotheses with null forms (R3), a short scope statement, and the success metric. The brief is a single-shot artifact, not the six-section spec.
6. **Banner-exempt.** Do NOT inject the authorship banner — research-brief files are exempt per the `.apothem/**` exception class.
7. **Print metadata-only output.** Emit the absolute destination path, the resolved project root, the chosen filename, and a one-line confirmation. Do NOT echo the brief body or any pipeline state.

### Mutual Exclusivity

`--quick` is mutually exclusive with `--refine-existing` and with the full framing workflow's output (`_spec/research-spec.md`, the Handoff Manifest). When `--quick` is supplied, the framing workflow does NOT execute; the stage writes the single brief and exits. When neither `--quick` nor a default-mode flag is supplied, the framing workflow executes per the phases below.
