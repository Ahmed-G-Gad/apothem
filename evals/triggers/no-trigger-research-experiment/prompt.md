---
description: A near-miss request that research-experiment must not pick up.
tags: [no-trigger, 'class:command', 'component:research-experiment']
expected_outcome: Claude does not invoke research-experiment.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

What does the -x flag do when running pytest?
