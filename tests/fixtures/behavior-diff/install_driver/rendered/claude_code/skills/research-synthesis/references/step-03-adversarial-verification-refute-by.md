<!-- SPDX-License-Identifier: MIT -->

### Phase 3 — Adversarial Verification (refute-by-default)

Route every load-bearing claim destined for the SOTA map through `agents/fact-checker.md` adversarial verification. The fact-checker treats each claim as false until ≥2 independent sources force otherwise, seeks the strongest counter-evidence first (Filter 3 Inversion Press), and assigns a cited verdict per claim:

| Verdict | Condition | Destination |
| ------- | --------- | ----------- |
| `corroborated` | Two or more independent sources agree; no surviving counter-evidence. | Anchors the SOTA map. |
| `contested` | Sources disagree; both positions carry evidence. | Contested-findings ledger (both positions + evidence). |
| `unverified` | No independent corroboration. | Contested-findings ledger. |

Independence is judged on the underlying evidence. Sources that cite each other, reports that share a study id in the ledger, and studies that share a collected sample (a `shared-data` link) count as one source (`search-record.md` §7); two papers from one author group are checked for shared data before they count as two. A source whose `integrity-status` is `retracted` or `withdrawn` does not count toward `corroborated`, and one marked `concern` is never the sole support for a claim. A prior synthesis found in the search locates primary studies and does not count beside the studies it pools. Filter 3 starts from the ledger's `contrary` class; when that class retained nothing, the finding is recorded as `none found in the searches recorded`, never as consensus.

A claim defaults to contested-or-unverified when evidence is insufficient, never a charitable `corroborated`. Only `corroborated` claims anchor the SOTA map (R1, R3). Dispatch the verification as an Audit Team per `rules/agent-orchestration.md` when the claim count justifies parallel fan-out (3+ independent claims); each agent returns a pass/fail verdict plus cited evidence under the 200-token audit return contract.
