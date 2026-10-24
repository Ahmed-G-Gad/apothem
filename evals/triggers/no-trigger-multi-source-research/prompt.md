---
description: A near-miss request that multi-source-research must not pick up.
tags: [no-trigger, 'class:skill', 'component:multi-source-research']
expected_outcome: Claude does not invoke multi-source-research.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

What is the difference between a primary and a secondary source? Two sentences.
