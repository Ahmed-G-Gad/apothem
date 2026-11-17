<!-- SPDX-License-Identifier: MIT -->

# workflow-concurrency-grep — pass fixtures

Conformant workflow fixtures for `workflow-concurrency-grep`, run by
`../test_workflow_concurrency_grep.py`.

- `ci.yml` — push/pull_request triggers, `cancel-in-progress: true`, every job declares `timeout-minutes: 20`.
- `release.yml` — release-class workflow, `cancel-in-progress: false`, `timeout-minutes: 30`.
- `matrix-timeouts.yml` — matrix jobs with `timeout-minutes: 90` and with `${{ matrix.os == 'windows-latest' && N || M }}` (N at most 120, M at most 90), written with standard, compact and extra spacing.
- `reusable-caller.yml` — reusable-workflow callers: a matrix caller passing the Windows conditional through `with: timeout-minutes`, a caller without a matrix passing 30, and a caller passing no limit.
