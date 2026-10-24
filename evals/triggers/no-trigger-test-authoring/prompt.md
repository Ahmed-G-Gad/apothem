---
description: A near-miss request that test-authoring must not pick up.
tags: [no-trigger, 'class:skill', 'component:test-authoring']
expected_outcome: Claude does not invoke test-authoring.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

What does arrange-act-assert mean in a unit test? Two sentences.
