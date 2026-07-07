---
name: sample-surface
description: Sample surface fixture exercising the deterministic output-shape PASS case for determinism-grep.
---

<!-- SPDX-License-Identifier: MIT -->

# /sample-surface

A sample surface fixture used by `determinism-grep` to exercise the PASS
case: a complete, deterministic output shape with an SPDX header, H2
section headings, an annotated option set whose recommended option carries
the `(Recommended)` postfix in its header, and a terminal next-step block.

## Steps

1. First step of the surface.
2. Second step of the surface.

## Choice

- `proceed (Recommended)`: advance to the next surface.
- `defer`: revisit later.

## Recommended Next Step

Run `/plan-status` to inspect the next phase's prerequisites before
proceeding to `/plan-execute`. The status command surfaces any pending
inquiries that would otherwise block execution.
