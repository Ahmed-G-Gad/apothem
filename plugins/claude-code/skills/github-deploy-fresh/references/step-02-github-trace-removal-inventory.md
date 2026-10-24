<!-- SPDX-License-Identifier: MIT -->

2. **GitHub-trace removal inventory.** Sweep the repository's GitHub-side state for residual traces, extending each class comprehensively per the "etc." extension rule. Each removal is destructive: route a per-action confirmation per `rules/interactive-questions.md` §6, with the in-place default being "retain, report only." Named removal steps (each a distinct confirmation):
   - **Caches** — GitHub Actions caches and restored-cache entries keyed to superseded runs.
   - **Stale artifacts** — uploaded workflow artifacts and release assets from superseded runs.
   - **Branches** — every branch other than `main`, including merged feature branches and stale protected branches.
   - **Pull requests** — open and closed pull requests; PR-comment threads and review history.
   - **Previous versions / releases / packages / deployments** — prior GitHub Releases, GitHub Packages versions, and deployment records; extended to **draft and pre-releases**, **stale tags**, and registry coordinates (npm, npx) pointing at superseded versions.
   - **Failed runs and workflow-run history** — failed Actions runs, the full workflow-run history, and the **Actions run logs** they retain.
   - **Signs to previous commits / releases** — back-references in narrative, badges, and metadata pointing at superseded commits, releases, or registry versions.
   - **Backward / placeholder / refinement / fix / modification references** — process-narration and obsolete-artifact references in commit metadata, release notes, and the repository description.
   - **References to obsolete / legacy / retired artifacts or narrative** — repository-description, topic, and About-panel mentions of retired surfaces.
   - **Git history** — the full commit history preceding the single fresh commit (gated as the `--rewrite-history` step at stanza 4).
   - **Plugins** — repository-installed GitHub Apps and integrations referencing superseded surfaces.
   - **Extended sibling classes (per the "etc." extension rule)** — **GitHub Pages build history**, **environment and deployment records**, **branch-protection drift**, **gist and wiki traces**, and **fork-network artifacts**, each a distinct confirmation.
