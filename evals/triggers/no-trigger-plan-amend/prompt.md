---
description: A near-miss request that plan-amend must not pick up.
tags: [no-trigger, 'class:command', 'component:plan-amend']
expected_outcome: Claude does not invoke plan-amend.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Show me how far along the payments-v2 plan is and which phase comes next.
