<!-- SPDX-License-Identifier: MIT -->

## Decision Tree

```mermaid
%%{ init: { "theme": "neutral" } }%%
%% verified: 2026-06-16 %%
%% provenance: commands/research-theory.md §Workflow %%
%% cross-reference: commands/research-spec.md (predecessor), commands/research-sources.md (successor), skills/research-suite/SKILL.md §Thirteen-Stage Research Lifecycle, rules/visual-leverage.md %%
flowchart TD
    Start[/research-theory invoked] --> Gate0{Sequence Gate: research-spec.md present?}
    Gate0 -->|no| Blocked[Halt: 'Blocked: run /research-spec first']
    Gate0 -->|yes| P1[Phase 1 ingest spec · select framework]
    P1 --> Frame{Framework supplied or ratified?}
    Frame -->|no| AskFrame[structured inquiry: ratify the theoretical framework]
    AskFrame --> P1
    Frame -->|yes| P2[Phase 2 build theory of change · logic model]
    P2 --> Refute{Every theorized relation refutable?}
    Refute -->|no| AskRefute[structured inquiry: surface the untestable link as an open question]
    AskRefute --> P2
    Refute -->|yes| P3[Phase 3 operationalize constructs]
    P3 --> P4[Phase 4 author conceptual model diagram]
    P4 --> GateN{Phase 5 fifteen-bar gate passes?}
    GateN -->|no| Revise[Revise per failing bar's action]
    Revise --> GateN
    GateN -->|yes| Emit[Emit _inputs/theory.md · update Handoff Manifest]
```
