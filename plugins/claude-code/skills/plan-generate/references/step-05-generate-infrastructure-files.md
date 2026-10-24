<!-- SPDX-License-Identifier: MIT -->

### Step 5: Generate Infrastructure Files

Deploy a parallel Generation Team (CM-25A — one agent per file; return contract: confirmation + path, max 1000 tokens). Assess file size before generation (CM-23A) — if any infrastructure file is expected to exceed 500 lines, use the incremental generation protocol (CM-23B). After generation, summarize-and-release (CM-24B).

**Scale-tier classification.** Before laying the infrastructure, classify the suite's scale tier (small / medium / large) with the executable classifier [`src/apothem/lib/plan_tiers.py`](../lib/plan_tiers.py) (`classify_tier(phase_count, spec_count) -> Tier`); the prose framework it mirrors is `rules/canonical-layout-reporting-tiers.md` §7. The governing tier is the higher of the phase-dimension and spec-dimension tiers, and it drives the validation cadence, indexing (`MASTER-INDEX.md` at medium+), and decomposition (phase-grouped at medium, sub-suite federation at large) the infrastructure files below must reflect. When either count sits within ±10% of a boundary, route the classification through the structured-inquiry channel per `rules/authority-inquiry.md` rather than silently picking.

- **`PREAMBLE.md`** — context, standards, architecture, naming, workflow mandates (referencing TM-N by number), checklists, session protocols, problem-solving protocol.
- **`MASTER-PLAN.md`** — title, versioning, decisions, phase index, dependency graph, roadmap, risks, future extensions.
- **`PROGRESS.md`** — bounded status ledger: status, counts, review summary with scorecard grades (initialized as pending — populated after Step 7), tracker, Phase Output Registry (initialized empty for all phases), Resumption Contract (initialized with project conventions; next action set to "Complete phase file generation — Step 6"), files, decisions, next steps. After Step 6, update the Resumption Contract with the actual Phase 01 path. Do not paste long audit logs here; link to REPORT.md or `_outputs/`.
- **`PLAN-NOTES.md`** — bounded decision ledger: source prose path, task, decisions (DO NOT RE-ASK), gap analysis, Q&A batches, update tracker, user preferences. Use rolling summaries and backlinks for long evidence or historical detail.
- **`_outputs/` convention** — reserve as the suite-local durable-output surface for future `/plan-audit`, `/plan-review`, `/plan-execute`, and persisted status artifacts. Empty directories need not be force-tracked unless the host convention uses marker files.
