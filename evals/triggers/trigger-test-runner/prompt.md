---
description: A task test-runner exists for, phrased as a user would type it.
tags: [trigger, 'class:agent', 'component:test-runner']
expected_outcome: Claude delegates to the test-runner subagent through the Agent tool.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Run the test suite and triage every failure by its root cause.
