<!-- SPDX-License-Identifier: MIT -->

## Example — Standard run with a computational protocol

```text
$ /research-experiment --suite-name edge-attention-latency --data-dir data/ --seed 1729

[Gate] study-design.md + preregistration.md present; predecessor attestation clean. Proceed.
[Phase 1] Read design + frozen preregistration. All 7 protocol steps executable. Data destination data/ ratified (Infrastructure inquiry). Env snapshot captured: Ubuntu 24.04, Python 3.12.4, 6 pinned deps, 1×A100. Seed 1729 recorded. R6: no human subjects → declarations cover the run.
[Phase 2] Executed 7 steps; test-runner dispatched for the 3 computational steps. Each step logged on run. 132 trials total: 118 confirming, 9 null, 5 failed (all logged). 1 deviation (step 4 batch size halved on OOM) → Deviation Ledger; preregistration NOT edited.
[Phase 3] Raw data written to data/latency-runs.parquet (append-only). Schema recorded (8 columns + units). 3 missing values marked with reason.
[Phase 4] reproducibility-manifest.md composed: env + seed 1729 + 6 commit-pinned deps + per-file content hash + re-run recipe.
[Phase 5] Fifteen-bar gate PASS; M5 zero fabricated facts; M8 deviations stated not hedged.
[Phase 5] experiment-log.md + reproducibility-manifest.md emitted; Handoff Manifest updated; downstream: /research-analysis.
```
