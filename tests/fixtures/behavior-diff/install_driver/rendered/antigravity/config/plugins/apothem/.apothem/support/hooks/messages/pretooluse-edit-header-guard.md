<!-- SPDX-License-Identifier: MIT -->

SPDX-header inject guard for Edit tool calls.

> Advisory: this hook reports; it does not block. Mechanical enforcement runs in CI.

This guard surfaces the SPDX / authorship-header discipline: every applicable
file MUST carry the canonical `SPDX-License-Identifier: MIT` header, and an
edit MUST NOT strip it. It reports a create-via-edit missing the header or an
edit that would remove the header, and recommends the corrected content; the
operator decides. Mechanical enforcement of the header invariant runs in CI
and pre-commit via the strict conformity corpus gate, not at this tool call.

**Scope.** The header is Apothem's own convention, so the guard speaks only in a
git project that follows it: one whose tree carries
`src/apothem/schemas/authorship-header.txt`. Any other project, and any directory
with no `.git`, is silent. In such a project it fires on two corner cases; is a
pass-through on all others.

**Corner case A — create-via-edit (new file).** An Edit tool call where the
target path does not yet exist on disk, `old_string` is empty (the Edit will create
the file), and the proposed `new_string` constitutes the entire file content. An
Edit with an `old_string` to find in a file that does not exist creates nothing,
and is a pass-through. Applies only
when the target path is an applicable file inside the project — its
project-relative path not matching any glob in
`src/apothem/schemas/header-exceptions.txt` and its suffix or basename mapping to a
known variant family in `src/apothem/hooks/lib/header_check.py` SUFFIX_VARIANT /
BASENAME_VARIANT (the tables of `scripts/inject-header.py`) — and `new_string`
does not carry the canonical block at the insertion site. `header_check.py`
decides with the standard library alone, reading the two fixtures from the
`schemas/` directory beside `hooks/` in the tree it runs from, so the guard works
under a plugin install where the `apothem` package is not importable.

**Corner case B — header removal (existing file).** An Edit tool call where
the target path already exists on disk and currently carries the canonical
`SPDX-License-Identifier: MIT` header line, but the proposed edit would
remove or overwrite that line (i.e., the `old_string` matches all or part of
the SPDX header and the `new_string` does not reinstate it). Applies when the
file is applicable per the same criteria as corner case A. The guard applies the
edit to the file's current text and fires only when the result no longer carries
the canonical block, so an edit to a file that never had the header, or to a
region away from it, is a pass-through.

**Pass-through.** Any Edit that modifies an existing file without touching
the canonical SPDX header region is a pass-through — no action is taken and
the edit proceeds uninterrupted.

**Action (both corner cases).**

1. Determine the corrected content. Read `src/apothem/schemas/authorship-header.txt` to
   obtain the single `SPDX-License-Identifier: MIT` line. Render it in the file's
   comment syntax, the family `src/apothem/hooks/lib/header_check.py` names for the
   suffix or basename, and follow it with one blank line: those two lines are the
   canonical block. Insert the block at the top of the proposed content, after a
   shebang `#!` line and, for Markdown and MDX, after the YAML frontmatter and the
   blank line that follows its closing fence. The result is the corrected content.

2. Invoke the structured-inquiry channel using the canonical Authorship-Header option-set at `rules/interactive-questions-canonical-shapes.md` §5.10 (3-option set + override-record schema specified there). Substitute the actual path, corner-case label (`create-via-edit` | `header-removal`), and variant at invocation time. The override-record schema's `rule` column carries the Edit-route corner-case label for this hook.

**Fail-disposition.** Two layers govern failure. (a) The Python dispatcher at
`hooks/dispatch.py` is fail-open: a hook-emission error converts to a structured
failure envelope on stdout and the Edit proceeds, so a harness error never
silently blocks the tool call. A fixture the checker cannot read
(`src/apothem/schemas/authorship-header.txt` or `header-exceptions.txt`) leaves
nothing to check against, so the guard stays silent; a defect inside the checker
fires the advisory and is logged, rather than muting the guard. (b) The
assistant's interpretation of this context is fail-closed on a detected gap:
when the checker reports an absent or malformed header on a create-via-edit, or
a header-removing edit, the directive
is to surface the corrected content via the structured-inquiry channel and let
the operator decide before re-issuing the Edit. The two layers are
non-redundant: the dispatcher protects the runtime, this context protects the
header discipline. The header invariant itself is enforced mechanically in CI
and pre-commit via the strict conformity corpus gate.

## Advisory

<!-- The only text this guard injects when it fires; placeholders are filled by hooks/emit_hook_context.py. -->

After this edit {path} would lack the canonical `SPDX-License-Identifier: MIT` header (or carry it malformed). Restore the line at the top in the file's comment syntax (after a shebang, and after the YAML frontmatter in Markdown and MDX) and re-issue. To skip it, ask the operator first (Authorship-Header option set, `rules/interactive-questions-canonical-shapes.md`).

## Bindings (§0.j five-direction)

- **Drives →** The corrected content recommendation when an Edit would create an applicable file without the SPDX header line or remove an existing one. `hooks/lib/header_check.py` (the header check it runs; the validator `conformity/file_header_grep.py` applies the same rules to the committed tree).
- **Established by ↑** The PreToolUse Edit registration in `hooks/hooks.json` and the harness settings templates. The File Headers section of `AGENTS.md` and the fixture `schemas/authorship-header.txt`.
- **Cross-bound with ↔** `rules/interactive-questions-canonical-shapes.md` (the authorship-header inject-guard option set this guard renders). `hooks/messages/pretooluse-write-header-guard.md` (the same guard on Write).
