<!-- SPDX-License-Identifier: MIT -->

# workflow-concurrency-grep — pass fixtures

Conformant workflow fixtures for `workflow-concurrency-grep`.

- `ci.yml` — push/pull_request triggers, `cancel-in-progress: true`, every job declares `timeout-minutes: 20`.
- `release.yml` — release-class workflow, `cancel-in-progress: false`, `timeout-minutes: 60`.
