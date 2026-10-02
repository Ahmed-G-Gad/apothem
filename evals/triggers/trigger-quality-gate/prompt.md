---
description: A task quality-gate exists for, phrased as a user would type it.
tags: [trigger, 'class:agent', 'component:quality-gate']
expected_outcome: Claude delegates to the quality-gate subagent through the Agent tool.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Run the full quality matrix on this branch (lint, types, tests, security) and tell me what fails before I push.
