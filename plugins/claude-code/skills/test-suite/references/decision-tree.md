<!-- SPDX-License-Identifier: MIT -->

## Decision Tree

```mermaid
%%{ init: { "theme": "neutral" } }%%
%% verified: 2026-06-09 %%
%% provenance: commands/test-suite.md §Workflow %%
%% cross-reference: skills/test-authoring/SKILL.md + agents/test-runner.md %%
flowchart TD
    Start[/test-suite invoked against a repo/] --> Discover{Test framework discoverable from manifest or corpus?}
    Discover -->|no| Inquire[Route framework choice through structured inquiry · rules/authority-inquiry.md]
    Discover -->|yes| Contracts[Enumerate behavior contracts · public API + error branches + invariants]
    Inquire --> Contracts
    Contracts --> Author[Author behavior-first AAA tests · test-authoring skill · inject SPDX header]
    Author --> Run[Run via test-runner agent · 200-token return contract]
    Run --> Outcome{Any failing test?}
    Outcome -->|no| Coverage[Parse coverage · report critical-path gaps]
    Outcome -->|yes| Triage{Test defect or source defect?}
    Triage -->|test defect| FixTest[Correct the assertion · re-run]
    Triage -->|source defect| Finding[Record finding · cite file:line + contract · no source edit]
    FixTest --> Run
    Finding --> Coverage
    Coverage --> Gate[Run fifteen-bar pre-emission gate · emit report]
```
