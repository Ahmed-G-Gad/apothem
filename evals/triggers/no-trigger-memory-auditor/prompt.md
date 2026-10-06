---
description: A near-miss request that should not be delegated to memory-auditor.
tags: [no-trigger, 'class:agent', 'component:memory-auditor']
expected_outcome: Claude does not delegate to memory-auditor.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Explain the difference between stack and heap memory.
