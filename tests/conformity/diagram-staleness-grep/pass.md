<!-- SPDX-License-Identifier: MIT -->

# Sample Artifact — Fresh Diagram

This fixture is the PASS case for `diagram-staleness-grep`. The
embedded Mermaid diagram carries a verified-date marker within the
freshness ceiling.

```mermaid
%% verified: 2026-04-28 %%
%% provenance: sample fixture for the staleness grep %%
flowchart TD
    Start --> Check{Verified date present?}
    Check -->|yes| Done[Pass]
    Check -->|no| Flag[Fail]
```

The diagram is current; the grep returns clean.
