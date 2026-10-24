<!-- SPDX-License-Identifier: MIT -->

## Decision Tree

```mermaid
%%{ init: { "theme": "neutral" } }%%
%% verified: 2026-06-22 %%
%% provenance: commands/github-deploy-fresh.md §Workflow %%
%% cross-reference: commands/freshify.md §Workflow (inherited agnostic core) + rules/production-ready-prs.md §1-§4 %%
flowchart TD
    Start[Target repository ingested] --> F[Run inherited /freshify agnostic core]
    F --> Q1{Residual GitHub traces found?}
    Q1 -->|yes| C1[Route per-action confirmation per removal class · default retain-and-report · purge on opt-in]
    Q1 -->|no| Q2
    C1 --> Q2{All workflow cards green AND maximal score?}
    Q2 -->|no| Fix[Apply in-place root-cause fix · re-run workflow · drive OpenSSF score to max]
    Fix --> Q2
    Q2 -->|yes| Q3{History collapse to single fresh commit needed?}
    Q3 -->|yes| C3[Route confirmation · default push fresh commit only · rewrite on opt-in]
    Q3 -->|no| Commit[Author release: <repo-name> v0.1.0 on origin/main]
    C3 --> Commit
    Commit --> Log[Curate first-version CHANGELOG per Keep-a-Changelog]
    Log --> Q4{Re-sweep trace-free?}
    Q4 -->|residual trace| Q5{In-place freshening sufficient?}
    Q5 -->|yes| Q1
    Q5 -->|no| C5[MAY: route --recreate-repo confirmation · capture metadata · recreate with metadata preserved]
    C5 --> Q4
    Q4 -->|clean| Done[Run validation gate · emit deployment report]
```
