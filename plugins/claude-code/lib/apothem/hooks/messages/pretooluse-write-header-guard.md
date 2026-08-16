<!-- SPDX-License-Identifier: MIT -->

SPDX-header inject guard for Write tool calls.

> Advisory: this hook reports; it does not block. Mechanical enforcement runs in CI.

This guard surfaces the SPDX / authorship-header discipline: every applicable
new file MUST begin with the canonical `SPDX-License-Identifier: MIT` header.
It reports a missing or malformed header and recommends the corrected content;
the operator decides. Mechanical enforcement of the header invariant runs in CI
and pre-commit via the strict conformity corpus gate, not at this tool call.

**Scope.** Fires when a Write tool call targets an applicable file — any file
whose path does not match a glob in `src/apothem/schemas/header-exceptions.txt` and whose
suffix or basename maps to a known variant family in
`src/apothem/conformity/file_header_grep.py` SUFFIX_VARIANT / BASENAME_VARIANT — and
`file_header_grep.check()` returns HEADER_ABSENT or HEADER_MALFORMED for the
proposed content.

**Action.**

1. Determine the corrected content. Read `src/apothem/schemas/authorship-header.txt` to
   obtain the single `SPDX-License-Identifier: MIT` line. Call
   `_render_canonical_block` (from `src/apothem/conformity/file_header_grep.py`) for the
   file's variant family to produce the canonical block (the one SPDX line
   rendered in the family's comment syntax, followed by one trailing blank
   line). Set the insertion index to 1 when the proposed content opens
   with a shebang `#!`, otherwise 0. Insert the canonical block at that index
   to produce the corrected content.

2. Invoke the structured-inquiry channel using the canonical Authorship-Header option-set at `rules/interactive-questions-canonical-shapes.md` §5.10 (3-option set + override-record schema specified there). Substitute the actual path, rule, and variant at invocation time. The override-record schema's `rule` column carries the Write-route rule label for this hook.

**Fail-disposition.** Two layers govern failure. (a) The Python dispatcher at
`hooks/dispatch.py` is fail-open: a hook-emission error — `src/apothem/schemas/authorship-header.txt`
unreadable, `_render_canonical_block` raising, the variant lookup failing, or
any Python exception inside the predicate — converts to a structured failure
envelope on stdout and the Write proceeds, so a harness error never silently
blocks the tool call. (b) The assistant's interpretation of this context is
fail-closed on a detected gap: when the validator reports HEADER_ABSENT or
HEADER_MALFORMED, the directive is to surface the corrected content via the
structured-inquiry channel and let the operator decide before re-issuing the
Write. The two layers are non-redundant: the dispatcher protects the runtime,
this context protects the header discipline. The header invariant itself is
enforced mechanically in CI and pre-commit via the strict conformity corpus
gate.
