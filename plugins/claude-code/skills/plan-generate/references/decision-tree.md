<!-- SPDX-License-Identifier: MIT -->

## Decision Tree

```mermaid
%%{ init: { "theme": "neutral" } }%%
%% verified: 2026-04-27 %%
%% provenance: commands/plan-generate.md §Workflow %%
%% cross-reference: src/apothem/commands/ (slash-command cohort) %%
flowchart TD
    Start[/plan-generate invoked/] --> Spec{Prose spec exists?}
    Spec -->|no| Recommend[STOP — recommend /plan-spec]
    Spec -->|yes| Suite{Suite folder exists?}
    Suite -->|yes| Overwrite[structured inquiry: overwrite · merge · abort]
    Suite -->|no| Discovery[Discovery: requirement extraction]
    Overwrite -->|abort| Halt[STOP]
    Overwrite -->|overwrite| Discovery
    Overwrite -->|merge| MergeMode[Merge into existing suite]
    Discovery --> Generate[Generate phase manifest + per-phase PHASE.md files]
    MergeMode --> Generate
    Generate --> Score{Seriousness >= PERSONAL_USE?}
    Score -->|yes| ProseScore[Run Prose Fidelity Scorecard]
    Score -->|no| Skip1[Skip prose-fidelity check]
    ProseScore --> Score2{Seriousness >= SHARED?}
    Skip1 --> Score2
    Score2 -->|yes| ConsistScore[Run Internal Consistency Scorecard]
    Score2 -->|no| Skip2[Skip internal-consistency check]
    ConsistScore --> Gate{Scorecards PASS?}
    Skip2 --> Emit[Emit suite files]
    Gate -->|fail at SHARED+| AskFail[structured inquiry: revise · override · abort]
    Gate -->|pass| Emit
    Emit --> Done[Hand off to /plan-review or /plan-execute]
```

The tree distinguishes seriousness-driven branches (scorecards activate at
PERSONAL_USE+ and SHARED+) from operator-decision branches surfaced through
structured inquiry (overwrite-vs-merge, scorecard-fail handling).
