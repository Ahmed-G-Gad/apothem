---
description: A near-miss request that teaching-pack must not pick up.
tags: [no-trigger, 'class:skill', 'component:teaching-pack']
expected_outcome: Claude does not invoke teaching-pack.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

In one short paragraph, tell me what papers/consensus-under-failures.md claims in its abstract. I only need the gist before a meeting.
