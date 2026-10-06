---
description: A request in research-review's domain, phrased as a user would type it.
tags: [trigger, 'class:command', 'component:research-review']
expected_outcome: Claude invokes the research-review command through the Skill tool.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Review this paper like a hostile second reviewer: score novelty, rigor and reproducibility and give me the list of required revisions.
