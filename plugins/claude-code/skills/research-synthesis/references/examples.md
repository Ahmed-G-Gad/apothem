<!-- SPDX-License-Identifier: MIT -->

## Example — Standard synthesis run

```text
$ /research-synthesis --suite-name transformer-efficiency-survey --matrix-dimensions method,dataset,metric,assumption

[Gate] source-ledger.md + sources/ present; predecessor attestation clean. Proceed.
[Phase 1] Ingested 40 extractions. Claim inventory: 86 load-bearing claims keyed by source ID; clustered into 9 topics.
[Phase 2] Matrix built: 40 rows × 4 dimensions. 17 cells marked '—' (explicit coverage gaps).
[Phase 3] fact-checker Audit Team (4 agents) over 86 claims: 61 corroborated, 18 contested, 7 unverified.
[Phase 4] source-synthesis reconciled the 61 corroborated claims into the SOTA map. Gap statement: "Prior work characterizes attention-sparsity speedups on dense GPUs but leaves the latency profile under memory-bound edge accelerators uncharacterized."
[Phase 5] Fifteen-bar gate PASS; M5 zero phantom citations (86/86 resolve); M8 gap statement hedge-free.
[Phase 5] synthesis.md emitted; Handoff Manifest updated; downstream: /research-design.
```
