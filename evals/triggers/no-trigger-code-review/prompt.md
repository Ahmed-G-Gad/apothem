---
description: A near-miss request that code-review must not pick up.
tags: [no-trigger, 'class:command', 'component:code-review']
expected_outcome: Claude does not invoke code-review.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

What makes a good variable name? Give me three rules of thumb.
