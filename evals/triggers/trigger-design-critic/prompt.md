---
description: A task design-critic exists for, phrased as a user would type it.
tags: [trigger, 'class:agent', 'component:design-critic']
expected_outcome: Claude delegates to the design-critic subagent through the Agent tool.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Review the checkout screen in src/ui/checkout before we ship it. Tell me what is wrong with it for users: hard-to-read text, tiny buttons, confusing errors. Rank the fixes by how much they hurt, and do not change any files.
