<!-- SPDX-License-Identifier: MIT -->

## Decision Tree

```mermaid
%%{ init: { "theme": "neutral" } }%%
%% verified: 2026-10-26 %%
%% provenance: commands/research-design.md §Workflow %%
%% cross-reference: commands/research-synthesis.md, commands/research-experiment.md, commands/research-spec.md, rules/disclosure-ledger.md %%
flowchart TD
    Start[/research-design invoked] --> Gate0{Sequence Gate: proposal plan-of-record + synthesis gap + spec present?}
    Gate0 -->|no| Blocked[Halt: 'Blocked: run /research-proposal first']
    Gate0 -->|yes| Ingest[Phase 1 ingest gap + hypotheses · confirm falsifiable]
    Ingest --> Falsifiable{Every hypothesis refutable?}
    Falsifiable -->|no| Return[Return non-refutable hypothesis to /research-spec]
    Falsifiable -->|yes| Predict[Phase 2 operationalize predictions]
    Predict --> Q1{Design type supplied?}
    Q1 -->|no| DesignInquiry[Derive candidate · ratify via structured inquiry]
    Q1 -->|yes| Vars[Phase 3 variables · controls · instruments · sample frame]
    DesignInquiry --> Vars
    Vars --> Ethics{Sample touches subjects or sensitive data?}
    Ethics -->|yes| EthicsInquiry[Required R6 ethics/consent inquiry blocks emission]
    Ethics -->|no| Power[Phase 4 power analysis]
    EthicsInquiry --> Power
    Power --> EffectSize{Effect size grounded in synthesis?}
    EffectSize -->|no| Placeholder[Surface USER-CONFIRM effect-size placeholder]
    EffectSize -->|yes| Threats[Phase 5 threats-to-validity ledger]
    Placeholder --> Threats
    Threats --> Freeze[Phase 5 freeze preregistration · write-once]
    Freeze --> GateN{Phase 6 fifteen-bar gate passes?}
    GateN -->|no| Revise[Revise per failing bar's action]
    Revise --> GateN
    GateN -->|yes| Emit[Emit study-design.md + preregistration.md · update Handoff Manifest]
```
