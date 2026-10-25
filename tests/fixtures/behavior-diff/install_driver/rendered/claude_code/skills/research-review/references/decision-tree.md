<!-- SPDX-License-Identifier: MIT -->

## Decision Tree

```mermaid
%%{ init: { "theme": "neutral" } }%%
%% verified: 2026-10-25 %%
%% provenance: commands/research-review.md §Workflow and §Mode --paper %%
%% cross-reference: agents/fact-checker.md, commands/research-paper.md, commands/research-publish.md, rules/pre-emission-gate.md, skills/research-suite/references/external-paper-checks.md %%
flowchart TD
    Start[/research-review invoked] --> Mode{"--paper supplied, or a paper given with no suite?"}
    Mode -->|yes| Ext["Mode --paper: intake · venue profile · roles · consistency audit"]
    Ext --> Score
    Mode -->|no| Gate0{Sequence Gate: paper + analysis + synthesis present?}
    Gate0 -->|no| Blocked[Halt: 'Blocked: run /research-paper first']
    Gate0 -->|yes| Ingest[Phase 1 read paper + evidence base · resolve venue standard]
    Ingest --> Venue{Venue standard resolved?}
    Venue -->|no| Inquire[Structured inquiry: ratify venue bar]
    Venue -->|yes| Score[Phase 2 score seven axes refute-by-default]
    Inquire --> Score
    Score --> Rerun[Phase 3 reproducibility re-run · headline numbers vs analysis]
    Rerun --> Cite[Phase 3 citation-integrity audit vs source ledger]
    Cite --> Triage[Phase 4 triage findings HIGH/MEDIUM/LOW + concrete-driver rationale]
    Triage --> Verify[Phase 4 fact-checker re-derives each finding refute-by-default]
    Verify --> Verdict{Finding verdict}
    Verdict -->|confirmed| List[Finding enters required-revision list]
    Verdict -->|downgraded| List
    Verdict -->|withdrawn| Drop[Finding dropped · misreading named]
    List --> Overall[Compose overall verdict accept/minor/major/reject]
    Drop --> Overall
    Overall --> GateN{Phase 5 fifteen-bar gate passes?}
    GateN -->|no| Revise[Revise per failing bar's action]
    Revise --> GateN
    GateN -->|yes| Emit[Emit _outputs/review-report.md · update Handoff Manifest]
```
