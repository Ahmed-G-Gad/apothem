---
description: A near-miss request that refactor-extract must not pick up.
tags: [no-trigger, 'class:skill', 'component:refactor-extract']
expected_outcome: Claude does not invoke refactor-extract.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Is it acceptable for a function to have more than one return statement? Two sentences.
