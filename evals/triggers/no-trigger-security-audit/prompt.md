---
description: A near-miss request that security-audit must not pick up.
tags: [no-trigger, 'class:command', 'component:security-audit']
expected_outcome: Claude does not invoke security-audit.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

What are the three most common causes of SQL injection? One sentence each.
