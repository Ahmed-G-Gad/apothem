---
description: A near-miss request that code-audit must not pick up.
tags: [no-trigger, 'class:command', 'component:code-audit']
expected_outcome: Claude does not invoke code-audit.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

What is the difference between dead code and unreachable code? One short paragraph.
