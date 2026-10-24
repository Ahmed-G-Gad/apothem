<!-- SPDX-License-Identifier: MIT -->

### Phase 4 — Adversarial Verification & Readiness Checklist

**Verify the plan refute-by-default** across two surfaces through `agents/fact-checker.md`:

- **Archival-identifier resolution** — every persistent identifier (the reserved DOI, the archival accession) is treated as unresolved until it dereferences to a real deposit; any phantom or unresolvable identifier is flagged and blocks the plan line (R8).
- **Public-artifact claim match** — every claim in every public artifact is re-checked against the published paper; a claim the paper does not make is flagged as an invented or overstated claim and blocks the artifact (R4).

Dispatch the verification as an **Audit Team** per `rules/agent-orchestration.md` when 3+ independent identifier clusters or artifact drafts justify parallel fan-out; each agent returns a pass/fail verdict plus resolution evidence under the 200-token audit return contract.

**Then run the dissemination-readiness checklist.** Every dissemination requirement — the preprint announcement, each public artifact, the FAIR deposit, the impact-tracking plan, the revision loop, the registered-report path — is a checklist line with a `met` / `unmet` verdict and the evidence for `met`. A single `unmet` line holds the plan at `not-ready`; only an all-`met` checklist earns the `ready` verdict.
