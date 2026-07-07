---
fixture: F-9
title: Production-readiness gap
spec-source: _spec/spec.md §7.1 row 9
mandates: [M15]
---

<!-- SPDX-License-Identifier: MIT -->

# F-9 — Production-readiness gap

## Spec binding

Spec §7.1 row 9: a request to add a new public function in a
host that already operates the M15 visibility surfaces (LICENSE,
CHANGELOG with Keep-a-Changelog format, semver, tests
directory). Tests **M15 — Production-Ready Discipline on
Host-Project Artifacts** at the same-change-set arm: every code
change ships with tests + docs + CHANGELOG entry in **one**
change.

## Synthetic host description

| Path | Role |
|---|---|
| `before/README.md` | Project landing page; declares semver + Keep-a-Changelog. |
| `before/CHANGELOG.md` | Keep-a-Changelog with `[Unreleased]` rolling section + two historical entries. |
| `before/src/cadence/every.py` | Existing public surface: `Schedule`, `daily`, `weekly` — fully-typed, `@dataclass(frozen=True, slots=True)`, Google-style docstrings with `Args` + `Returns`. |
| `before/tests/test_every.py` | Existing pytest tests for `daily` + `weekly` — AAA shape; behavior-descriptive names. |
| `before/PROMPT.md` | Verbatim user request: add `monthly(day_of_month, at)` matching the shape of `daily` + `weekly`. The user does NOT mention tests, docs, or CHANGELOG. |

The host's existing `every.py` and `test_every.py` are the
sibling-convergence target — every emitted artifact converges
on those files' idioms.

## Mandate-firing expectations

### M15 — Same-Change-Set Discipline (§1)

Per `src/apothem/rules/production-ready-prs.md` §1, the new
public function ships **in one change-set** with:

| Element | Where in this fixture |
|---|---|
| Tests | `before/tests/test_every.py` extended with at least one `test_monthly_*` function (AAA shape; behavior-descriptive name) covering happy path + at least one edge case. |
| Documentation | The new function's Google-style docstring — `Args` + `Returns` matching the `daily` / `weekly` siblings. |
| CHANGELOG entry | `[Unreleased]` § `### Added` — one row naming the new public surface (`every.monthly(day_of_month, at)` for monthly recurrence patterns). |
| Code | `every.py` extended with the new `monthly` function, sibling-convergent (typed signature, `@dataclass`-returning, `from __future__ import annotations`). |

The same-change-set discipline forbids the pattern "I'll add
tests / docs / CHANGELOG in a follow-up". Any element shipped
without one of the four constitutes a release-blocker per
spec §7.3 mandatory-bar floor on M15 (under the per-run override
the operator ratified, M15 is at the 100%-pass tier per
threshold-inquiry-record).

### M15 — Visibility-Surface Continuity (§2)

The host's existing surfaces (CHANGELOG with semver pin) define
the format the agent must converge on:

- The `[Unreleased]` § `### Added` row format is preserved;
- The CHANGELOG format-pin (Keep-a-Changelog 1.1.0) is honored
  by the new row's prose.

## Pass signals

- [ ] `every.py` carries a `monthly` function with a Google-style
      docstring (Args + Returns) matching the `daily` / `weekly`
      sibling shape.
- [ ] `test_every.py` carries at least one `test_monthly_*`
      function with AAA shape.
- [ ] `CHANGELOG.md` `[Unreleased]` § `### Added` carries a row
      naming the new public surface.
- [ ] All four artifacts (`every.py`, `test_every.py`, `CHANGELOG.md`,
      and either README or docstring covering the surface) are
      modified in the same change-set.
- [ ] The fifteen-bar attestation block records `M15: pass` with
      the same-change-set evidence enumerated.

## Fail signals

- The `monthly` function is added without a corresponding test
  in `test_every.py` (M15 same-change-set violation —
  release-blocker).
- The `monthly` function is added without a docstring (M13.11
  violation reaching M15 visibility-surface gap on the
  how-to-use surface).
- The CHANGELOG `[Unreleased]` section is not updated (M15
  same-change-set violation — release-blocker).
- The agent emits the function with a comment like `# TODO: add
  test in follow-up` or splits the work across multiple
  imagined change-sets (M15 deferred-quality failure tell).

## Bindings (§0.j five-direction)

- **Drives →** Sub-phase 09B `verify.py`.
- **Satisfies →** Spec §7.1 row 9. Sub-phase 09B Task 5.
- **Established by ↑** Sub-phase 09B `PHASE.md` Task 5.
- **Cross-bound with ↔** F-4 (M15 visibility-gap arm — the
  CONTRIBUTING-absent inquiry path). Together F-4 + F-9 cover
  the two arms of M15: visibility-surface gap-surfacing (F-4)
  and same-change-set production discipline (F-9).
