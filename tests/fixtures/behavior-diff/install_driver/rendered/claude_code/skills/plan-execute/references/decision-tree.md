<!-- SPDX-License-Identifier: MIT -->

## Decision Tree

The command's branching logic at a glance — every decision either resolves
deterministically against state on disk or surfaces a structured-inquiry
invocation.

```mermaid
%%{ init: { "theme": "neutral" } }%%
%% verified: 2026-06-16 %%
%% provenance: commands/plan-execute.md §Workflow %%
%% cross-reference: src/apothem/commands/ (slash-command cohort) %%
flowchart TD
    Start[/plan-execute invoked/] --> Suite{Suite files present?}
    Suite -->|no| Recommend[STOP — recommend /plan-generate]
    Suite -->|yes| Resolve{Phase argument given?}
    Resolve -->|yes| Target[Target = named phase]
    Resolve -->|no| Next{All phases complete?}
    Next -->|yes| AskDone[structured inquiry: phase done]
    Next -->|no| Target2[Target = next pending phase]
    Target --> Status{Target phase status}
    Target2 --> Status
    Status -->|Pending| Prereq{Prerequisites satisfied?}
    Status -->|Complete| AskRedo[structured inquiry: re-execute · resume · abort]
    Status -->|Blocked| AskBlock[structured inquiry: resolve · force · abort]
    Status -->|Skipped| AskSkip[structured inquiry: resolve upstream · force · abort]
    Status -->|InProgress| Resume[Resume from Resumption Contract pointer]
    Prereq -->|no| AskPrereq[structured inquiry: run prereq · override · abort]
    Prereq -->|yes| Run[Step 3: execute tasks · per-task commits]
    Resume --> Run
    Run --> QG{Quality gates pass?}
    QG -->|no, retry budget remaining| Fix[Diagnose · fix · re-run]
    Fix --> QG
    QG -->|no, budget exhausted| AskGate[structured inquiry: BLOCKED · override · abort]
    QG -->|yes| Verify[Step 6: verification · CM-7 isolation check]
    Verify -->|fail| AskGate
    Verify -->|pass| Report[Step 7: write REPORT.md]
    Report --> Exit[Step 8: Phase Exit Protocol]
    Exit --> Final{Final phase?}
    Final -->|yes| Complete[Emit COMPLETION.md · halt]
    Final -->|no| ContExec{Continuous mode opted in?}
    ContExec -->|yes| Compact[Compact · bootstrap next phase]
    ContExec -->|no| AskCont[structured inquiry: next phase · specific · stop]
    Compact --> Resolve
```

The tree distinguishes three fork classes: **deterministic forks** resolved
against state on disk (file presence, dependency-graph order, prerequisite
satisfaction), **structured-inquiry forks** where the operator's decision is
material and surfaces through the canonical channel, and **retry forks** where a
budget governs how many cycles attempt resolution before escalation.
