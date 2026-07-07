<!-- SPDX-License-Identifier: MIT -->

# workflow-concurrency-grep — fail fixtures

Drift fixtures for `workflow-concurrency-grep`.

- `ci.yml` — missing `concurrency:` block; lint job omits `timeout-minutes:`.
- `release.yml` — release-class workflow with `cancel-in-progress: true` (wrong polarity for deployment) and a 240-minute publish job exceeding the 90-minute full-matrix ceiling.
