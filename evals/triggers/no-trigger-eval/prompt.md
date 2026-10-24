---
description: A near-miss request that eval must not pick up.
tags: [no-trigger, 'class:command', 'component:eval']
expected_outcome: Claude does not invoke eval.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

What does pass@k mean for code-generation benchmarks? Two sentences.
