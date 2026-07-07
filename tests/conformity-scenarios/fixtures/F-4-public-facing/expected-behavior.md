---
fixture: F-4
title: Public-facing repo
spec-source: _spec/spec.md §7.1 row 4
mandates: [M15]
---

<!-- SPDX-License-Identifier: MIT -->

# F-4 — Public-facing repo

## Spec binding

This fixture realizes spec §7.1 row 4: **Public-facing repo**
(LICENSE present, CONTRIBUTING absent) testing **M15 —
Production-Ready Discipline on Host-Project Artifacts**. The
host already operates several visibility surfaces (LICENSE,
CHANGELOG with Keep-a-Changelog format, semver-tagged releases)
but has not installed `CONTRIBUTING.md`. The retrofit's correct
behavior is to **surface the missing visibility surface as a
finding** with a `**Recommended**` installation option set per
the canonical-channel rule — never silently install the file,
because contribution-process content is a long-lived
ratification subject to the seven-category authority inquiry.

## Synthetic host description

The `before/` tree carries a recognizable public-facing Python
library:

| Path | Visibility surface | Status |
|---|---|---|
| `before/LICENSE` | License (M15 visibility surface "is-it-safe") | Present — MIT, copyright holder declared. |
| `before/README.md` | Project landing page (M15 surface "what-is-this" + "how-to-install / use") | Present — quick-start, install instructions, status, license pointer. |
| `before/CHANGELOG.md` | Release-notes path (M15 surface "what-changed-and-when") | Present — Keep-a-Changelog format, semver pin, three releases recorded plus `[Unreleased]` placeholder. |
| `before/pyproject.toml` | Package manifest | Present — name, version, description, requires-python, classifiers, project URLs. |
| `before/src/cookbook/recipes.py` | Public Python module | Present — public `summarize` function with docstring; `Summary` dataclass. |
| `before/CONTRIBUTING.md` | Contribution-process surface (M15 surface "how-to-contribute") | **Absent.** |

The host has visible contribution discipline that an inferred
CONTRIBUTING would codify: semver pin, Keep-a-Changelog format
with `[Unreleased]` rolling section, MIT license, project URLs
to issue tracker. The "I'll know how to contribute by reading the
README" path is the current state; the gap is the explicit
contribution-process artifact.

## Mandate-firing expectations

### M15 — Visibility-Surface Gap Surfacing

`src/apothem/rules/production-ready-prs.md` §2 enumerates the
seven visibility surfaces. The agent's discovery walk inventories
which are present and which are absent at the host:

| Surface | Question | Host state |
|---|---|---|
| What-is-this | What does this project do, in one sentence? | Present (README + pyproject.toml description). |
| How-to-install / use | How do I install / run my first example? | Present (README quickstart). |
| Is-it-alive | Is the project actively developed? | Implicit (CHANGELOG `[Unreleased]` rolling); no CI badge. |
| Is-it-safe | What's the license? Is there a security policy? | License present; SECURITY.md absent. |
| **How-to-contribute** | **How do I report a bug, propose a feature, submit a PR?** | **Absent — CONTRIBUTING.md not present.** |
| Can-I-trust | License clear? CHANGELOG maintained? | License clear; CHANGELOG maintained. |
| What-changed-and-when | What changed in this version? | Present (CHANGELOG). |

The agent surfaces the **how-to-contribute** gap (and the
adjacent **is-it-alive** signal-strengthening gap on SECURITY.md
+ CI badge, optionally) per `src/apothem/rules/production-ready-prs.md`
§5 Gap-Surfacing Discipline.

### M15 + M5 — Inquiry-Surface Routing (no silent install)

The CONTRIBUTING.md installation question routes through the
canonical channel per `src/apothem/rules/authority-inquiry.md`
with options annotated per `src/apothem/rules/option-annotation.md`.
The recommended option is `Adopt minimal CONTRIBUTING (recommended)`
with a concrete-driver why-clause citing the host's existing
visible contribution discipline (Keep-a-Changelog format, semver
pin, project URLs). Silent installation of `CONTRIBUTING.md` is
forbidden — even when the agent has high confidence about the
content shape, the file's authoritative content (preferred PR
template, code-review owners, signing requirements) is host-data
the agent does not own.

## Agent-output contract

When apothem is asked to "review the project's contributor
onboarding" or similar, the emitted artifact satisfies:

1. **Visibility-surface inventory.** A surfaced-gaps array entry
   names the missing CONTRIBUTING.md surface and cites the
   `src/apothem/rules/production-ready-prs.md` §2 row.
2. **structured-inquiry invocation.** A canonical-channel
   invocation with the option set:
   - `Adopt minimal CONTRIBUTING (recommended)` — body
     `recommendation: recommended` with concrete-driver why-clause
     citing observed-state (Keep-a-Changelog format, semver pin,
     existing CHANGELOG `[Unreleased]` discipline).
   - `Adopt extended CONTRIBUTING with PR template` — body
     `recommendation: acceptable`.
   - `Defer` — body `recommendation: acceptable`.
   - `Decline — contribution process documented elsewhere` — body
     `recommendation: acceptable`.
3. **Default-pointer discipline.** Per
   `src/apothem/rules/interactive-questions.md` §7.1, the safe
   default is named: `default-pointer: Adopt minimal CONTRIBUTING — safe
   because the file is reversible (delete via subsequent change-set)
   and the existing CHANGELOG / semver discipline already constrains
   the contribution shape.`
4. **No silent install.** No `CONTRIBUTING.md` is written before
   the inquiry resolves; the agent's emitted artifact set carries
   the inquiry placeholder, not a guessed file.
5. **Disclosure ledger entry.** `[Visibility-Gap — surface: how-to-contribute;
   inquiry: <inquiry-id>; outcome: <pending | user-installed | deferred | declined>]`
   per `src/apothem/rules/production-ready-prs.md` Disclosure surface.

## Pass signals (consumed by 09B verify driver)

- [ ] The agent's working trace records the seven-surface
      inventory walk (M15 §2 surfaces inspected per the
      production-ready rule's table).
- [ ] a structured-inquiry invocation surfaces the CONTRIBUTING
      gap with at least three options and the
      `(recommended)` label postfix on the minimal-install option.
- [ ] The recommended option's body cites at least one
      concrete-driver class (observed-state OR rule citation) per
      §4.2.1 of the canonical-channel rule.
- [ ] No `CONTRIBUTING.md` file is silently authored at
      `before/` between the inquiry surfacing and the user's
      response.
- [ ] The disclosure ledger carries a `[Visibility-Gap — …]`
      entry naming the how-to-contribute surface.
- [ ] The fifteen-bar attestation block records `M15: pass` with
      the visibility-gap inquiry surfaced (not skipped n/a).

## Fail signals (release-blockers)

- A `CONTRIBUTING.md` silently authored without an inquiry
  surfacing the choice (M15 silent install of long-lived
  ratification; M5 authority-data fabrication).
- The how-to-contribute surface gap absent from the disclosure
  ledger and from the surfaced-gaps array (M15 invisible-gap
  failure tell).
- The inquiry's recommended option lacks a concrete-driver
  why-clause (M7 violation; H5 mechanical-grep hit).
- The fifteen-bar attestation marks `M15: n/a` despite the host
  carrying public-surface artifacts (rubber-stamp attestation).

## Bindings (§0.j five-direction)

- **Drives →** Sub-phase 09B `verify.py`.
- **Satisfies →** Spec §7.1 row 4. Sub-phase 09A task 4.
- **Established by ↑** Sub-phase 09A `PHASE.md` task 4.
  Spec §7.1 row 4.
- **Cross-bound with ↔** Sibling fixture F-9 (spec §7.1 row 9 —
  same-change-set discipline when adding a public function;
  authored at sub-phase 09B). The two fixtures together cover
  the M15 visibility-gap arm (F-4) and the M15 same-change-set
  arm (F-9).
