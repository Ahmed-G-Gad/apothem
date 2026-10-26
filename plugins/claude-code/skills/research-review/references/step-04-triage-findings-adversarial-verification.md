<!-- SPDX-License-Identifier: MIT -->

### Phase 4 — Triage Findings & Adversarial Verification

Compose the severity-triaged required-revision list. Each finding carries its severity and a concrete-driver rationale per `rules/interactive-questions-canonical-shapes.md` §3.2.1 — never a bare opinion:

- **HIGH.** A defect that blocks acceptance at the venue bar: a novelty claim the synthesis refutes, a confirmatory result with no preregistered test (R5), a reported number that diverges from the analysis, a phantom citation (R4), an absent ethics declaration the venue requires (R6), a result with no reproducibility path (R2), an experimental image with an undisclosed splice, composite, or processing step, a registered outcome that differs from the reported one with no reported reason (R5).
- **MEDIUM.** A defect that materially weakens the paper but does not block acceptance alone: an effect reported without its confidence interval (R7), a threat-to-validity the design named but the discussion ignores, a figure that is not self-describing, a figure whose encoding misleads or that cannot be read without colour (`skills/research-suite/references/figure-integrity.md`), a related-work omission the synthesis flags.
- **LOW.** A defect of clarity or polish: a hedge where the result is firm (`rules/definitiveness.md`), an inconsistent term, a citation-style deviation, a structural-ordering slip against the venue's expected shape.

**Then verify refute-by-default.** Route every finding through `agents/fact-checker.md`, which treats each finding as unproven until the manuscript locus and cross-checked evidence force it — confirming the finding cites a real defect at a real locus (not a misreading of the paper) and that the severity matches the venue bar. It assigns a cited verdict per finding:

- **`confirmed`** — the defect is real and the severity holds. Enters the required-revision list.
- **`downgraded`** — the defect is real but the severity is lower than assigned. Enters the list at the corrected severity.
- **`withdrawn`** — the finding is a misreading. Dropped, with the misreading named so the count stays honest.

**The overall verdict is an explicit ADVANCE GATE.** A paper advances past review only when it clears the venue bar convincingly *and* significantly with no unresolved HIGH finding — a paper carrying an unresolved HIGH finding, or an improvement claimed without statistical significance over its comparators, does not clear the gate and earns `major-revision` or `reject`, never `accept`. Each clearance is logged so every advance is auditable after the fact per `skills/research-suite/references/advancement-gate.md`.

When `--blind` ran, reconcile the blind findings against any prior review at this step per `rules/planning-techniques.md` §6, surfacing the delta the prior-anchored review missed.
