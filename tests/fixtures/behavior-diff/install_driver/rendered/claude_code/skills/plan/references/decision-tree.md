<!-- SPDX-License-Identifier: MIT -->

## Decision Tree

```mermaid
%% verified: 2026-06-16 %%
%% provenance: commands/plan.md §Workflow %%
%% cross-reference: commands/workflow.md, commands/plan.md, commands/plan-spec.md, plan-generate.md, plan-review.md, plan-design.md, plan-execute.md, skills/workflow/SKILL.md, skills/plan-suite/SKILL.md %%
flowchart TD
    Start[/plan invoked/] --> Frame{Mission + entry point unambiguous?}
    Frame -->|no| Inquiry[Frame: structured-inquiry scope + entry set]
    Inquiry --> Frame
    Frame -->|raw mission| Spec[entry = plan-spec]
    Frame -->|existing suite| Resume[resume stage from manifests / --from]
    Spec --> Decompose[Decompose pipeline into staged work-items + manifest return contracts]
    Resume --> Decompose
    Decompose --> OptIn{--autonomous set?}
    OptIn -->|no| Plan[Present next-stage plan · confirm]
    OptIn -->|yes| Dispatch[Dispatch /plan-stage · resume from upstream manifest]
    Plan --> Dispatch
    Dispatch --> Cond{stage = plan-design AND not architecture-bearing?}
    Cond -->|yes| Skip[skip plan-design]
    Cond -->|no| RunStage[stage runs · emits manifest + gate attestation]
    Skip --> Verify
    RunStage --> Verify[Refute-by-default critics over the hand-off]
    Verify --> Survive{Non-refute majority AND Sequence Gate passes?}
    Survive -->|no| Halt[Halt · surface failed gate / refuted hand-off · remediate at owning stage]
    Halt --> Dispatch
    Survive -->|yes| More{more stages?}
    More -->|yes| Decompose
    More -->|no| Synth[plan-execute final phase → COMPLETION.md · synthesize · workflow fifteen-bar gate]
    Synth --> Emit[Emit deterministic result + recommended next move]
```
