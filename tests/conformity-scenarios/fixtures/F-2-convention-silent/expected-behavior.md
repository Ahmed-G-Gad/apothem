---
fixture: F-2
title: Convention-silent repo
spec-source: _spec/spec.md §7.1 row 2
mandates: [M1, M5, M7]
---

<!-- SPDX-License-Identifier: MIT -->

# F-2 — Convention-silent repo

## Spec binding

This fixture realizes spec §7.1 row 2: **Convention-silent repo**
(no formatter / linter / CHANGELOG) testing **M1 +
M5 + M7**. The host has decided nothing about lint posture,
format posture, release-notes posture, license, or contribution
process. The retrofit's correct behavior is **inquire, do not
invent** — every absent convention surfaces as an annotated
structured-inquiry invocation per the canonical channel rule, and
silent installation of any long-lived ratification is forbidden.

## Synthetic host description

The `before/` tree is two files:

| Path | Role | What is **absent** that the discovery walk surfaces |
|---|---|---|
| `before/README.md` | Bare project description | No license declaration; no contribution process; no release-notes path. |
| `before/tally.py` | Single Python source file | No `pyproject.toml`; no `requirements*.txt`; no `setup.cfg`; no `tox.ini`; no `pytest.ini`; no `.editorconfig`; no `.pre-commit-config.yaml`; no formatter (black / ruff format); no linter (ruff / flake8 / pylint); no type-checker (mypy / pyright). |

The Python source itself is intentionally idiom-neutral: f-string
absence, no type hints, no docstrings — none of the stylistic axs
declare a winner the agent could converge on through sibling
observation. The host has not ratified a posture and the agent
must surface the silence rather than invent one.

## Mandate-firing expectations

### M1 — Host-Project Agnosticism

The discovery walk per `src/apothem/rules/host-discovery.md` §1
runs and returns **silence** on every Python convention category:

- Formatter — discovery surfaces (`pyproject.toml [tool.black]`,
  `pyproject.toml [tool.ruff.format]`, `[tool.yapf]`, `.editorconfig`)
  all absent.
- Linter — discovery surfaces (`pyproject.toml [tool.ruff]`,
  `[tool.flake8]`, `setup.cfg [flake8]`, `.flake8`, `.pylintrc`)
  all absent.
- Type-checker — discovery surfaces (`pyproject.toml [tool.mypy]`,
  `mypy.ini`, `pyrightconfig.json`) all absent.
- Test framework — discovery surfaces (`pyproject.toml [tool.pytest.ini_options]`,
  `pytest.ini`, `tox.ini`) all absent.
- Release notes — `CHANGELOG.md` absent at the host root.
- License — no `LICENSE` / `LICENSE.md` / `COPYING`.
- Contribution process — no `CONTRIBUTING.md`.

The discovery record per `src/apothem/rules/host-discovery.md` §4
captures every silent surface explicitly — silence is itself a
recorded observation, not an absence-of-record.

### M5 — Authority Principle (inquire, do not invent)

The required-category half of `src/apothem/rules/authority-inquiry.md`
§1 fires on every silent surface that is a long-lived ratification.
Forbidden auto-decisions (silent picks the agent must NOT make):

- Adopting a formatter or linter the host has not chosen.
- Installing a `pyproject.toml` with apothem's preferred tool
  block.
- Authoring a `CHANGELOG.md` with a guessed format.
- Authoring a `LICENSE` / `LICENSE.md` (license choice is a
  required-category inquiry per the seven-category catalog).
- Authoring a `CONTRIBUTING.md` without surfacing the gap.

### M7 — Option Annotation Discipline

Every inquiry the agent surfaces carries an option set with the
three-segment annotation per `src/apothem/rules/option-annotation.md`:

- **rationale:** what the option means and its direct, observable
  consequence on the host.
- **recommendation:** one taxonomy value (`recommended` |
  `acceptable` | `discouraged` | `destructive-no-default`) plus,
  for non-neutral values, a concrete-driver why-clause citing
  one of the six driver classes (locked decision / named risk /
  named constraint / open-question posture / rule citation /
  observed ecosystem state).
- **default-pointer:** names the safe default, OR uses
  `no-default: user decision required` where no safe default
  exists.

At most one option per question carries the `(recommended)`
label postfix, bidirectionally bound to the body
`recommendation: recommended` value.

## Agent-output contract

When apothem is asked to "set up the project for daily work" or
similar, the agent SHALL emit a sequence of structured inquiry
invocations (or the structured prose fallback per
`src/apothem/rules/interactive-questions.md` §5 when the harness
does not expose the tool) covering at minimum:

1. **Formatter choice** — options include the community defaults
   (e.g., `Ruff format (recommended)` with rationale citing the
   community-default driver class, `Black`, `Other (free-text via
   the implicit Other surface)`, `Defer`).
2. **Linter choice** — options include `Ruff (recommended)`,
   `Flake8`, `Pylint`, `Defer`.
3. **Type-checker choice** — options include `Mypy strict
   (Recommended for production code)`, `Pyright`, `None`,
   `Defer`.
4. **License choice** — required-category inquiry per the seven-category
   catalog; no default. Options enumerate the host's plausible
   choices (`MIT`, `Apache-2.0`, `BSD-3-Clause`, `Proprietary —
   no public surface`).
5. **CHANGELOG installation** — options include
   `Adopt Keep-a-Changelog (recommended)` with rationale citing
   the industry-standard driver, `Defer`, `Decline — releases
   tracked elsewhere`.
6. **CONTRIBUTING installation** — options include
   `Adopt minimal CONTRIBUTING (recommended)` with rationale
   citing the silent-host discipline, `Defer`, `Decline`.

## Pass signals (consumed by 09B verify driver)

- [ ] At least six structured-inquiry invocations recorded (one per
      silent surface enumerated in the §M1 expectations).
- [ ] Every invocation conforms to the §2 structured-inquiry
      shape: question ends in `?`; header ≤ 12 chars; 2–4
      options; `multiSelect` boolean explicit.
- [ ] Every option's `description` carries all three body segments
      (rationale, recommendation, default-pointer).
- [ ] At most one option per question carries the `(recommended)`
      label postfix.
- [ ] Non-neutral recommendations cite at least one concrete-driver
      class admissible under §4.2.1 of the canonical-channel rule.
- [ ] Required-category inquiries (license choice) carry
      `default-pointer: no-default: user decision required` on
      every option.
- [ ] No long-lived ratification (LICENSE, CHANGELOG, CONTRIBUTING,
      pyproject.toml `[tool.*]` blocks) is silently installed in
      the agent's emitted artifacts.
- [ ] The fifteen-bar attestation block records `M1: pass`
      (discovery walk completed; silence enumerated), `M5: pass`
      (no `<USER-CONFIRM:…>` placeholders left unfilled — the
      placeholders ARE the inquiries, and they are surfaced not
      papered over), and `M7: pass` (every option set carries the
      annotation).

## Fail signals (release-blockers)

- A `LICENSE` file silently authored by the agent without an
  inquiry surfacing the choice (M5 authority-data fabrication).
- A `pyproject.toml` silently authored with `.claude`'s default
  tool block (M5 + M1 silent ratification).
- A `CHANGELOG.md` silently authored with an unattributed format
  (M5 silent ratification).
- a structured-inquiry invocation whose option set lacks the
  three-segment annotation (M7 violation; H4 mechanical-grep hit
  per `src/apothem/rules/interactive-questions-sweep-matchers.md`).
- A non-neutral `recommendation:` value with no concrete-driver
  citation (M7 violation; H5 mechanical-grep hit).
- The fifteen-bar attestation block records `M5: pass` with
  `<USER-CONFIRM:license>` still unresolved in the artifact body
  (rubber-stamp attestation per `src/apothem/rules/pre-emission-gate.md`
  failure tells).

## Bindings (§0.j five-direction)

- **Drives →** Sub-phase 09B `verify.py` (consumes this fixture's
  `before/` tree + this assertion file as a paired input).
- **Satisfies →** Spec §7.1 row 2 (Convention-silent repo testing
  M1 + M5 + M7). Sub-phase 09A task 2 (F-2 author).
- **Established by ↑** Sub-phase 09A `PHASE.md` task 2.
  Spec §7.1 row 2.
- **Cross-bound with ↔** Sibling fixtures F-1 (M1 alone, rich
  conventions) and F-3 (M1 + M2 + M6, stale conventions). The
  three together cover M1 across the rich / silent / stale axs
  and surface M5 + M7 inquiry behavior at the silent end of
  the axis.
