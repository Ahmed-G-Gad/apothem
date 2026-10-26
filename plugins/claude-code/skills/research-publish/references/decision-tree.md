<!-- SPDX-License-Identifier: MIT -->

## Decision Tree

```mermaid
%%{ init: { "theme": "neutral" } }%%
%% verified: 2026-10-26 %%
%% provenance: commands/research-publish.md §Workflow %%
%% cross-reference: agents/fact-checker.md, commands/research-review.md, rules/authority-inquiry.md, rules/pre-emission-gate.md %%
flowchart TD
    Start[/research-publish invoked] --> Gate0{Sequence Gate: paper + review-report.md present · HIGH revisions resolved?}
    Gate0 -->|no| Blocked[Halt: 'Blocked: run /research-review first']
    Gate0 -->|yes| Ingest[Phase 1 read review first · resolve venue · gather declaration data]
    Ingest --> Venue{Venue + template resolved?}
    Venue -->|no| Inquire[Surface venue/template inquiry · block until resolved]
    Venue -->|yes| Format[Phase 2 format manuscript to template · no claim altered]
    Inquire --> Format
    Format --> Cite{Every citation resolves?}
    Cite -->|no| Block1[Phantom citation blocks the package · resolve or remove at source]
    Cite -->|yes| Assemble[Phase 3 supplementary + declarations + cover letter]
    Block1 --> Assemble
    Assemble --> Decl{Every required declaration's facts present?}
    Decl -->|no| Inq2[Surface required ethics/COI inquiry · block until resolved]
    Decl -->|yes| Preprint[Phase 4 preprint/archival plan · reserve DOI]
    Inq2 --> Preprint
    Preprint --> Verify[Phase 4 fact-checker re-dereferences citations + re-checks declarations]
    Verify --> Checklist[Phase 4 run submission checklist]
    Checklist --> Ready{Every checklist line met?}
    Ready -->|no| Hold[Hold package at not-ready · resolve unmet lines]
    Hold --> Checklist
    Ready -->|yes| GateN{Phase 5 fifteen-bar gate passes?}
    GateN -->|no| Revise[Revise per failing bar's action]
    Revise --> GateN
    GateN -->|yes| Emit[Emit package + publication-record.md · close Handoff Manifest · hand off to operator]
```
