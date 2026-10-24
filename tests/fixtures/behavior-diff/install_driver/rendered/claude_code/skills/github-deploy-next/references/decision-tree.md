<!-- SPDX-License-Identifier: MIT -->

## Decision Tree

```mermaid
%%{ init: { "theme": "neutral" } }%%
%% verified: 2026-06-22 %%
%% provenance: commands/github-deploy-next.md §Workflow %%
%% cross-reference: commands/github-deploy-fresh.md §Workflow (fresh-first-release sibling) + rules/production-ready-prs.md §1-§4 %%
flowchart TD
    Start[Target repository ingested] --> Q1{Open pull requests the release should land?}
    Q1 -->|not yet ready| Rev[Relentlessly revise to ready · rebase/resolve conflict · drive CI green · cap 3 attempts then defer-with-rationale per rules/planning-techniques.md §1]
    Q1 -->|ready| C1
    Q1 -->|none| Iss
    Rev --> C1[Route per-action merge confirmation per rules/interactive-questions.md §6 · default leave-open-report-only · merge on opt-in]
    C1 --> Iss[Resolve addressed issues · cite issue numbers]
    Iss --> Bump[Derive SemVer bump from Conventional Commits change set · read-only preview · no gate]
    Bump --> Log[Roll [Unreleased] into new version section per Keep-a-Changelog · read-only draft · no gate]
    Log --> C5[Route per-action publish confirmation per rules/interactive-questions.md §6 · default stage-locally-report-only · publish on opt-in]
    C5 --> Sign[Attach signed artifacts where ratified · signing posture per rules/host-discovery.md]
    Sign --> Notes[Author current-version-only release notes · read-only draft · no gate]
    Notes --> Fresh[Post-cycle freshness sweep · prune merged branches + superseded run logs · confirmation-gated]
    Fresh --> Q2{Re-sweep facade current-version-only AND stale-trace-free?}
    Q2 -->|residual back-reference or stale trace| Log
    Q2 -->|clean| Done[Run validation gate · emit deployment report]
```
