---
description: A request in research-design's domain, phrased as a user would type it.
tags: [trigger, 'class:command', 'component:research-design']
expected_outcome: Claude invokes the research-design command through the Skill tool.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Design the study for our research question: turn the hypotheses into testable predictions, pick the variables and controls, run the power analysis, and preregister the analysis plan.
