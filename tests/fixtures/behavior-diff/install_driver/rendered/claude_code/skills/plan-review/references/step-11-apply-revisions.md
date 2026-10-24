<!-- SPDX-License-Identifier: MIT -->

### Step 10: Apply Revisions

Deploy an Implementation Team (CM-25A) for parallel non-overlapping revisions — each agent handles revisions in non-overlapping files (CM-25E).

**10.1** Pre-revision impact analysis → Revision Impact Map. For each revision, trace every file and element it affects. Identify revision pairs whose targets overlap or whose changes interact. If revisions have overlapping file targets, partition into conflict-free groups — execute each group as a parallel wave (non-overlapping files within each wave; waves execute sequentially). When several revisions target the same file(s), apply sequentially in severity order (Critical first) without deploying an Implementation Team.

**10.2** Apply with cross-reference tracking. Classify each applied revision as STRUCTURAL (adds/removes phases, changes the dependency graph, or alters architectural decisions) or REFINEMENT (modifies task scope, updates acceptance criteria, or fixes inconsistencies within existing phases). Bump the plan's semver: STRUCTURAL → MAJOR (vN.0.0), REFINEMENT → MINOR (vN.M.0), pure-typo or formatting fix → PATCH (vN.M.P). Append each applied revision to the Revision History table as `vX.Y.Z | YYYY-MM-DD | classification | summary`.

**10.3** Post-revision checklist: every proposed revision applied; every blast-radius impact checked; no new inconsistencies introduced by the revisions themselves. If a revision introduces a new inconsistency, that is a Critical finding requiring immediate re-revision before proceeding.

**10.4** If a STRUCTURAL revision (phases added/removed, dependency graph changed): update the PROGRESS.md phase tracker, counts, and dependency references to reflect the new plan structure.

**10.5** Findings status update: after each applied revision, update the Findings Registry row from `open` to `resolved` only when Step 11 re-checks the finding's exact evidence locus. Operator-waived and deferred-to-maintenance statuses require a rationale, source anchor, and downstream routing entry; they never silently count as resolved.
