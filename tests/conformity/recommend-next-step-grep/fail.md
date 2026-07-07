---
name: sample-command-broken
description: Sample command fixture exercising the multi-action `## Next Steps` block with zero Recommended markers (FAIL case).
---

<!-- SPDX-License-Identifier: MIT -->

# /sample-command-broken

A sample command fixture used by `recommend-next-step-grep` to exercise
the FAIL case: the multi-action form is present but carries zero
`**Recommended**` markers, violating the exactly-one invariant.

## Steps

1. First step of the command.
2. Second step of the command.

## Next Steps

- Run `/plan-status` to inspect the next phase.
- Run `/plan-execute` to proceed.
- Run `/plan-review` to audit.
