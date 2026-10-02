---
description: A near-miss request that should not be delegated to dependency-auditor.
tags: [no-trigger, 'class:agent', 'component:dependency-auditor']
expected_outcome: Claude does not delegate to dependency-auditor.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

What does the ~= operator mean in a requirements.txt line?
