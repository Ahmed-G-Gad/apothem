<!-- SPDX-License-Identifier: MIT -->

## Decision Tree

```mermaid
%%{ init: { "theme": "neutral" } }%%
%% verified: 2026-06-15 %%
%% provenance: commands/research-synthesis.md §Workflow %%
%% cross-reference: agents/fact-checker.md, skills/source-synthesis/SKILL.md, commands/research-sources.md, commands/research-design.md %%
flowchart TD
    Start[/research-synthesis invoked] --> Gate0{Sequence Gate: source-ledger.md + sources/ present?}
    Gate0 -->|no| Blocked[Halt: 'Blocked: run /research-sources first']
    Gate0 -->|yes| Ingest[Phase 1 ingest corpus · build claim inventory · cluster by topic]
    Ingest --> Q1{Matrix dimensions supplied?}
    Q1 -->|no| DimInquiry[Phase 2 derive dimensions · ratify via structured inquiry]
    Q1 -->|yes| Matrix[Phase 2 build source-by-dimension literature matrix]
    DimInquiry --> Matrix
    Matrix --> Verify[Phase 3 fact-checker refute-by-default per claim]
    Verify --> Outcome{Claim verdict}
    Outcome -->|corroborated| Map[Phase 4 anchor SOTA map · source-synthesis skill]
    Outcome -->|contested| Ledger[Record both positions in contested-findings ledger]
    Outcome -->|unverified| Ledger
    Map --> Gap[Phase 4 state explicit gap from matrix coverage gaps]
    Ledger --> Gap
    Gap --> GateN{Phase 5 fifteen-bar gate passes?}
    GateN -->|no| Revise[Revise per failing bar's action]
    Revise --> GateN
    GateN -->|yes| Emit[Emit _inputs/synthesis.md · update Handoff Manifest]
```
