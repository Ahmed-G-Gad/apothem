---
description: A near-miss request that should not invoke decision-matrix.
tags: [no-trigger, 'class:skill', 'component:decision-matrix']
expected_outcome: Claude does not invoke decision-matrix.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

What is the difference between a message queue and a pub/sub topic? Explain it in two short paragraphs.
