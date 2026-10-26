<!-- SPDX-License-Identifier: MIT -->

## Example — Standard design run

```text
$ /research-design --suite-name edge-attention-latency --design between-subjects --alpha 0.05 --power 0.80

[Gate] synthesis.md gap + research-spec.md present; predecessor attestation clean. Proceed.
[Phase 1] Gap + 3 falsifiable hypotheses extracted. All refutable (R3 confirmed). Provenance carried per hypothesis.
[Phase 2] 5 operational predictions; each names its refuting outcome. Design type confirmed: between-subjects. Positive and negative controls planned, each with a pass criterion.
[Phase 3] Variable table: 1 IV (sparsity mode × 2 levels), 2 DVs (p50/p99 latency), 4 controls (each ruling out a named confound). Unit = benchmark run; seeded schedule; machine blocked, run order interleaved across modes. Instruments cited; sample frame touches no human subjects → R6 N/A.
[Phase 4] SESOI d=0.6 from the spec's p99 success metric; synthesis source S-019 (single study, d=0.8) bounds the plausible range only. Goal: superiority, two-sided, 1:1 allocation. N=55/group at the corrected per-test α=0.025 (Bonferroni across 2 primary DVs), power=0.80; effect-range table d=0.4–0.8 recorded (121 to 31 per group). 10% unusable runs expected → 62 runs collected per group. Fixed-N stopping rule.
[Phase 5] Threats-to-validity ledger: 3 internal, 2 external, 1 construct, 1 statistical-conclusion — each mitigated or acknowledged. Preregistration FROZEN at 2026-06-15T14:02:11Z.
[Phase 6] Fifteen-bar gate PASS; M5 zero invented quantitative inputs; M8 predictions hedge-free.
[Phase 6] study-design.md + preregistration.md emitted; Handoff Manifest updated; downstream: /research-experiment.
```
