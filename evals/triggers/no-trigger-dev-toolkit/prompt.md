---
description: A near-miss request that dev-toolkit must not pick up.
tags: [no-trigger, 'class:skill', 'component:dev-toolkit']
expected_outcome: Claude does not invoke dev-toolkit.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

What does red-green-refactor mean in test-driven development? Two sentences.
