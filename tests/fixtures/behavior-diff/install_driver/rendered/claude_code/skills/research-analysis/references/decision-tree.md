<!-- SPDX-License-Identifier: MIT -->

## Decision Tree

```mermaid
%%{ init: { "theme": "neutral" } }%%
%% verified: 2026-06-15 %%
%% provenance: commands/research-analysis.md §Workflow %%
%% cross-reference: agents/fact-checker.md, commands/research-experiment.md, commands/research-paper.md, rules/pre-emission-gate.md %%
flowchart TD
    Start[/research-analysis invoked] --> Gate0{Sequence Gate: raw data + preregistration.md present?}
    Gate0 -->|no| Blocked[Halt: 'Blocked: run /research-experiment first']
    Gate0 -->|yes| Ingest[Phase 1 read preregistration first · ingest raw data · verify integrity]
    Ingest --> Tests[Phase 2 run preregistered tests · assumption checks]
    Tests --> Assume{Assumption check passes?}
    Assume -->|no| Deviate[Route substitution to deviation flow]
    Assume -->|yes| Effect[Report effect size + CI · p-value alongside · null results recorded]
    Deviate --> Effect
    Effect --> Family{Comparison family declared or revealed?}
    Family -->|yes| Correct[Phase 3 apply correction · report corrected vs uncorrected]
    Family -->|no| Robust[Phase 3 robustness + sensitivity battery]
    Correct --> Robust
    Robust --> Ledger[Phase 4 compose disclosed-deviation ledger]
    Ledger --> Verify[Phase 4 fact-checker re-derives each result refute-by-default]
    Verify --> Verdict{Result verdict}
    Verdict -->|confirmed| Anchor[Result anchors the paper's claims]
    Verdict -->|fragile| Record[Record with the perturbation that breaks it]
    Verdict -->|unverified| Record
    Anchor --> GateN{Phase 5 fifteen-bar gate passes?}
    Record --> GateN
    GateN -->|no| Revise[Revise per failing bar's action]
    Revise --> GateN
    GateN -->|yes| Emit[Emit _outputs/analysis.md + figures/tables · update Handoff Manifest]
```
