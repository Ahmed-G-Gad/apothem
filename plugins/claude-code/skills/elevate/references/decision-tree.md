<!-- SPDX-License-Identifier: MIT -->

## Decision Tree

```mermaid
%%{ init: { "theme": "neutral" } }%%
%% verified: 2026-07-02 %%
%% provenance: commands/elevate.md §Workflow %%
%% cross-reference: commands/audit.md (detect front) + rules/agent-orchestration.md (orchestration) + rules/sota-elevation.md (elevation target) + commands/freshify.md (culmination) %%
flowchart TD
    Start[Target repository ingested] --> Base[Capture regression baseline · emit Derived Project Context + Constraints blocks]
    Base --> Enum[Enumerate every nuance into the prioritized stop inventory]
    Enum --> Detect[Detect: dispatch /audit over the technically-auditable dimensions · consume verified findings]
    Detect --> Fan[Fan out independent bespoke critique agents over the SOTA/elevation dimensions no audit covers]
    Fan --> Stop{Stop at next nuance}
    Stop --> Crit[Zero-trust critique across the cross-dimension axes]
    Crit --> Q1{Survives with cited authoritative evidence?}
    Q1 -->|yes| More
    Q1 -->|no| Q2{Remediation destructive?}
    Q2 -->|mechanically safe| Fix[Apply most-appropriate action via dimension-native primitive · cite file:line + source · disclose]
    Q2 -->|destructive| Conf[Route per-target confirmation · default non-destructive]
    Fix --> More{More nuances this pass?}
    Conf --> More
    More -->|yes| Stop
    More -->|no| Opp[Surface elevation opportunities · disclose · route for operator decision]
    Opp --> Q3{Cross-coherent at SOTA · zero open critiques · within max-passes?}
    Q3 -->|residual findings| Detect
    Q3 -->|converged| Prop[Propagate every change across the reference graph · highlight emerging merits]
    Prop --> Gate[Run fifteen-bar gate · verify cohorts via /test-suite · /eval · /release-readiness · emit elevation report]
    Gate --> Hand[Hand off elevated tree to /freshify for trace-free culmination · close session formally]
```
