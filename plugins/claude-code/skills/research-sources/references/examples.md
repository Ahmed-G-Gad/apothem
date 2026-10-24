<!-- SPDX-License-Identifier: MIT -->

## Examples

### Example 1 — Standard collection run

```text
$ /research-sources <project-root>/.apothem/plans/transformer-efficiency-survey

[Phase 1] Reading ratified research-spec.md. 4 falsifiable hypotheses; inclusion criteria: peer-reviewed OR arXiv-with-code, 2020+, English. Decomposed into 6 orthogonal sub-queries.
[Phase 1] Source budget unfixed; structured inquiry fired — operator set --max-sources 40.
[Phase 2] Dispatched 6 research-scout agents (one per facet). 213 raw candidates returned.
[Phase 3] Dedup — 213 candidates collapsed to 147 distinct sources (38 preprint/published pairs, 28 cross-facet duplicates). Ranked. Screened: 91 pass inclusion criteria, 56 screened out (recorded with failed criterion).
[Phase 3] --max-sources 40 applied — top 40 by composite score retained; 51 trimmed candidates recorded.
[Phase 4] Extracted 40 sources to sources/<id>.md. fact-checker resolved every citation; 2 dead DOIs found → screened out → re-extracted next-ranked candidates.
[Phase 5] source-ledger.md composed; fifteen-bar gate PASS; R4 citation-integrity hard bar PASS (40/40 resolve).
[Phase 5] Handoff Manifest amended; downstream: /research-synthesis.
```

### Example 2 — Gate-closed

```text
$ /research-sources <project-root>/.apothem/plans/new-question

Blocked: run /research-theory first.
Absent artifact: <project-root>/.apothem/plans/new-question/_inputs/theory.md.
No theoretical grounding — the search strategy is ungrounded. Run /research-theory to produce the conceptual framework, or pass --override with a rationale to collect un-grounded.
```
