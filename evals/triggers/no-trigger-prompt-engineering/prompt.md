---
description: A near-miss request that prompt-engineering must not pick up.
tags: [no-trigger, 'class:skill', 'component:prompt-engineering']
expected_outcome: Claude does not invoke prompt-engineering.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

What does the temperature setting do in text generation? Two sentences.
