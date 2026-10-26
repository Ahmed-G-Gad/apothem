<!-- SPDX-License-Identifier: MIT -->

## Decision Tree

```mermaid
%%{ init: { "theme": "neutral" } }%%
%% verified: 2026-10-26 %%
%% provenance: src/apothem/commands/research-sources.md §Workflow — Five Phases %%
%% cross-reference: skills/research-suite/SKILL.md §Thirteen-Stage Research Lifecycle %%
flowchart TD
    Start[/research-sources invoked] --> Gate{/research-theory grounding + ratified spec present?}
    Gate -->|no AND no --override| Blocked[Emit 'Blocked: run /research-theory first.' · halt]
    Gate -->|no AND --override| Audit[Write Gate-Override audit row · proceed un-spec-screened]
    Gate -->|yes| P1[Phase 1 · ingest spec · decompose into orthogonal sub-queries]
    Audit --> P1
    P1 --> Inq{Screening criteria + source budget fixed?}
    Inq -->|no| Surface[Surface USER-CONFIRM placeholders via structured inquiry · block on required gaps]
    Inq -->|yes| P2[Phase 2 · parallel research-scout dispatch · one agent per facet · search record per pass]
    Surface --> P2
    P2 --> P3[Phase 3 · dedup · link reports to studies · rank · screen · chase references · assess bias]
    P3 --> Cap{Included count over --max-sources and ceiling applies?}
    Cap -->|yes| Trim[Retain highest-ranked survivors · record each trimmed source as eligible, not extracted]
    Cap -->|no| P4
    Trim --> P4[Phase 4 · extract each source with provenance · fact-checker resolves every citation]
    P4 --> Phantom{Any phantom citation?}
    Phantom -->|yes| Drop[Screen out the source · record the resolution failure]
    Phantom -->|no| P5
    Drop --> P5[Phase 5 · compose source-ledger.md · run fifteen-bar pre-emission gate]
    P5 --> GatePass{Gate passes · R4 citation-integrity hard bar?}
    GatePass -->|no| Fix[Revise per failing bar · re-run gate]
    GatePass -->|yes| Emit[Amend Handoff Manifest · downstream /research-synthesis]
    Fix --> P5
    Emit --> Done[Evidence base ready for synthesis]
```
