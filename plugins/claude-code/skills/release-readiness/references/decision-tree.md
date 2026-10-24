<!-- SPDX-License-Identifier: MIT -->

## Decision Tree

```mermaid
%%{ init: { "theme": "neutral" } }%%
%% verified: 2026-06-16 %%
%% provenance: commands/release-readiness.md §Workflow %%
%% cross-reference: rules/production-ready-prs.md §1-§4 (production-ready discipline) %%
flowchart TD
    Start[Release surface ingested] --> Q1{Quality matrix exit-zero?}
    Q1 -->|no| Block[Append HIGH blocker · record file:line]
    Q1 -->|yes| Q2{Dependency-risk pass clean?}
    Q2 -->|open HIGH CVE| Block
    Q2 -->|unpinned production pin| Med[Append MEDIUM finding]
    Q2 -->|clean| Q3{Supply-chain checks pass?}
    Q3 -->|unpinned action OR secret literal OR unsigned-where-ratified| Block
    Q3 -->|clean| Q4{CHANGELOG current AND version matches tag?}
    Q4 -->|tag divergence| Block
    Q4 -->|CHANGELOG lagging| Med
    Q4 -->|both current| Q5{Any blocking findings?}
    Med --> Q5
    Block --> Q5
    Q5 -->|yes| Blocked[Verdict BLOCKED · emit ordered blocking list]
    Q5 -->|no| Ready[Verdict READY · emit attestation]
```
