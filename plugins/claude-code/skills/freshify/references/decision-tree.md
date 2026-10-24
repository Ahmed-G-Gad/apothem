<!-- SPDX-License-Identifier: MIT -->

## Decision Tree

```mermaid
%%{ init: { "theme": "neutral" } }%%
%% verified: 2026-06-22 %%
%% provenance: commands/freshify.md §Workflow %%
%% cross-reference: rules/production-ready-prs.md §1-§4 (production-ready discipline) %%
flowchart TD
    Start[Target repository ingested] --> Q1{Cache or stale-artifact targets found?}
    Q1 -->|yes| C1[Route per-target confirmation · default retain-and-report · purge on opt-in]
    Q1 -->|no| Q2
    C1 --> Q2{Legacy narrative or back-references found?}
    Q2 -->|mechanically dead| Repair[Repair in place · carve-out auto-decision]
    Q2 -->|judgment-dependent| C2[Route confirmation · name removed passage]
    Q2 -->|none| QN
    Repair --> QN
    C2 --> QN{Off-convention names or non-natural narrative?}
    QN -->|off-convention name| CN[Route Rename/Move confirmation · propagate inbound refs · rename on opt-in]
    QN -->|non-natural narrative| RN[Rewrite to natural product voice in place]
    QN -->|none| Q3
    CN --> Q3
    RN --> Q3{Facade current-version-only?}
    Q3 -->|history rewrite needed| C3[Route confirmation · default freshen working tree only]
    Q3 -->|working-tree freshen suffices| Q4
    C3 --> Q4{All host gates green?}
    Q4 -->|no| Fix[Apply in-place root-cause fix · re-run gate]
    Fix --> Q4
    Q4 -->|yes| Q5{Re-sweep trace-free · all refs propagated?}
    Q5 -->|residual trace| Q1
    Q5 -->|clean| Done[Run validation gate · emit freshening report]
```
