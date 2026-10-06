---
description: A near-miss request that research-analysis must not pick up.
tags: [no-trigger, 'class:command', 'component:research-analysis']
expected_outcome: Claude does not invoke research-analysis.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

In two sentences, what is the difference between a p-value and a confidence interval?
