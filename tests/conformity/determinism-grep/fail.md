---
name: sample-surface-broken
description: Sample surface fixture exercising the determinism-grep FAIL case — the terminal next-step block is removed.
---

<!-- SPDX-License-Identifier: MIT -->

# /sample-surface-broken

A sample surface fixture used by `determinism-grep` to exercise the FAIL
case: the surface carries an SPDX header and H2 headings but the terminal
next-step block has been removed, so the output shape is incomplete — the
operator's onward path is unnamed at the surface's close.

## Steps

1. First step of the surface.
2. Second step of the surface.

## Choice

- `proceed`: advance to the next surface.
- `defer`: revisit later.
