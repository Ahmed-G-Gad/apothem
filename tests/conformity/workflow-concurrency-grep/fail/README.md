<!-- SPDX-License-Identifier: MIT -->

# workflow-concurrency-grep — fail fixtures

Drift fixtures for `workflow-concurrency-grep`, run by
`../test_workflow_concurrency_grep.py`.

- `ci.yml` — missing `concurrency:` block; lint job omits `timeout-minutes:`.
- `release.yml` — release-class workflow with `cancel-in-progress: true` (wrong polarity for deployment) and a 240-minute publish job exceeding the 30-minute short-job ceiling.
- `matrix-timeouts.yml` — one drift per job: an integer over the 90-minute matrix ceiling, a Windows limit over 120, an other-cell limit over 90, a different OS in the conditional, an extra `||` term, an `inputs.` expression, and the conditional on a job without a matrix.
- `reusable-caller.yml` — reusable-workflow callers whose `with: timeout-minutes` breaks the same rules: Windows limit over 120, other-cell limit over 90, an `inputs.` expression, and 60 on a caller without a matrix (ceiling 30).
