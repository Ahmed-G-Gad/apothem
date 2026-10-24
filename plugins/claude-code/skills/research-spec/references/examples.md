<!-- SPDX-License-Identifier: MIT -->

## Example — Default framing run

```text
$ /research-spec ./notes/cache-eviction-idea.md --suite-name cache-eviction-study

[Phase 1] Read 1 notes file (3.2K tokens). Triple-extracted: claim "LRU loses to ARC under scan-heavy workloads"; scope "key-value caches"; success condition "measurable hit-rate delta".
[Phase 1] Suite folder created: <project-root>/.apothem/plans/cache-eviction-study/_spec/.
[Phase 2] Crystallized 2 falsifiable hypotheses. H1 null: "ARC hit-rate ≤ LRU hit-rate under scan workload W". H2 carried a non-refutable framing → structured inquiry fired → re-framed with a null.
[Phase 3] Scope drawn. Inclusion: read-heavy KV caches, ≥1M ops/run. Exclusion: write-through caches, distributed multi-node (one undefined boundary → inquiry → operator excluded multi-node).
[Phase 4] 1 success metric: hit-rate delta ≥ 3 percentage points, 95% CI excluding 0 (R7 effect-size form). Glossary: 6 terms defined.
[Phase 5] Question-Resolution Audit: 3 invocations, 3 resolved, 0 silent-defaulted. Fifteen-bar gate PASS.
[Phase 5] Promoted to _spec/research-spec.md; Handoff Manifest emitted; downstream: /research-theory.
```
