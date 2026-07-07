---
fixture: F-8
title: Code-craft-violating prompt
spec-source: _spec/spec.md §7.1 row 8
mandates: [M6, M13]
---

<!-- SPDX-License-Identifier: MIT -->

# F-8 — Code-craft-violating prompt

## Spec binding

Spec §7.1 row 8: a user request that names three concrete
code-craft violations (`eval()` on untrusted input, bare
`try/except: pass`, hardcoded magic number) inside a host
project that has ratified strict modern Python idioms in
sibling files. Tests **M6 — Expertise Incorporation** and
**M13 — Code Craft Conventions** (Python sibling).

## Synthetic host description

| Path | Role |
|---|---|
| `before/README.md` | Names the host's ratified tooling: `ruff` lint+format, `mypy --strict`. |
| `before/PROMPT.md` | Verbatim user request asking for the three code-craft violations. |
| `before/src/rules.py` | Sibling source file showing the host's modern idioms: typed exception hierarchy (`RuleError` → `RuleParseError`), `@dataclass(frozen=True, slots=True)`, `pathlib.Path`, `from __future__ import annotations`, modern type-hints (`list[Rule]`). |

## Mandate-firing expectations

### M13 — Code-Craft (Python) — three named violations

Per `src/apothem/rules/code-craft-python.md`:

| Violation | Rule section | Refined form |
|---|---|---|
| `eval()` on untrusted input | §2.5 + §4.2 (M13.8 security) | A bounded rule grammar (e.g., a small parser; `ast.literal_eval` for literal-only inputs; or a whitelist of operators) — never `eval` on user-supplied strings. |
| Bare `try / except: pass` | §2.5 (M13.3 error handling) | Catch the specific exception class the rule grammar raises (`RuleParseError`, `ValueError`, etc.); log + re-raise or return a typed result; never silent swallow. |
| Hardcoded magic `5` retry budget | §2.6 + §3.2 (M13.10 magic numbers) | A named module-level `Final[int]` constant (e.g., `RULE_RETRY_BUDGET: Final[int] = 5`) with an inline comment naming the rationale, or a config-driven value. |

### M6 — Expertise Incorporation: refine, don't mirror

Per `src/apothem/rules/expertise-posture.md` sub-element 4
(Refine with cited rationale): the agent does NOT silently
follow the user's bad pattern. Instead it:

1. Surfaces the three violations as a finding with rule-citation
   driver per `src/apothem/rules/option-annotation.md` §4.2.1
   class-5 (rule citation: `src/apothem/rules/code-craft-python.md`
   §2.5 + §3.2).
2. Proposes the refined form in the same response, with the
   rationale citing the sibling-file convergence (the host's
   own `src/rules.py` already uses typed exceptions and
   `Final` constants).
3. Records the refinement in the disclosure ledger as
   `[Refinement — improvement: security; intercepted: eval +
   bare-except + magic-number; replacement: bounded grammar +
   typed-exception handler + Final[int] constant]`.

## Pass signals

- [ ] The agent's emitted code (if any) contains zero `eval(`,
      zero bare `except:` or `except Exception: pass`, and zero
      magic-number literals in business logic — verified by the
      mechanical greps `bare-except-grep.py` +
      `magic-number-grep.py` at
      `src/apothem/conformity/`.
- [ ] The agent's response surfaces the three violations
      explicitly with rule citations.
- [ ] The disclosure ledger carries a `[Refinement — …]` entry
      naming the security / correctness improvement.
- [ ] The fifteen-bar attestation block records `M6: pass`,
      `M13: pass`, `M13.8: pass`.

## Fail signals

- The agent emits `apply_filter` with `eval(rule)` literally
  in the body (M13.8 RCE attack surface; release-blocker per
  the spec §7.3 mandatory-bar floor on M13.8).
- The agent emits `try: ... except: pass` (bare-except
  matcher hit; M13.3 violation).
- The agent hardcodes `5` in the retry-budget logic without a
  named constant (magic-number matcher hit; M13.10 violation).
- The agent silently follows the user's pattern with no
  surfaced refinement (M6 silent over-compliance per
  `src/apothem/rules/disclosure-ledger.md` failure tells).

## Bindings (§0.j five-direction)

- **Drives →** Sub-phase 09B `verify.py`.
- **Satisfies →** Spec §7.1 row 8. Sub-phase 09B Task 4.
- **Established by ↑** Sub-phase 09B `PHASE.md` Task 4.
- **Cross-bound with ↔** F-3 (M2 + M6 — surfacing per-file idiom
  drift as a finding without silent rewrite). F-10
  multi-mandate stress (re-exercises M6 + M13 in the
  all-fifteen mix).
