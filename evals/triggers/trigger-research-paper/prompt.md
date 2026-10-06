---
description: A request in research-paper's domain, phrased as a user would type it.
tags: [trigger, 'class:command', 'component:research-paper']
expected_outcome: Claude invokes the research-paper command through the Skill tool.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Write up our results as a paper draft: abstract, introduction, related work, method, results, discussion, and references that all resolve.
