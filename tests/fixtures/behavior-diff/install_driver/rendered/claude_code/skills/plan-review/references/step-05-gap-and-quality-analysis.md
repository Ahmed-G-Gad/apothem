<!-- SPDX-License-Identifier: MIT -->

### Step 4: Gap and Quality Analysis

> Skip if `--focus` excludes `quality` / `standards` / `domain` / `architecture` / `completeness` / `all`.

Deploy an Audit Team (CM-25A) — parallel per-dimension analysis. Prose-anchored: every gap classified as prose-relative or domain-standard-relative.

**4.1 — Completeness.** Are there functional areas implied by the project scope that no phase addresses? Edge cases that should be handled but are not mentioned? Integration points assumed but not explicitly tasked? Deployment, monitoring, or operational concerns that are missing?

**4.2 — Quality (TM-13 thresholds and success metrics).** For every phase: (a) does it have a clear, measurable success metric? (b) are acceptance criteria specific and testable? (c) do task counts stay within the ≤10 task, ≤5 file, ≤2000 token thresholds? (d) are mixed concerns properly separated? Any phase exceeding thresholds without a sub-phase split is a finding.

**4.3 — Standards.** Does the plan specify all necessary technical standards — linting, formatting, type checking, testing framework, code-coverage targets, security scanning, documentation format? Are these consistent with the preamble's mandates?

**4.4 — Domain Bundles.** Based on the declared domain, are domain-specific requirements addressed? (Web app: accessibility, CORS, CSP, rate limiting, auth. ML: reproducibility, data versioning, experiment tracking. API: versioning, pagination, error codes, rate limiting.)

**4.5 — Architecture (roadmap, milestones, layer compliance).** Is the week-by-week roadmap realistic? Are milestones clear and measurable? Is the dependency graph optimized for parallelization? Is Phase 1 delivering the fastest path to a first tangible result? **Layer boundary verification (CM-27):** if the project warrants clean architecture (3+ modules, SHARED+ seriousness, or the preamble declares layer structure), verify: (a) phases producing domain logic do not introduce infrastructure imports, (b) the dependency direction between planned modules respects the inward-only rule (Domain ← Application ← Infrastructure/Presentation), (c) testing strategy aligns with layer boundaries (domain = pure unit, application = mocked interfaces, infrastructure = integration), (d) no phase task bundles cross-cutting concerns that should be separated across layers.

**4.6 — Creative Quality (CM-21).** A mandatory quality gate, not a decorative assessment.

- **Language-standards compliance:** scan EVERY file for forbidden phrases (cognitive identity rule, Section 4). Any occurrence is a finding. Scan for required qualities (specificity, surprise, internal logic, generativity, tension) in substantive sections — architectural decisions, scope descriptions, strategic analysis.
- **Originality assessment:** does the plan contain at least one structurally novel element per substantive architectural decision? Are key concepts given named frameworks? Does the overall design demonstrate conceptual elegance or merely functional adequacy?
- **Filter 1 (Obvious Purge) compliance:** is there evidence that obvious / default solutions were identified and rejected in favor of non-obvious alternatives? If every architectural choice is the "standard" approach, this gate fails.
- **Filter 2 (Domain Exile) compliance:** is there evidence the problem was reframed through at least one foreign discipline?
- **Filter 3 (Inversion Press) compliance:** does at least one inverted assumption survive into the plan's design decisions?
- **Filter 4 (Combinatorial Explosion) compliance:** is there at least one cross-domain synthesis in the plan's architectural decisions?
- **Filter 5 (Aesthetic Demand):** would this plan make a staff engineer stop and think *"I have never approached it that way"*? Apply this as a final quality bar.
- **Seriousness scaling:** per cognitive identity rule, Section 2.
