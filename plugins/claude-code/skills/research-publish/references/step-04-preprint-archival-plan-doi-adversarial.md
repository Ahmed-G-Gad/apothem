<!-- SPDX-License-Identifier: MIT -->

### Phase 4 — Preprint/Archival Plan, DOI, & Adversarial Verification

**Select the open-access route and license (R8).** Record the open-access route the operator chooses — gold (open at the publisher), green (self-archived in a repository), diamond (no author or reader fee), or closed where the venue admits no OA — and the **license** that governs reuse (a Creative Commons license such as CC BY for the manuscript, and a separate open-source license for the released code). The OA route and the licenses are operator decisions ratified through the structured-inquiry channel; none is assumed, and a restrictive default is never silently applied (FAIR/open-science, <https://www.nature.com/articles/sdata201618>).

**Deposit the data and code to an archive beyond the reserved DOI (R8).** Plan the **Zenodo (or equivalent archival-repository) deposit** of the dataset, the analysis code, and the containerized environment so the artifacts carry their own persistent, citable, version-pinned identifiers — not merely a DOI reserved for the paper. The deposit plan names the archive, the artifact set, the license per artifact, and the minted concept-and-version DOIs; the deposit is the open-science guarantee that the evidence outlives the venue (<https://www.nature.com/articles/sdata201618>).

**Scale the reproducibility-evidence package to the venue ambition (N17).** The evidence package deposited alongside the manuscript — the dataset, the analysis code, the pinned/containerized environment, the run logs, the statistics outputs, the compute-utilization manifest, the full per-instance results, and the convergence/distribution figures — is the **venue-scaled evidence package** that scaffolds the deliverable: its depth MUST scale to the target-venue ambition, deeper for a higher-ambition venue and no lighter than the venue's stated reproducibility bar. Where the target-venue ambition is unspecified it surfaces as a `<USER-CONFIRM:kind=venue-ambition>` placeholder through the structured-inquiry channel rather than an assumed tier, and the submission-checklist depth (the number and stringency of reproducibility lines) scales to that same ambition (N17).

**Carry the registered-report Stage-2 path where one was preregistered.** When the design stage froze a registered-report Stage-1 protocol, record the **Stage-2 submission route** — the in-principle-acceptance reference and the venue's Stage-2 manuscript requirements — so the accepted protocol's results submission is assembled against the right contract (R5/R8).

**Compose the preprint/archival plan:** the preprint server (per `--preprint` or the Phase 1 inquiry), the timing relative to submission (the venue's preprint policy governs whether the preprint precedes, accompanies, or follows submission), and the **reserved DOI** the archival deposit mints — a real, resolvable identifier reserved through the minting authority, never a fabricated string (R4, R6). When the venue forbids preprinting, the plan records the prohibition and the archival alternative (post-acceptance institutional deposit).

**Then verify the package refute-by-default** across two surfaces through `agents/fact-checker.md`:

- **Citation resolution** — every citation is treated as unresolved until it dereferences to a real source; each reference in the formatted manuscript is re-checked against its permalink/DOI, and any phantom or moved citation is flagged (R4).
- **Declaration completeness and accuracy** — every venue-required declaration is present, the ethics/COI/data-availability facts match the suite's recorded authoritative data, and no declaration carries an invented value (R6).

Dispatch the verification as an **Audit Team** per `rules/agent-orchestration.md` when 3+ independent reference clusters justify parallel fan-out; each agent returns a pass/fail verdict plus resolution evidence under the 200-token audit return contract.

**Then run the submission checklist.** Every venue requirement — template conformance, page/word limit, anonymization, figure format, each required declaration, the data/code statement, the cover letter, the preprint/DOI plan — is a checklist line with a `met` / `unmet` verdict and the evidence for `met`. A single `unmet` line holds the package at `not-ready`; only an all-`met` checklist earns the `ready` verdict.
