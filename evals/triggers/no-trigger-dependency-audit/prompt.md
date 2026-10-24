---
description: A near-miss request that dependency-audit must not pick up.
tags: [no-trigger, 'class:command', 'component:dependency-audit']
expected_outcome: Claude does not invoke dependency-audit.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

What is the difference between a direct and a transitive dependency? Two sentences.
