<!-- SPDX-License-Identifier: MIT -->

## Decision Tree

```mermaid
%%{ init: { "theme": "neutral" } }%%
%% verified: 2026-06-16 %%
%% provenance: commands/research-proposal.md §Workflow %%
%% cross-reference: commands/research-synthesis.md (predecessor), commands/research-design.md (successor), skills/research-suite/SKILL.md §Thirteen-Stage Research Lifecycle, rules/authority-inquiry.md %%
flowchart TD
    Start[/research-proposal invoked] --> Gate0{Sequence Gate: synthesis.md + theory.md present?}
    Gate0 -->|no| Blocked[Halt: 'Blocked: run /research-synthesis first']
    Gate0 -->|yes| P1[Phase 1 ingest gap + theory · frame aims]
    P1 --> P2[Phase 2 SMART aims hierarchy · feasibility]
    P2 --> Feas{Every aim achievable against resources?}
    Feas -->|no| ReScope[Re-scope or demote the infeasible aim · confirm via inquiry]
    ReScope --> P2
    Feas -->|yes| P3[Phase 3 resource/timeline/risk register · preregistration plan]
    P3 --> Reg{Preregistration registry named?}
    Reg -->|no| AskReg[structured inquiry: name the registry]
    AskReg --> P3
    Reg -->|yes| P4[Phase 4 impact pathway · EQUATOR pre-select · ethics feasibility]
    P4 --> GateN{Phase 5 fifteen-bar gate passes?}
    GateN -->|no| Revise[Revise per failing bar's action]
    Revise --> GateN
    GateN -->|yes| Emit[Emit _inputs/proposal.md · update Handoff Manifest]
```
