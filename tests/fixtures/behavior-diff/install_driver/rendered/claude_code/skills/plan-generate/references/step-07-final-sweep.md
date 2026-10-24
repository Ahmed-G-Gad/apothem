<!-- SPDX-License-Identifier: MIT -->

### Step 7: Final Sweep

Deploy an Audit Team (CM-25A) for parallel traceability, naming, dependency, and contract checks. Verify all generated artifacts follow the harness conventions (CM-22, §1). Phase files are located at `phases/**/PHASE.md`.

**7A — Prose Fidelity (CM-11A).** Forward + reverse traceability. Scorecard: PASS / CONDITIONAL / FAIL. (At SHARED+. Spot-check at PERSONAL_USE. Skip at EXPLORING.)

**7A→7B Bridge.** Prose-fidelity findings feed consistency checks — REINTERPRETED requirements trigger naming verification, split requirements trigger contract checks, WEAK traceability triggers dependency audits.

**7B — Internal Consistency (CM-11B).** Decisions, dependencies, naming, interfaces, preamble compliance, index accuracy. Scorecard. (At SHARED+.)

**7C — Completeness.** Appendix checklist. Key assertions. Top 3 risks. Highest-impact phase (single binding constraint per CM-8). Confirm PROGRESS.md and PLAN-NOTES.md remain bounded / index-first and that detailed emissions have `_outputs/` or REPORT.md targets.

**7D — Creative Quality (CM-21).** Language-standards compliance (no forbidden phrases). Originality threshold (at least one structurally novel element in architectural decisions). Named frameworks present for key concepts. Cognitive-filter seriousness scaling per cognitive identity rule, Section 2.

**7E — Plan-Internal Isolation Readiness (CM-7).** Verify that ALL generated phase-file content — task descriptions, acceptance criteria, scope statements, commit guidance, verification assertions — uses natural domain language that will not leak plan-internal terminology into execution artifacts. Specifically: (a) task descriptions describe WHAT to build in domain terms, never referencing plan structure ("implement the D2 decision" → "implement OAuth2 with PKCE"); (b) acceptance criteria are domain-testable, not plan-process-testable ("Phase 03 outputs verified" → "authentication endpoint returns valid JWT"); (c) scope boundaries reference functional areas, not plan-internal identifiers; (d) verification assertions test domain behavior, not plan conformity. Any content that would encourage CM-7 forbidden terms (CLAUDE.md CM-7) to appear in protected artifacts during execution is rewritten in domain language before presenting.

**FAIL → revise before presenting (max 2 cycles).** Root-cause fixes only — address structural issues, not surface symptoms. If still failing after 2 revision cycles, escalate to the user with findings (CM-18).

**7F — Update PROGRESS.md Scorecards.** Write scorecard grades from executed steps only to the PROGRESS.md Review Summary section (replacing the "pending" placeholders from Step 5). Also write grades to PLAN-NOTES.md `## Generation Scorecards` so plan-execute's Review Gate can find them as a fallback. Leave unexecuted scorecard grades as "N/A — skipped at [LEVEL]" (e.g., Internal Consistency is N/A at PERSONAL_USE since Step 7B runs only at SHARED+).
