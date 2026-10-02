---
description: A task convention-auditor exists for, phrased as a user would type it.
tags: [trigger, 'class:agent', 'component:convention-auditor']
expected_outcome: Claude delegates to the convention-auditor subagent through the Agent tool.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Audit naming and cross-references across the rules and skills folders: kebab-case file names, SPDX headers, and dead links, with a PASS or FINDING verdict per item.
