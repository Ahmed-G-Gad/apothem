<!-- SPDX-License-Identifier: MIT -->

## Decision Tree

```mermaid
%% verified: 2026-06-16 %%
%% provenance: commands/audit.md §Workflow %%
%% cross-reference: commands/workflow.md, commands/code-review.md, commands/security-audit.md, commands/elevate.md, commands/release-readiness.md, skills/workflow/SKILL.md %%
flowchart TD
    Start[/audit invoked/] --> Frame{Target + dimension set unambiguous?}
    Frame -->|no| Inquiry[Frame: structured-inquiry target + dimensions]
    Inquiry --> Frame
    Frame -->|yes| Decompose[Decompose into scoped audit dimensions + findings return contracts]
    Decompose --> OptIn{--autonomous set?}
    OptIn -->|no| Plan[Present dimension plan · confirm]
    OptIn -->|yes| Dispatch[Dispatch scoped audits in PARALLEL]
    Plan --> Dispatch
    Dispatch --> RunDim[each audit runs · emits severity-triaged findings + gate attestation]
    RunDim --> Verify[Refute-by-default critics over each finding]
    Verify --> Survive{Non-refute majority?}
    Survive -->|no| Drop[Drop finding · record refutation]
    Survive -->|yes| Keep[Finding survives]
    Drop --> Synth
    Keep --> Synth[Synthesize: dedup across dimensions · severity-triage · route remediation]
    Synth --> Gate[Workflow fifteen-bar gate over the report]
    Gate --> Emit[Emit deterministic findings report + recommended next move]
```
