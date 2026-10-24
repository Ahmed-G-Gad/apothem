<!-- SPDX-License-Identifier: MIT -->

## Decision Tree

```mermaid
%%{ init: { "theme": "neutral" } }%%
%% verified: 2026-06-16 %%
%% provenance: commands/eval.md §Workflow %%
%% cross-reference: skills/eval-harness/SKILL.md + agents/prompt-evaluator.md %%
flowchart TD
    Start[/eval invoked] --> Q0{Dataset + scorer + candidate ratified?}
    Q0 -->|no| Inquiry[Surface structured inquiry · rules/authority-inquiry.md]
    Inquiry --> Q0
    Q0 -->|yes| Define[Phase 1 · define dataset + scorer via eval-harness skill]
    Define --> RunCand[Phase 2 · run candidate over dataset]
    RunCand --> Score[Phase 3 · score outputs with prompt-evaluator agent]
    Score --> Agg[Phase 4 · aggregate metrics + per-category breakdown]
    Agg --> Q4{Per-category regression vs baseline?}
    Q4 -->|yes| Ledger[Record regression in EVAL-N ledger]
    Q4 -->|no| Clean[Record baseline-clean attestation]
    Ledger --> Gate[Phase 5 · fifteen-bar pre-emission gate]
    Clean --> Gate
    Gate -->|fail| Iterate[Revise per gate §3 iterate-on-failure]
    Iterate --> Gate
    Gate -->|pass| Emit[Emit _inputs/eval-findings.md]
```
