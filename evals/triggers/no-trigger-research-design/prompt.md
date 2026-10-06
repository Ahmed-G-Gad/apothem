---
description: A near-miss request that research-design must not pick up.
tags: [no-trigger, 'class:command', 'component:research-design']
expected_outcome: Claude does not invoke research-design.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Suggest a table layout for storing survey responses in PostgreSQL.
