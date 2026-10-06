<!-- SPDX-License-Identifier: MIT -->

Call-time `(Recommended)`-marker guard for `AskUserQuestion` tool calls.

> Advisory: this guard reports; it does not block by default. The strict
> opt-in (`APOTHEM_CONFORMITY_STRICT=1` or `--strict`) escalates
> well-formedness violations to a block.

This guard closes the previously documented-but-unenforced call-time gap in the
`(Recommended)` interactive-question guarantee. The option-annotation matchers
(`conformity/option_annotation_grep.py`) scan committed `*.md` artifacts only;
nothing inspected the LIVE `AskUserQuestion` tool payload at the moment the
agent asks the operator. This dispatch-routed `PreToolUse` handler
(`hooks/askuserquestion_validator.py`) inspects the live payload — the
`questions` array, each question's `options[].label` and `multiSelect` — and
validates marker well-formedness against the canonical rule at
`rules/interactive-questions-canonical-shapes.md` §2.1.

**Scope.** Fires on `AskUserQuestion` tool calls. The dispatcher routes this
message basename to the validator rather than emitting a static context, so the
check runs on the live payload at call time.

**Well-formedness findings (block-eligible under the strict opt-in).** Each is
objectively decidable from the payload alone:

- **non-canonical-postfix-case** — a label ends with the banned lowercase
  `(recommended)`; the canonical form is the capital `(Recommended)`.
- **non-canonical-postfix-form** — a label names a recommended token in a
  non-canonical bracket / spacing form (`[Recommended]`, `(Rec)`,
  `(Recommended )`, `( Recommended )`); the canonical form is the exact
  ` (Recommended)` postfix with one leading space at the end of the label.
- **recommended-on-destructive** — the marker rides a clearly-destructive
  option label (delete / remove / discard / overwrite / revert / …); an
  irreversible action must not be the recommended (and easy) path, per the
  destructive-op no-default floor at
  `rules/interactive-questions-canonical-shapes.md` §5.8.
- **single-select-multi-recommended** — a `multiSelect: false` question carries
  the marker on more than one option; at most one is permitted (set
  `multiSelect: true` to recommend several).

**Nudge (advisory only — never blocks).** A `multiSelect: false` question with
two or more substantive options and zero `(Recommended)` markers is *advised*
to mark its recommended option. The native `AskUserQuestion` payload carries no
separate "recommended" field — the marker IS the only signal of which option is
recommended — so a missing marker cannot be proven a defect. This is a
heuristic nudge, not a hard rule.

**What the runtime check CAN and CANNOT guarantee.** It CAN guarantee marker
well-formedness (a present marker is in the canonical form, placed correctly,
not on a destructive option, at most one per single-select question). It CANNOT
force a recommendation to exist — that is a behavioral-convention obligation the
rules carry, surfaced here only as the advisory nudge.

**Advisory vs. strict.** By default the guard returns the findings and nudges
as `additionalContext`, so the model that wrote the labels can fix them; the
question proceeds. Under the strict opt-in (`APOTHEM_CONFORMITY_STRICT=1` or
`--strict`, mirroring `conformity/gate.py`), well-formedness findings (never the
nudge) escalate to `permissionDecision: deny` with the findings as the reason.

**Fail-disposition.** Fail-open. Any exception inside the validator — a
malformed payload, a shapeless `questions` array, an unexpected option type —
yields an empty (allow) envelope, so a validator error never crashes the
operator's question. The dispatcher's outer boundary is fail-open too: a
dispatch error converts to a structured failure envelope on stdout and the
question proceeds.

## Bindings (§0.j five-direction)

- **Drives →** `hooks/askuserquestion_validator.py` (the dispatcher routes this basename to the validator, which checks the `(Recommended)` marker on the live question payload).
- **Established by ↑** The PreToolUse AskUserQuestion registration in `hooks/hooks.json` and the harness settings templates. `rules/interactive-questions-canonical-shapes.md` (the marker form it validates). `conformity/option_annotation_grep.py` (the committed-artifact counterpart this call-time check complements).
- **Cross-bound with ↔** `hooks/messages/pretooluse-conformity.md` (the per-write gate context whose option-annotation matcher covers committed artifacts).
