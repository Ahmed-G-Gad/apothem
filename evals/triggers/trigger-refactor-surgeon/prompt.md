---
description: A task refactor-surgeon exists for, phrased as a user would type it.
tags: [trigger, 'class:agent', 'component:refactor-surgeon']
expected_outcome: Claude delegates to the refactor-surgeon subagent through the Agent tool.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Refactor src/billing/invoice.py: extract the duplicated tax calculation into one helper without changing behavior, and confirm it with the existing tests.
