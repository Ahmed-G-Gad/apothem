<!-- SPDX-License-Identifier: MIT -->

## Decision Tree

```mermaid
%%{ init: { "theme": "neutral" } }%%
%% verified: 2026-06-15 %%
%% provenance: commands/research-paper.md §Workflow %%
%% cross-reference: agents/fact-checker.md, commands/research-analysis.md, commands/research-review.md, rules/pre-emission-gate.md %%
flowchart TD
    Start[/research-paper invoked] --> Gate0{Sequence Gate: analysis.md + synthesis.md + study-design.md present?}
    Gate0 -->|no| Blocked[Halt: 'Blocked: run /research-analysis first']
    Gate0 -->|yes| Ingest[Phase 1 ingest synthesis · study design · confirmed results · discover venue]
    Ingest --> Compose[Phase 2 compose nine sections clean-room · incremental generation]
    Compose --> Ledger[Phase 3 build reference ledger · bidirectional cross-check]
    Ledger --> Orphan{Orphan reference or dangling citation?}
    Orphan -->|yes| Resolve[Resolve: add citation, list reference, or inquire on missing source]
    Orphan -->|no| Verify[Phase 4 fact-checker resolves each reference refute-by-default]
    Resolve --> Verify
    Verify --> Verdict{Reference verdict}
    Verdict -->|resolved| Keep[Reference earns its citation]
    Verdict -->|misattributed| Fix[Correct to supporting source or remove the claim]
    Verdict -->|phantom| Fix
    Fix --> Verify
    Keep --> Claim{Every results claim traces to a confirmed analysis result?}
    Claim -->|no| Recheck[Remove fragile/unverified claims · report fragile in limitations]
    Claim -->|yes| GateN{Phase 5 fifteen-bar gate passes?}
    Recheck --> GateN
    GateN -->|no| Revise[Revise per failing bar's action]
    Revise --> GateN
    GateN -->|yes| Emit[Emit paper/ manuscript + reference ledger · update Handoff Manifest]
```
