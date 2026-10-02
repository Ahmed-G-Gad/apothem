---
description: A near-miss request that plan-status must not pick up.
tags: [no-trigger, 'class:command', 'component:plan-status']
expected_outcome: Claude does not invoke plan-status.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Which HTTP status code means Too Many Requests?
