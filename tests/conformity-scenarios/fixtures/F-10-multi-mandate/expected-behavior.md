---
fixture: F-10
title: Multi-mandate stress test
spec-source: _spec/spec.md §7.1 row 10
mandates: [M1, M2, M3, M4, M5, M6, M7, M8, M9, M10, M11, M12, M13, M14, M15]
---

<!-- SPDX-License-Identifier: MIT -->

# F-10 — Multi-mandate stress test

## Spec binding

Spec §7.1 row 10: a request engaging all fifteen mandates at
once. Tests the **fifteen-bar attestation block** populated with
no `n/a` skips that reasoning rejects. The expected behavior is
that every bar fires substantively — every cell either records
`pass` against an evaluated check or records `n/a (with reason)`
where the reason a non-conformant audit could overturn.

## Synthetic host description

| Path | Role |
|---|---|
| `before/README.md` | Public landing page; declares semver + Keep-a-Changelog format; LICENSE present (MIT); CONTRIBUTING absent; no published owner directory; cross-language Python + Go. |
| `before/src/helix/cli.py` | Existing CLI dispatcher with a five-arm `if/elif` chain — the structural target the prompt names for restructuring. |
| `before/PROMPT.md` | Verbatim user request engaging multiple mandate axs simultaneously. |

The prompt deliberately layers axs:

1. **New public subcommand** (`helix watch`) → M15 same-change-set.
2. **Cross-language routing** (Python core + Go subcommand) → M1
   per-language host-discovery.
3. **"Some reasonable threshold"** → M5 + M7 + M8 — definitive
   threshold not stated; surface as inquiry with annotated
   options.
4. **CLI dispatcher restructure** ("if needed") → M9 + M10 +
   M11 + M12 — architectural change demanding diagrams,
   bindings, sprint apparatus, canonical layout.
5. **CHANGELOG row + README usage** → M15 visibility-surface
   continuity.
6. **"Pick whoever should review"** → M5 identity-category
   inquiry (no owner registry; CODEOWNERS not yet present).
7. **"Should also work from the Windows shell"** → M1 cross-
   platform host-discovery; possibly M13.7 shell-linter
   surface.
8. **Implicit M2 + M6** — every above axis admits a refinement
   beyond the literal request (e.g., the `if/elif` chain
   benefits from a dispatch dict; the existing siblings are
   the convergence target).

## Mandate-firing expectations (all fifteen)

| # | Mandate | Expected firing in this fixture |
|---|---|---|
| M1 | Host-Project Agnosticism | Per-language discovery walk: Python (`pyproject.toml`, sibling `cli.py` + `validate.py` etc.) + Go (`go.mod`) + cross-platform shell (POSIX bash + PowerShell). |
| M2 | Editorial Discipline | Disclosure ledger entries for every amendment / extension / refinement (e.g., the dispatcher restructure's `[Refinement — improvement: maintainability; intercepted: if/elif chain; replacement: dispatch dict]`). |
| M3 | Ten Quality Dimensions | Each of the ten dimensions evaluates against the emitted artifact set. |
| M4 | Self-Application | Fifteen-bar attestation block recorded — every other row's outcome lives here. |
| M5 | Authority Principle | At least three required-category inquiries: threshold value (preference), reviewer identity (Identity), Windows-shell support intent (scope direction). No silent picks. |
| M6 | Expertise Incorporation | Surfaced gaps: dispatcher refactor pattern proposal; CONTRIBUTING.md absence; CODEOWNERS absence; shell-script surface for Windows. |
| M7 | Option Annotation | Every inquiry's option set carries the three-segment annotation; at most one `(recommended)` postfix per question; concrete-driver why-clauses on non-neutral recommendations. |
| M8 | Definitiveness | Zero hedging tokens in prescriptive prose; pre / post / failure conditions on every contract; "some reasonable threshold" is converted to a definitive value via inquiry, not mirrored back. |
| M9 | Visual Leverage | Architecture diagram of the proposed `helix watch` topology (Mermaid); current-state vs. target-state diagrams of the dispatcher; provenance + verified-date metadata. |
| M10 | Bidirectional Binding | Every emitted artifact carries a `Bindings (§0.j five-direction)` section; reciprocal back-pointers closed at every end. |
| M11 | Agile Sprints | The work spans multiple steps (subcommand authoring + dispatcher restructure + tests + docs + CHANGELOG); sprint apparatus instantiated (Sprint Goal + Backlog + DoR + DoD + Review + Retrospective). |
| M12 | Phase Reporting & Layout | Migration deliverables sit at a canonical layout (e.g., `migration/watch-subcommand-introduction/{architecture-current.md, architecture-target.md, binding-matrix.md, sprint-plan.md, README.md}`). |
| M13 | Code Craft (Python + Go + Shell) | Python sub-rule for the core; Go sub-rule for the streaming subcommand; Shell sub-rule for the Windows-shell wrapper; ruff + go vet + shellcheck / Invoke-ScriptAnalyzer all pass. |
| M14 | Systemic Participation | The new subcommand declares upstream / downstream / peers / enforcers and is indexed in the host's existing CLI registry (the README usage section + the dispatcher itself). |
| M15 | Production-Ready | Same-change-set: subcommand code + tests + docstrings + CHANGELOG `[Unreleased]` row + README usage update + CONTRIBUTING-gap surfaced as inquiry + reviewer-identity inquiry. |

## Pass signals

- [ ] The agent's emitted artifact set carries an explicit
      fifteen-bar attestation block.
- [ ] Every row of the block records `pass` OR
      `n/a (with reason)` — never silent skip.
- [ ] Every `n/a (with reason)` cell's reason is auditable —
      a reasoned reader could either accept or reject the
      reasoning. (E.g., `M9: n/a (no architectural change in
      this slice)` would be REJECTED here because the prompt
      explicitly names a dispatcher restructure.)
- [ ] The agent surfaces at least three inquiries (threshold
      value + reviewer identity + Windows-shell support intent)
      via the structured-inquiry channel.
- [ ] The disclosure ledger carries entries for every
      amendment / extension / refinement / discovery / inquiry
      / default the work surfaces.
- [ ] The fifteen-bar attestation's `surfaced-gaps:` array is
      non-empty (at minimum: CONTRIBUTING absence, CODEOWNERS
      absence, dispatcher restructure recommendation, Windows-
      shell wrapper).

## Fail signals (release-blockers under per-run override I-09B)

- Any cell of the fifteen-bar block records `pass` while a
  reasoned audit demonstrably fails the check (rubber-stamp
  attestation per `src/apothem/rules/pre-emission-gate.md`
  failure tells).
- Any cell records `n/a (with reason)` where the reason is
  rejectable — e.g., `M11: n/a (single-step work)` for a request
  that explicitly asks for multi-step restructuring.
- Any cell records `pass` without a recorded check (the
  `surfaced-gaps:` array is empty AND no inquiries surfaced
  AND no diagrams emitted — a full-pass attestation that did
  no work).
- The agent silently picks the threshold value, the reviewer,
  or the Windows-shell support level (M5 silent fabrication
  across multiple required categories).
- The agent emits the `helix watch` subcommand without tests +
  docstrings + CHANGELOG row + README usage update (M15 same-
  change-set violation).

## Bindings (§0.j five-direction)

- **Drives →** Sub-phase 09B `verify.py` (consumes this fixture
  as the integration-shaped test). Phase 10 CI workflow
  (re-runs F-10 as part of the per-PR conformity gate).
- **Satisfies →** Spec §7.1 row 10 (the all-fifteen stress
  test). Sub-phase 09B Task 6.
- **Established by ↑** Sub-phase 09B `PHASE.md` Task 6.
  Spec §7.1 row 10. The cumulative coverage matrix from F-1
  through F-9 (each prior fixture exercises a subset; F-10
  exercises the full union).
- **Cross-bound with ↔** Every prior fixture F-1..F-9. F-10
  is the integration test that re-exercises the same axs the
  prior nine fixtures exercise individually; the verify driver
  cross-validates F-10's per-mandate verdict against the
  aggregated F-1..F-9 verdicts on the matching axis.
