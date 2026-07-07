<!-- SPDX-License-Identifier: MIT -->

# Preservation Audit Template

The Preservation Audit is the deliverable of Discipline D3 (STRICT Preservation) inside `src/apothem/commands/plan-spec.md`. It records the per-clause verdicts at all three preservation levels — Level 1 syntactic · Level 2 semantic · Level 3 tonal — that gate emission of the spec.

## Purpose

Realize the spec's load-bearing principle: **preservation is strict weaving; every prose clause is woven into scaffolding at its structural locus; transformation is additive, not rewriting**. The Preservation Audit is the per-clause record proving this principle held: every distinctive prose phrase verbatim-present (Level 1), every requirement / constraint / directive operationally HONORED (Level 2), every tonal choice preserved at the analogous locus (Level 3).

## The three levels

- **Level 1 — Syntactic.** Every distinctive phrase verbatim, grep-matchable. Reproducible matcher: `rg --no-heading -nF '<phrase>' {suite}/_spec/spec.md`. A single grep-miss is a Level-1 failure (`**P1**` block).
- **Level 2 — Semantic.** Every requirement / constraint / directive / implicit assumption is HONORED in operational scaffolding (not merely quoted). Quotation without operational enforcement is a Level-2 failure (`**P1**` block).
- **Level 3 — Tonal.** Bold / italic / ALL-CAPS / repeated intensifiers / slash-alternations / paired adjectives / rhetorical repetition are preserved at the analogous locus. Flattening is a Level-3 failure (`**P2**` escalating to `**P1**` when interpretive weight is materially affected).

## Schema

| Column | Type | Required | Content |
| ------ | ---- | -------- | ------- |
| `clause-id` | string | Yes | Stable identifier shared with the Consideration Log's `item-id` namespace (e.g., `CL-001` becomes `clause-id: CL-001` here). |
| `source-locus` | string | Yes | Path + line reference for the source prose. |
| `target-locus` | string | Yes | Section anchor in `_spec/spec.md` where the clause is woven. |
| `l1-verdict` | enum | Yes | `pass` (verbatim grep-match holds) · `fail` (grep-miss; the verbatim phrase is absent at the target locus). |
| `l1-matcher` | string | Conditional | The `rg` invocation used; required when `l1-verdict: pass` so the verdict is reproducible. |
| `l2-verdict` | enum | Yes | `pass` (the requirement / constraint / directive is operationally enforced via SLO / option set / sprint apparatus / etc.) · `fail` (the source clause is quoted without operational enforcement). |
| `l2-enforcement-anchor` | string | Conditional | The Potency Map row (`PM-NNN`) or the section in `_spec/spec.md` where the operational enforcement lives; required when `l2-verdict: pass`. |
| `l3-verdict` | enum | Yes | `pass` (tonal choice preserved at the analogous locus) · `partial` (`**P2**` — tonal choice partially preserved with no material effect on interpretive weight) · `fail` (`**P1**` — tonal choice flattened with material effect on interpretive weight). |
| `l3-tonal-marker` | string | Conditional | The specific tonal marker preserved (e.g., `ALL-CAPS PERSISTENTLY`, `bold "must never"`, `paired adjective "airtight + strict"`); required when `l3-verdict: pass` or `partial`. |
| `notes` | string | No | Free-form remediation notes when any verdict is `fail` or `partial`. |

## Sample row

```markdown
| clause-id | source-locus | target-locus | l1-verdict | l1-matcher | l2-verdict | l2-enforcement-anchor | l3-verdict | l3-tonal-marker | notes |
|-----------|--------------|--------------|------------|------------|------------|-----------------------|------------|-----------------|-------|
| CL-001    | notes/migration.md:14 | §3.4 SLOs | pass | rg --no-heading -nF '"Reliability above all"' _spec/spec.md | pass | PM-001 (SLO 99.95%/28-day) | pass | bold "above all" preserved at §3.4 lead | — |
| CL-014    | notes/migration.md:62 | §3.4 Reliability options | pass | rg --no-heading -nF '"Probably should think about caching"' _spec/spec.md | pass | PM-002 (decision option set) | pass | hedging "probably" preserved as deferral signal | Surfaced via the structured-inquiry channel at G3; selection captured in Question-Resolution Audit row QR-007. |
| CL-022    | notes/migration.md:72 | §5.1 Reversibility paths | pass | rg --no-heading -nF '"Migration must be reversible"' _spec/spec.md | pass | PM-008 (definitive closed-set) | pass | imperative "must be" preserved verbatim | — |
```

## Per-level summary

The Preservation Audit emits a header summary above the per-row table:

```markdown
| Level | Pass | Partial | Fail | Total |
|-------|------|---------|------|-------|
| 1     | 124  | 0       | 0    | 124   |
| 2     | 47   | 0       | 0    | 47    |
| 3     | 12   | 0       | 0    | 12    |
```

The summary is the inspection surface for the four-discipline operational invariant condition (i) + (ii) + (iii). Any non-zero `Fail` count blocks emission until the offending rows resolve.

## Cross-references

- Discipline D3 STRICT Preservation definition: `src/apothem/commands/plan-spec.md` §Workflow Phase 4.
- Source consideration item: `src/apothem/templates/consideration-log.md` (`item-id` ↔ `clause-id`).
- Operational enforcement target: `src/apothem/templates/potency-map.md` (`PM-NNN` referenced in `l2-enforcement-anchor`).
