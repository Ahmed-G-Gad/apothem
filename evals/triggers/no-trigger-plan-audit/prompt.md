---
description: A near-miss request that plan-audit must not pick up.
tags: [no-trigger, 'class:command', 'component:plan-audit']
expected_outcome: Claude does not invoke plan-audit.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Audit the Python code under src/ for security problems.
