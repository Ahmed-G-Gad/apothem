<!-- SPDX-License-Identifier: MIT -->

# Templates

Plan-suite and ledger templates — the canonical starting shapes the planning pipeline and ledger-keeping disciplines materialize into concrete artifacts. A template is read, copied, and filled; it is never the live artifact itself.

## Plan-suite indexing & traceability

| Template | Purpose |
|----------|---------|
| [`master-index-template.md`](master-index-template.md) | Suite-root index for **medium+ tier** plan suites (≥50 phases or ≥100 spec sections / constraints per `../rules/canonical-layout.md` §7). The queryable surface a fresh session or `/plan-review` cycle reads to navigate the suite without scanning every PHASE.md linearly. |
| [`trace-matrix-template.md`](trace-matrix-template.md) | Bidirectional traceability matrix mapping every spec requirement to the phase(s) that satisfy it and back. Closes the all-tier drift-prevention invariant; at small tier a narrative trace table substitutes. |

## Per-folder documentation

| Template | Purpose |
|----------|---------|
| [`agents-md-template.md`](agents-md-template.md) | Folder-parameterizable starting shape for a per-folder `AGENTS.md` companion per `../rules/agents-md-convention.md`. Copied into a meaningful folder beside its `README.md`; orients an agent to the folder's purpose, artifacts, conventions, and safe-operation guidance. |

## `/plan-spec` discipline ledgers

Deliverables of the four operational disciplines (D1–D4) plus the Phase-6 Question-Resolution Sweep audit (D5, from the separate Phase-6 ten-discipline namespace) inside [`../commands/plan-spec.md`](../commands/plan-spec.md). Each is the audit surface proving its discipline executed in full; a skeletal or sham ledger fires a gate and blocks emission.

| Template | Discipline | Records |
|----------|------------|---------|
| [`consideration-log.md`](consideration-log.md) | D1 Meticulous Consideration | Every consideration item surfaced during the prose-to-spec transformation — directives, intentions, rationales, adjacent-domain scans, second-order consequences, contradictions. |
| [`potency-map.md`](potency-map.md) | D2 EXTREME Potency | Every preserved prose element paired with its potent operational form. |
| [`preservation-audit.md`](preservation-audit.md) | D3 STRICT Preservation | Per-clause verdicts at all three preservation levels — syntactic, semantic, tonal. |
| [`expertise-gap-log.md`](expertise-gap-log.md) | D4 Extensive Expertise | Which of the seven axs of breadth applied per transformation, which were not-applicable-with-rationale, which surfaced an expertise-envelope limit. |
| [`question-resolution-audit.md`](question-resolution-audit.md) | D5 Question-Resolution Audit | Every structured-inquiry invocation across the six mandatory gate points G0–G5 — proof no question was suppressed and no default was silent. |

## Conventions

- Markdown templates carry the canonical single-line SPDX license header and an explanatory preamble naming the template's consumer and the gate it feeds.
- A template is copied and filled into a concrete artifact at the canonical layout — never edited as the live artifact in place.
- Tier thresholds and traceability discipline are specified in `../rules/canonical-layout.md`.

## Operating in this folder

- **A template is never the live artifact.** It is copied and filled into a concrete artifact at the canonical layout per `../rules/canonical-layout.md`; do not edit a template in place as though it were the materialized output, and never delete the template's placeholders or guidance comments in the source-of-truth file here.
- **Do not fork the thresholds.** Tier thresholds (which plan-suite tier materializes which template) and traceability discipline are specified in `../rules/canonical-layout.md` — do not restate or fork those thresholds here.
- **Adding a template:** author the new shape with its SPDX header and consumer/gate preamble, then register it in the matching class table above. **Modifying a template** updates every consumer's expectations in the same change-set.
- Validate a change with `python -m apothem.conformity.gate --all .`, `python -m pytest`, and `python -m ruff check`.
