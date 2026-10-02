---
description: A near-miss request that should not be delegated to test-runner.
tags: [no-trigger, 'class:agent', 'component:test-runner']
expected_outcome: Claude does not delegate to test-runner.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Write a unit test for a function that reverses a string.
