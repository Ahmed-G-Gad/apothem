---
description: A request in code-review's domain, phrased as a user would type it.
tags: [trigger, 'class:command', 'component:code-review']
expected_outcome: Claude invokes the code-review command through the Skill tool.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Review the source files under src one at a time for readability, naming, complexity and comment quality, and give me severity-ranked findings. Do not edit anything.
