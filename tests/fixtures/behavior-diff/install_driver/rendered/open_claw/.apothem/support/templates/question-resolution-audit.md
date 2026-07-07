<!-- SPDX-License-Identifier: MIT -->

# Question-Resolution Audit Template

The Question-Resolution Audit is the deliverable of Discipline D5 (Question-Resolution Audit) inside `src/apothem/commands/plan-spec.md` Phase 6. Every structured-inquiry invocation across the six mandatory gate points G0–G5 lands one row here; silent-defaulted rows are forbidden by the D8 anti-pattern set.

## Purpose

Realize the operational audit surface for the canonical-channel obligation of `src/apothem/rules/interactive-questions.md`. Every questionable identified by the ten D1 trigger categories produces a row; every row corresponds to an actual structured inquiry call; every P0/P1-severity row resolves at its gate or carries a `<USER-CONFIRM:kind=...; defer-reason=...; defer-timestamp=...; deferred-by-command=plan-spec/>` placeholder routed downstream via the Handoff Manifest. The audit is the proof that no question was suppressed, no default was silent, no fabrication occurred.

## Schema

| Column | Type | Required | Content |
| ------ | ---- | -------- | ------- |
| `question-id` | string | Yes | Stable identifier of the form `QR-NNN`. |
| `trigger-category` | enum | Yes | One of the ten D1 trigger categories: `authority-datum-absent` · `requirement-ambiguity` · `constraint-under-specification` · `ordering-indeterminacy` · `contradiction` · `option-set-decision` · `implicit-assumption` · `expertise-envelope-limit` · `scope-boundary` · `consequence-acceptance`. |
| `source` | string | Yes | Verbatim prose excerpt + source reference (`path:line` or `path:lines a-b`). For category `expertise-envelope-limit` rows, the source may be the Expertise-Gap Log row that surfaced the limit. |
| `question` | string | Yes | The question text emitted via the structured-inquiry channel. One sentence, ending in `?`. |
| `options` | string | Yes | Pipe-delimited list of option labels presented in the invocation. Implicit `Other` (free-text) is not enumerated; only the canned options. |
| `selection` | string | Yes | The label the operator selected. When the operator provided free-text via the implicit `Other` channel, the value is the literal `Other: <free-text>` form. |
| `gate` | enum | Yes | Which gate fired: `G0` (Consideration-Log-Complete standing) · `G1` (Pre-structural-drafting) · `G2` (Mid-drafting on-discovery) · `G3` (Pre-amendment) · `G4` (Pre-emission) · `G5` (Handoff). |
| `severity` | enum | Yes | `P0` (skipping G1/G2/G5 OR D4 Deferral discipline missing one of its five conditions; blocks emission) · `P1` (skipping G3/G4 OR a question that materially affects the spec; blocks emission until resolved) · `P2` (questions whose resolution does not block emission but improves spec quality). |
| `resolution-status` | enum | Yes | `resolved-at-gate-X` (substituting the actual gate that resolved it) · `deferred-with-placeholder` (operator chose to defer; the `<USER-CONFIRM:...>` placeholder is installed and the routing target captured below). |
| `consequence` | string | Yes | One sentence describing what selection of the operator's chosen option entails for the spec — what scaffolding lands, what is excluded, what becomes a dependency for downstream consumption. |
| `deferral-routing` | string | Conditional | When `resolution-status: deferred-with-placeholder`, names the downstream routing target via the Handoff Manifest's `placeholders` field; required only on deferred rows. |

## Sample row

```markdown
| question-id | trigger-category | source | question | options | selection | gate | severity | resolution-status | consequence | deferral-routing |
|-------------|------------------|--------|----------|---------|-----------|------|----------|-------------------|-------------|------------------|
| QR-001 | option-set-decision | notes/migration.md:31 "We probably need to retry transient failures" | Should the migration use retry-with-backoff or at-least-once delivery? | Retry-with-backoff (Recommended) | At-least-once delivery | Defer | Retry-with-backoff (Recommended) | G3 | P1 | resolved-at-gate-G3 | Spec §3.4 lands the retry-with-backoff option set; at-least-once delivery and deferral are excluded. The retry-config parameters become an authority-datum-absent question routed to G3 (closed in QR-002). | — |
| QR-007 | authority-datum-absent | notes/migration.md:48 "rollback strategy" | Which reversibility paths apply to this migration? | Down-migration | Feature-flag rollback | Blue-green swap | Point-in-time-restore | Down-migration · Feature-flag rollback · Point-in-time-restore | G2 | P1 | resolved-at-gate-G2 | Spec §5.1 lists three of the four canonical reversibility paths as in-scope; blue-green swap is explicitly out-of-scope with rationale. | — |
| QR-014 | implicit-assumption | notes/migration.md:55 "We assume the dump tool is fast enough" | Is the dump tool's throughput verified for the migration window? | Verified by recent benchmark | Verified by ops-team experience | Defer with placeholder | Defer with placeholder | G4 | P0 | deferred-with-placeholder | Spec §6.2 carries `<USER-CONFIRM:kind=ops-verification; defer-reason=ops-team-availability-pending; defer-timestamp=<TIMESTAMP>; deferred-by-command=plan-spec/>`; downstream `/plan-generate` consumes the placeholder per the Handoff Manifest's `placeholders` field. | downstream-command:/plan-generate |
```

## Invariants

The audit is checked at G4 (Pre-emission). Required invariants:

- Every row corresponds to an actual structured inquiry call (no fictional rows).
- Every `D1`-identified questionable produces exactly one row (no merging, no skipping).
- No row carries `selection: silent-default` or empty selection (the D8 anti-pattern set forbids these forms).
- Every `severity: P0` and `severity: P1` row carries either `resolution-status: resolved-at-gate-X` or `resolution-status: deferred-with-placeholder` with non-empty `deferral-routing`.
- The Handoff Manifest's `p0-unresolved` and `p1-unresolved` fields equal the count of P0 / P1 rows whose `resolution-status` is `deferred-with-placeholder` and whose `deferral-routing` does not name a placeholder-resolution target. The four-discipline operational invariant requires both fields to read `0` at G5 (Handoff).

## Cross-references

- Discipline D5 Question-Resolution Audit definition: `src/apothem/commands/plan-spec.md` Phase 6 — Question-Resolution Sweep (Ten Disciplines D1–D10).
- Canonical channel obligation: `src/apothem/rules/interactive-questions.md`.
- Handoff Manifest target: `src/apothem/schemas/handoff-manifest.yaml`.
- Trigger-category D1 enumeration source: `src/apothem/commands/plan-spec.md` §Workflow Phase 6 D1.
