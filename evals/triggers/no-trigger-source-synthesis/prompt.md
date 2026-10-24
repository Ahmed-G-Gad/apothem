---
description: A near-miss request that source-synthesis must not pick up.
tags: [no-trigger, 'class:skill', 'component:source-synthesis']
expected_outcome: Claude does not invoke source-synthesis.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

What is the difference between a summary and a synthesis? Two sentences.
