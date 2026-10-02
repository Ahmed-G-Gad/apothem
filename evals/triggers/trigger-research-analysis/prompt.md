---
description: A request in research-analysis's domain, phrased as a user would type it.
tags: [trigger, 'class:command', 'component:research-analysis']
expected_outcome: Claude invokes the research-analysis command through the Skill tool.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Run the preregistered analysis on the experiment data: compute the effect sizes with confidence intervals and apply the multiple-comparison correction.
