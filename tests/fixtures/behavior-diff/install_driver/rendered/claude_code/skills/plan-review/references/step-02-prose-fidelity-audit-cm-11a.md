<!-- SPDX-License-Identifier: MIT -->

### Step 2: Prose Fidelity Audit (CM-11A)

> Skip if `--focus` excludes `prose-fidelity` / `completeness` / `all`. Skip at EXPLORING seriousness. **Focus-seriousness conflict check:** after resolving `--focus` dimensions, if the current seriousness level would skip ALL focused dimensions (e.g., `--focus prose-fidelity` at EXPLORING), invoke the structured-inquiry channel: question `At the current seriousness level, the focused dimensions are skipped by default; how should the review proceed?`; header `Scope conflict`; options:
>
> - `Raise seriousness (Recommended)`:
>   rationale: Temporarily escalates the seriousness tier for this review so the focused dimensions run; the original tier restores after the review completes.
>   recommendation: recommended — cites class 5 rule citation: the seriousness-scaling discipline (Seriousness-Scaled Governance — escalating to satisfy a focused-dimension audit preserves the audit's evidence requirement) and class 6 observed-state: the operator explicitly named the focused dimensions, indicating they want those dimensions audited.
>   default-pointer: Raise seriousness — safe because the escalation is scoped to this review only and produces the audit evidence the operator requested.
> - `Broaden focus`:
>   rationale: Expands `--focus` to include dimensions available at the current tier; the originally-named dimensions are dropped from the audited set.
>   recommendation: acceptable
>   default-pointer: Raise seriousness — broadening focus drops the operator's named dimensions from coverage; raising seriousness preserves coverage of the named dimensions.
> - `Abort`:
>   rationale: Halts the review; the next invocation can resume with adjusted parameters.
>   recommendation: acceptable
>   default-pointer: Raise seriousness — aborting forces a re-bootstrap; raising seriousness completes the review in the same session.
> `multiSelect: false`. At PERSONAL_USE: spot-check mode — select 5 representative requirements spanning different functional areas, trace forward only (Step 2.1), produce a scorecard on the sample. At SHARED+: full exhaustive audit as specified below.

Deploy an Audit Team (CM-25A) — parallel per-phase traceability. Each agent returns traceability findings with evidence citations (CM-25C).

**2.1 — Forward (Prose→Plan).** Extract EVERY requirement from the original prose — not a sample, not the obvious ones, ALL of them. Assign sequential IDs (R1, R2, R3...). Trace each to a specific phase and specific task. Classify each mapping:

- **STRONG:** the requirement is fully and faithfully represented in a specific task with matching acceptance criteria.
- **WEAK:** partially represented — some aspect is covered but nuance, scope, or specificity is lost.
- **ABSENT:** no corresponding task anywhere in the plan. A Critical finding.
- **REINTERPRETED:** present but materially altered in meaning. Quote both the original prose and the plan's rendering side by side. Requires user confirmation.

**2.2 — Reverse (Plan→Prose).** For EVERY task in EVERY phase, trace back to the prose requirement it implements. Classify:

- **JUSTIFIED:** the task directly implements a prose requirement.
- **UNJUSTIFIED:** the task has no prose basis — it may be a valid domain-standard addition, but it must be flagged and justified. (At PUBLIC_LAUNCH: mandatory for all tasks with full reverse traceability and justification. At SHARED: reverse traceability executed — flag unjustified tasks, accept valid domain-standard additions with brief rationale.)

**2.3 — Nuance Preservation.** Examine specifically:

- Subtle intentions — does the plan capture what the user *meant*, not just what they *said*?
- Thresholds and quantities — are specific numbers preserved verbatim?
- Examples — are user-provided examples expanded into patterns, not flattened?
- Negatives — are "do NOT" and exclusion requirements captured as explicit OUT-of-scope items?
- Hedging and uncertainty — where the user expressed uncertainty, does the plan reflect that as a decision point instead of silently resolving it?

**2.4 — Scope Drift.** Identify every plan item with no prose basis. For each: either justify it as a necessary technical implementation detail or flag it as scope drift. Identify every reinterpretation — quote both the original prose and the plan's rendering side by side.

**2.5 — Emphasis Alignment.** Is plan emphasis proportional to prose emphasis? If the user spent 40% of their prose on feature X, does the plan allocate proportional attention? Disproportionate emphasis (inflated or deflated) is a finding.

**2.6 — Scorecard.** Grade per CM-11A scoring criteria:

- **PASS:** ≥90% STRONG, 0 ABSENT.
- **CONDITIONAL:** ≥75% STRONG, ≤2 ABSENT.
- **FAIL:** below CONDITIONAL thresholds.

Record the full traceability matrix and scorecard.
