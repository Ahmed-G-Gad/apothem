<!-- SPDX-License-Identifier: MIT -->

## Decision Tree

```mermaid
%%{ init: { "theme": "neutral" } }%%
%% verified: 2026-06-16 %%
%% provenance: commands/research-disseminate.md §Workflow %%
%% cross-reference: commands/research-publish.md (predecessor), agents/fact-checker.md, skills/research-suite/SKILL.md §Thirteen-Stage Research Lifecycle, rules/authority-inquiry.md %%
flowchart TD
    Start[/research-disseminate invoked] --> Gate0{Sequence Gate: publication-record.md present · package ready?}
    Gate0 -->|no| Blocked[Halt: 'Blocked: run /research-publish first']
    Gate0 -->|yes| Ingest[Phase 1 read publication record · compose preprint announcement]
    Ingest --> Archive{Archival repository resolved?}
    Archive -->|no| AskArch[structured inquiry: name the FAIR repository · block until resolved]
    AskArch --> Deposit[Phase 2 FAIR archival deposit · public artifacts]
    Archive -->|yes| Deposit
    Deposit --> Claim{Every public-artifact claim matches the paper?}
    Claim -->|no| Block1[Invented/overstated claim blocks the artifact · re-derive from paper]
    Block1 --> Track[Phase 3 altmetrics/impact tracking · revision loop · registered-report path]
    Claim -->|yes| Track
    Track --> Verify[Phase 4 fact-checker re-dereferences identifiers + re-checks claims]
    Verify --> Checklist[Phase 4 run dissemination-readiness checklist]
    Checklist --> Ready{Every checklist line met?}
    Ready -->|no| Hold[Hold plan at not-ready · resolve unmet lines]
    Hold --> Checklist
    Ready -->|yes| GateN{Phase 5 fifteen-bar gate passes?}
    GateN -->|no| Revise[Revise per failing bar's action]
    Revise --> GateN
    GateN -->|yes| Emit[Emit _outputs/dissemination-plan.md · close Handoff Manifest · hand off to operator]
```
