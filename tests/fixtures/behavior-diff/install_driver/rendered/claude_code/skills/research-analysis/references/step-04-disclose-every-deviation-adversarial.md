<!-- SPDX-License-Identifier: MIT -->

### Phase 4 — Disclose Every Deviation & Adversarial Verification

**Build the pre-specified-vs-exploratory split table.** Partition every reported result into two explicit classes in a table: **pre-specified** (the test was named in the frozen preregistration, on the variable it named, at the alpha it declared — a confirmatory result) and **exploratory** (the test was not in the preregistration — a hypothesis-generating result by construction). Each row names the result, its class, and — for exploratory rows — that it is hypothesis-generating and carries no confirmatory weight. The split table is the structural guard against HARKing (hypothesizing after results are known); an exploratory result presented as confirmatory is a discipline failure the table makes visible (R5, NASEM 2019 <https://nap.nationalacademies.org/catalog/25303/>).

**Compose the disclosed-deviation ledger.** Every departure from the frozen plan — a test substituted after a failed assumption check, a correction added for an unanticipated family, a changed alpha, a data-triggered exclusion, a robustness check the plan did not name — is logged with its rationale and its effect on the result it altered, in the same artifact that reports that result (R5). The analysis *is* the deviation's disclosure surface; nothing is deferred to the paper.

**Run the computational-reproducibility re-run (R8).** Re-execute the analysis end-to-end from the raw data inside the experiment stage's containerized or pinned environment, and confirm every reported number reproduces bit-for-bit (or within a stated numerical tolerance). The re-run is the open-science guarantee that the result is not an artifact of an un-pinned toolchain or an unrecorded manual step; a number that fails to reproduce on the clean re-run is a finding surfaced here, not in the paper (R2/R8).

**Then verify refute-by-default.** Route every reported result through `agents/fact-checker.md`, which treats each effect as false until the computation forces otherwise — re-deriving the headline numbers from the raw data and the recorded invocation (R2), confirming each effect carries its CI (R7), confirming each result's pre-specified-vs-exploratory class, and confirming each deviation carries its disclosure (R5). It assigns a cited verdict per result:

- **`confirmed`** — the computation reproduces the reported effect and its CI; any deviation is disclosed. Only `confirmed` results anchor the paper's claims.
- **`fragile`** — the effect does not survive the robustness battery. Reported with the breaking perturbation named.
- **`unverified`** — the computation cannot be reproduced from the recorded invocation. Reported with its failure named.

Dispatch the verification as an **Audit Team** per `rules/agent-orchestration.md` when 3+ independent results justify parallel fan-out; each agent returns a pass/fail verdict plus re-derived evidence under the 200-token audit return contract.
