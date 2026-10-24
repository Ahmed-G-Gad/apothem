---
description: A near-miss request that test-suite must not pick up.
tags: [no-trigger, 'class:command', 'component:test-suite']
expected_outcome: Claude does not invoke test-suite.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

What is the difference between a unit test and an integration test? Two sentences.
