<!-- SPDX-License-Identifier: MIT -->

## Decision Tree

```mermaid
%%{ init: { "theme": "neutral" } }%%
%% verified: 2026-06-15 %%
%% provenance: commands/research-experiment.md §Workflow %%
%% cross-reference: agents/test-runner.md, commands/research-design.md, commands/research-analysis.md %%
flowchart TD
    Start[/research-experiment invoked] --> Gate0{Sequence Gate: study-design.md + preregistration.md present?}
    Gate0 -->|no| Blocked[Halt: 'Blocked: run /research-design first']
    Gate0 -->|yes| Validate[Phase 1 read design + preregistration · confirm steps executable]
    Validate --> Q1{Data destination + seed + ethics scope resolved?}
    Q1 -->|no| Inquiry[Surface destination/seed/ethics via structured inquiry]
    Q1 -->|yes| Snapshot[Phase 1 capture environment snapshot · resolve seed]
    Inquiry --> Snapshot
    Snapshot --> Q2{--dry-run?}
    Q2 -->|yes| Readiness[Emit manifest pre-run sections + readiness verdict · exit]
    Q2 -->|no| Execute[Phase 2 execute preregistered protocol · log each step on run]
    Execute --> Trial{Trial outcome}
    Trial -->|confirming| Record[Phase 3 record observation with provenance]
    Trial -->|null/failed/unexpected| Record
    Trial -->|deviation from preregistration| Deviation[Log deviation + cause + timestamp · do not edit preregistration]
    Deviation --> Record
    Record --> Manifest[Phase 4 compose reproducibility manifest · env + seed + pins + recipe]
    Manifest --> GateN{Phase 5 fifteen-bar gate passes?}
    GateN -->|no| Revise[Revise per failing bar's action]
    Revise --> GateN
    GateN -->|yes| Emit[Emit experiment-log.md + reproducibility-manifest.md · update Handoff Manifest]
```
