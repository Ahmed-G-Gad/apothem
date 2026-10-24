<!-- SPDX-License-Identifier: MIT -->

## Decision Tree

```mermaid
%% verified: 2026-06-16 %%
%% provenance: commands/fortress.md §Workflow %%
%% cross-reference: commands/audit.md, commands/elevate.md, commands/release-readiness.md, commands/plan.md, commands/research.md, skills/workflow/SKILL.md, rules/planning-techniques.md %%
flowchart TD
    Start[/fortress invoked/] --> Frame{Target + scope unambiguous?}
    Frame -->|no| Inquiry[Frame: structured-inquiry target + scope + remediation boundary]
    Inquiry --> Frame
    Frame -->|yes| Detect[Detect: dispatch /audit over scoped dimensions · consume verified findings]
    Detect --> Verify[EXTREMELY-CRITIQUE verify each remediation target · refute-by-default]
    Verify --> Survive{Fix survives non-refute majority?}
    Survive -->|no| Rederive[Re-derive fix or escalate finding]
    Rederive --> Verify
    Survive -->|yes| OptIn{--autonomous set?}
    OptIn -->|no| Plan[Present remediation plan · confirm · per-action gate irreversible steps]
    OptIn -->|yes| Remediate[Remediate at root via surgical-guard / secret-rotation / vuln-triage / scoped /elevate]
    Plan --> Remediate
    Remediate --> Reaudit[Re-audit: re-run scoped /audit over remediated repo]
    Reaudit --> Clear{HIGH count == 0 AND MEDIUM remediated-or-accepted?}
    Clear -->|no| Cap{--max-rounds reached?}
    Cap -->|no| Detect
    Cap -->|yes| Retreat[Deterministic retreat: BLOCKED report · residual findings + owners + routed next action]
    Clear -->|yes| Gate[Gate: dispatch /release-readiness → READY/BLOCKED]
    Retreat --> Synth
    Gate --> Synth[Synthesize fortress-posture report · workflow fifteen-bar gate]
    Synth --> Emit[Emit deterministic report + recommended next move]
```
