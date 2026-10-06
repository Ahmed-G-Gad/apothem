---
description: A request in plan-review's domain, phrased as a user would type it.
tags: [trigger, 'class:command', 'component:plan-review']
expected_outcome: Claude invokes the plan-review command through the Skill tool.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Do a forensic, line-by-line review of the plan suite at .apothem/plans/search-revamp and tell me whether it is ready to execute.
