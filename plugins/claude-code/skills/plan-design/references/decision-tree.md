<!-- SPDX-License-Identifier: MIT -->

## Decision Tree

```mermaid
%%{ init: { "theme": "neutral" } }%%
%% verified: 2026-05-11 %%
%% provenance: commands/plan-design.md §Workflow %%
%% cross-reference: src/apothem/commands/ (slash-command cohort) %%
flowchart TD
    Start[/plan-design invoked/] --> Suite{Suite files present?}
    Suite -->|no| Recommend[STOP — recommend /plan-generate]
    Suite -->|yes| Review{Review Scorecards present at SHARED+?}
    Review -->|no| AskRev[structured inquiry: run /plan-review · proceed without · abort]
    Review -->|yes, FAIL| AskFail[structured inquiry: resolve · override · abort]
    Review -->|yes, PASS| Bearing{Architecture-bearing suite?}
    Bearing -->|no| Skip[STOP — design not applicable · handoff to /plan-execute]
    Bearing -->|yes| Refine{--refine-existing flag set?}
    Refine -->|yes, design.md exists| Iter[Iterative refinement on existing artifact]
    Refine -->|no| Fresh[Author fresh artifact]
    Iter --> P0[Phase 0: Input Ingest]
    Fresh --> P0
    P0 --> P1[Phase 1: Architectural Decomposition Pass]
    P1 --> Open{Open architectural questions remain?}
    Open -->|yes| AskOpen[structured inquiry: surface each open question]
    AskOpen --> P1
    Open -->|no| P2[Phase 2: Component-Interface Design]
    P2 --> P3[Phase 3: Cross-Component Binding Ratification]
    P3 --> Recip{All bindings reciprocally closed?}
    Recip -->|no| Fix[Close half-edges]
    Fix --> P3
    Recip -->|yes| P4[Phase 4: Design-Artifact Emission]
    P4 --> P5[Phase 5: Design Validation Gate]
    P5 --> Bar{All fifteen bars pass?}
    Bar -->|no| Revise[Revise on failing bar · re-run gate]
    Revise --> P5
    Bar -->|yes| Promote[Promote artifact · update Handoff Manifest]
    Promote --> Done[Pipeline handoff to /plan-execute]
```

The tree distinguishes deterministic forks (suite-file presence, scorecard state, flag presence, gate-bar verdicts) from structured-inquiry forks (open architectural questions, scorecard-FAIL disposition) from iteration forks (Phase 1 open-question loop, Phase 3 binding-closure loop, Phase 5 gate-bar loop).
