<!-- SPDX-License-Identifier: MIT -->

### Phase 2 — Run the Preregistered Tests with Effect Sizes & CIs

Run exactly the tests the preregistration committed to, on the variables it named, at the alpha it declared — no additions, no substitutions outside the deviation flow.

- **Assumption-check each test first** (normality, homogeneity of variance, independence, the test's own preconditions). A failed check is never silently ignored: a planned-test substitution routes to the Phase 4 deviation flow as a disclosed deviation, never a silent swap.
- **Report the effect size with its confidence interval as the primary evidence** — Cohen's *d*, Hedges' *g*, odds ratio, *r*, η², or the host-discovered measure appropriate to the test. The p-value appears alongside, never alone (R7).
- **Record null results with full rigor.** A test that fails to reject the null is a finding, reported with its effect-size CI bracketing the null — never dropped (R3).
- **Honor the empirical-comparison repetition floor for stochastic method-instances.** A method whose outcome depends on a random draw MUST be summarized over at least thirty independent repetitions per instance/condition — raised until the summary statistics are stable when the repetition spread is wide relative to the differences under test — reporting the **best / mean / median / standard deviation / worst** of the primary metric per condition rather than a single point estimate, and computing the effect-size confidence interval over the repetition distribution; a deterministic method-instance reports its single observed value marked deterministic (R2/R7; `skills/research-suite/references/empirical-comparison-rigor.md`).

Discover and honor the host's ratified statistics toolchain per `rules/host-discovery.md`; the analysis code passes the host's lint / format / type-check per `rules/code-craft-python.md` (or the host's per-language sibling). Externalise the per-test computations to the host-natural analysis location so every reported number is reproducible (R2).
