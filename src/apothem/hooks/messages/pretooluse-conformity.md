<!-- SPDX-License-Identifier: MIT -->

# Conformity-gate orchestrator (PreToolUse Write/Edit)

> Advisory: this hook reports; it does not block. Mechanical enforcement runs in CI.

The conformity-gate orchestrator at `<harness-root>/apothem/conformity/gate.py`
runs the registered per-Write greps against the Write/Edit tool input before the
tool fires. The orchestrator reads the harness's tool-input JSON from stdin,
extracts the content (Write `content` field, Edit `new_string` field) and the
target path, and dispatches every registered per-Write matcher via `importlib`.
Each grep returns a structured result; the orchestrator aggregates them into a
single JSON report. The findings are surfaced as an advisory nudge plus a
definitive next step — the per-Write surface does not block the tool call (the
EN-1 advisory-by-default posture). Strict enforcement runs separately in CI and
pre-commit via the corpus gate (`gate --all-perwrite --strict`).

## Per-Write grep coverage

The authoritative full set is `conformity/gate.py` `GREP_MODULES`; the per-Write
dispatch runs **every** registered matcher in that tuple (count derived from the
registry, never hardcoded here). The matchers partition into a small blocking set
(`_BLOCKING_PER_WRITE_GREPS` — deterministic, low-false-positive, green over the
tracked corpus, so a finding fails the strict corpus run) and the remaining
advisory set (`_ADVISORY_PER_WRITE_GREPS` — reported with a named remediation
owner per `_ADVISORY_RATIONALE`, never gating). Representative matchers and their
cited rules:

| Grep | Rule cited | Partition |
|------|------------|-----------|
| user-confirm-grep | M5 authority-inquiry-categories §1 | advisory |
| option-annotation-grep | M7 option-annotation | blocking |
| binding-reciprocity-grep | M10 bidirectional-binding §Notation | blocking |
| completion-claim-grep | M12 / M15 completion claims | blocking |
| unpinned-action-grep | M15 production-ready §Supply-chain | blocking |
| hedging-grep | M8 definitiveness §Hedging | advisory |
| secret-leak-grep | M13.8 + M15 production-ready | advisory |
| file-header-grep | SPDX authorship-header policy | advisory |
| always-on-budget-grep | token-budget-discipline §Always-on body budget | advisory |

The blocking-vs-advisory classification is asserted at import time
(`_assert_perwrite_partition`) so every registered matcher is classified.

## Performance budget

Per-grep wall-clock is bounded by `PER_GREP_BUDGET_SECONDS` (0.520 s) in
`gate.py`; `over_budget: true` in the JSON output flags a matcher that exceeded
it. The budget surfaces as a watch item in the report — it does not block the
write (the hook's own ceiling and the fail-open dispatcher govern hard limits).

## Exit / disposition contract

- **Advisory finding (per-Write hook):** the orchestrator surfaces the JSON
  report (one entry per matcher, with findings) and a recommended next step; the
  Write/Edit proceeds. The operator decides whether to address a finding before
  re-issuing.
- **Strict enforcement (CI / pre-commit corpus):** `gate --all-perwrite . --strict`
  exits non-zero when a **blocking** matcher reports a finding over the tracked
  corpus; that is where the conformity floor is enforced, not at the tool call.
- **Fail-disposition:** the dispatcher at `hooks/dispatch.py` is fail-open — any
  exception inside a matcher or the orchestrator converts to a structured failure
  envelope on stdout and the tool call proceeds, so a harness error never
  silently blocks a write.

## Action on a finding

The operator inspects the JSON report (one entry per matcher, with findings for
the matchers that flagged), addresses the reported violations in the candidate
content where warranted, and re-issues the Write/Edit. Each finding carries its
rule anchor for routing.

## Bindings (§0.j five-direction)

- **Drives →** The reading of the gate's advisory report on every Write and Edit: each finding is surfaced with a next step, and strict enforcement stays in CI and pre-commit. `conformity/gate.py` (the per-write matcher chain the `--hook` entry runs).
- **Established by ↑** The `gate.py --hook` PreToolUse Write and Edit entries in the harness settings templates. `rules/pre-emission-gate.md` (the gate whose mechanical bars the matchers check).
- **Cross-bound with ↔** `hooks/messages/pretooluse-askuserquestion-recommended.md` (the call-time `(Recommended)` check that complements the committed-artifact option-annotation matcher).
