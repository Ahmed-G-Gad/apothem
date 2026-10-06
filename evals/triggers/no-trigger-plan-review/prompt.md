---
description: A near-miss request that plan-review must not pick up.
tags: [no-trigger, 'class:command', 'component:plan-review']
expected_outcome: Claude does not invoke plan-review.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Review this Python function for bugs: def avg(xs): return sum(xs) / len(xs)
