<!-- SPDX-License-Identifier: MIT -->

### Phase 1 — Ingest the Raw Data & the Frozen Plan

**Read the plan before the data.** Open `{suite}/_inputs/preregistration.md` in full *first*: the frozen plan is authoritative over every analysis choice, and reading it ahead of the data is what keeps the analysis from drifting toward whichever framing the data flatters (R5). Then read `{suite}/_outputs/experiment-log.md` and `{suite}/_outputs/reproducibility-manifest.md` to resolve the raw-data location, the seed, and the environment pins, and ingest the raw data per the locate-before-read discipline at `rules/large-file-reading.md`.

Build the **analysis inventory** — for each preregistered test: its variables, its planned statistic, its declared alpha and tail, its independent unit of analysis, any preregistered fallback test, and its place in any comparison family — plus the declared correction method and the robustness/sensitivity checks the plan committed to. When the inventory exceeds a single pass, externalise it to `{suite}/_inputs/analysis-plan.md` (a free-form `{kebab-case-topic}.md` scratch file per `rules/context-management-scratch.md` §1).

**Integrity check before any test runs.** Verify the raw data against the reproducibility manifest's expected shape — row count, variable set, value ranges. A mismatch is a finding surfaced *here*, before a single statistic is computed. Record the missing-value count per variable and condition at the same point.
