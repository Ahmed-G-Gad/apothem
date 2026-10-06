---
description: A near-miss request that research-synthesis must not pick up.
tags: [no-trigger, 'class:command', 'component:research-synthesis']
expected_outcome: Claude does not invoke research-synthesis.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Summarize in one sentence: 'Caching trades memory for latency by keeping recent results close to the consumer.'
