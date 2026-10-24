<!-- SPDX-License-Identifier: MIT -->

## Decision Tree

```mermaid
%% verified: 2026-06-16 %%
%% provenance: commands/research.md §Workflow %%
%% cross-reference: commands/workflow.md, commands/research-ideate.md, research-spec.md, research-theory.md, research-sources.md, research-synthesis.md, research-proposal.md, research-design.md, research-experiment.md, research-analysis.md, research-paper.md, research-review.md, research-publish.md, research-disseminate.md, skills/workflow/SKILL.md, skills/research-suite/SKILL.md %%
flowchart TD
    Start[/research invoked/] --> Frame{Mission + entry point unambiguous?}
    Frame -->|no| Inquiry[Frame: structured-inquiry scope + entry + ethics set]
    Inquiry --> Frame
    Frame -->|raw idea or domain| Ideate[entry = research-ideate]
    Frame -->|--quick| QuickEntry[entry = research-sources · terminate after research-synthesis]
    Frame -->|existing suite| Resume[resume stage from manifests / --from]
    Ideate --> Decompose[Decompose pipeline into staged work-items + manifest return contracts]
    QuickEntry --> Decompose
    Resume --> Decompose
    Decompose --> OptIn{--autonomous set?}
    OptIn -->|no| Plan[Present next-stage plan · confirm]
    OptIn -->|yes| Dispatch[Dispatch /research-stage · resume from upstream manifest]
    Plan --> Dispatch
    Dispatch --> RunStage[stage runs · emits manifest + gate attestation]
    RunStage --> Verify[Refute-by-default critics over the hand-off · R1-R10 lenses]
    Verify --> AdvGate{At analysis-to-paper boundary: advancement-gate attestation cleared? R7 convincingly + significantly}
    AdvGate -->|no| Halt
    AdvGate -->|yes / not at boundary| Survive{Non-refute majority AND Sequence Gate passes?}
    Survive -->|no| Halt[Halt · surface failed gate / refuted hand-off / non-cleared advancement gate · remediate at owning stage]
    Halt --> Dispatch
    Survive -->|yes| More{more stages in scope?}
    More -->|yes| Decompose
    More -->|no| Synth[research-disseminate record / --quick synthesis → synthesize · workflow fifteen-bar gate]
    Synth --> Emit[Emit deterministic result + recommended next move]
```
