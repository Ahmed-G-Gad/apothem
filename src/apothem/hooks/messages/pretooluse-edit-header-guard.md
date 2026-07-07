<!-- SPDX-License-Identifier: MIT -->

SPDX-header inject guard for Edit tool calls.

> Advisory: this hook reports; it does not block. Mechanical enforcement runs in CI.

This guard surfaces the SPDX / authorship-header discipline: every applicable
file MUST carry the canonical `SPDX-License-Identifier: MIT` header, and an
edit MUST NOT strip it. It reports a create-via-edit missing the header or an
edit that would remove the header, and recommends the corrected content; the
operator decides. Mechanical enforcement of the header invariant runs in CI
and pre-commit via the strict conformity corpus gate, not at this tool call.

**Scope.** Fires on two corner cases; is a pass-through on all others.

**Corner case A — create-via-edit (new file).** An Edit tool call where the
target path does not yet exist on disk (the Edit will create the file) and
the proposed `new_string` constitutes the entire file content. Applies only
when the target path is an applicable file — not matching any glob in
`src/apothem/schemas/header-exceptions.txt` and whose suffix or basename maps to a known
variant family in `src/apothem/conformity/file_header_grep.py` SUFFIX_VARIANT /
BASENAME_VARIANT — and `file_header_grep.check()` returns HEADER_ABSENT or
HEADER_MALFORMED for `new_string`.

**Corner case B — header removal (existing file).** An Edit tool call where
the target path already exists on disk and currently carries the canonical
`SPDX-License-Identifier: MIT` header line, but the proposed edit would
remove or overwrite that line (i.e., the `old_string` matches all or part of
the SPDX header and the `new_string` does not reinstate it). Applies when the
file is applicable per the same criteria as corner case A.

**Pass-through.** Any Edit that modifies an existing file without touching
the canonical SPDX header region is a pass-through — no action is taken and
the edit proceeds uninterrupted.

**Action (both corner cases).**

1. Determine the corrected content. Read `src/apothem/schemas/authorship-header.txt` to
   obtain the single `SPDX-License-Identifier: MIT` line. Call
   `_render_canonical_block` (from `src/apothem/conformity/file_header_grep.py`) for the
   file's variant family to produce the canonical block (the one SPDX line
   rendered in the family's comment syntax, followed by one trailing blank
   line). Set the insertion index to 1 when the proposed content opens
   with a shebang `#!`, otherwise 0. Insert the canonical block at that index
   into the proposed content to produce the corrected content.

2. Invoke the structured-inquiry channel using the canonical Authorship-Header option-set at `rules/interactive-questions-canonical-shapes.md` §5.10 (3-option set + override-record schema specified there). Substitute the actual path, corner-case label (`create-via-edit` | `header-removal`), and variant at invocation time. The override-record schema's `rule` column carries the Edit-route corner-case label for this hook.

**Fail-disposition.** Two layers govern failure. (a) The Python dispatcher at
`hooks/dispatch.py` is fail-open: a hook-emission error — `src/apothem/schemas/authorship-header.txt`
unreadable, `_render_canonical_block` raising, the variant lookup failing, or
any Python exception inside the predicate — converts to a structured failure
envelope on stdout and the Edit proceeds, so a harness error never silently
blocks the tool call. (b) The assistant's interpretation of this context is
fail-closed on a detected gap: when the validator reports HEADER_ABSENT or
HEADER_MALFORMED on a create-via-edit, or a header-removing edit, the directive
is to surface the corrected content via the structured-inquiry channel and let
the operator decide before re-issuing the Edit. The two layers are
non-redundant: the dispatcher protects the runtime, this context protects the
header discipline. The header invariant itself is enforced mechanically in CI
and pre-commit via the strict conformity corpus gate.
