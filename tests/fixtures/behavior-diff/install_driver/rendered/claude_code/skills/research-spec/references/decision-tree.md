<!-- SPDX-License-Identifier: MIT -->

## Decision Tree

```mermaid
%%{ init: { "theme": "neutral" } }%%
%% verified: 2026-06-15 %%
%% provenance: commands/research-spec.md §Workflow %%
%% cross-reference: rules/interactive-questions.md (canonical channel) %%
flowchart TD
    Start[/research-spec invoked/] --> Quick{--quick flag set?}
    Quick -->|yes| Brief[Resolve project root · write lightweight brief · exit]
    Quick -->|no| Source{Question or notes source resolves?}
    Source -->|no| AskSrc[structured inquiry: surface the missing source · do not invent]
    Source -->|yes| Refine{--refine-existing and research-spec.md exists?}
    Refine -->|yes| Iter[Iterative refinement on existing spec]
    Refine -->|no| Fresh[Fresh framing run]
    Iter --> P1[Phase 1: Discovery and Extraction]
    Fresh --> P1
    P1 --> P2[Phase 2: Hypothesis Crystallization]
    P2 --> Fals{Every hypothesis carries a null form?}
    Fals -->|no| AskFals[structured inquiry: re-frame the unfalsifiable hypothesis]
    AskFals --> P2
    Fals -->|yes| P3[Phase 3: Scope and Criteria Drawing]
    P3 --> P4[Phase 4: Success Metrics and Glossary]
    P4 --> P5[Phase 5: Question-Resolution Sweep]
    P5 --> Open{Open ambiguities remain?}
    Open -->|yes| AskOpen[structured inquiry: surface each unresolved boundary or threshold]
    AskOpen --> P5
    Open -->|no| Gate{Fifteen-bar pre-emission gate PASS?}
    Gate -->|no| Revise[Revise the failing bar · re-run the gate]
    Revise --> Gate
    Gate -->|yes| Emit[Promote to _spec/research-spec.md · emit Handoff Manifest]
```
