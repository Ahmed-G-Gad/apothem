<!-- SPDX-License-Identifier: MIT -->

### Phase 3 — Adversarial Verification (refute-by-default)

Route every load-bearing claim destined for the SOTA map through `agents/fact-checker.md` adversarial verification. The fact-checker treats each claim as false until ≥2 independent sources force otherwise, seeks the strongest counter-evidence first (Filter 3 Inversion Press), and assigns a cited verdict per claim:

| Verdict | Condition | Destination |
| ------- | --------- | ----------- |
| `corroborated` | Two or more independent sources agree; no surviving counter-evidence. | Anchors the SOTA map. |
| `contested` | Sources disagree; both positions carry evidence. | Contested-findings ledger (both positions + evidence). |
| `unverified` | No independent corroboration. | Contested-findings ledger. |

A claim defaults to contested-or-unverified when evidence is insufficient, never a charitable `corroborated`. Only `corroborated` claims anchor the SOTA map (R1, R3). Dispatch the verification as an Audit Team per `rules/agent-orchestration.md` when the claim count justifies parallel fan-out (3+ independent claims); each agent returns a pass/fail verdict plus cited evidence under the 200-token audit return contract.
