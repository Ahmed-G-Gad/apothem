---
description: A request in plan-status's domain, phrased as a user would type it.
tags: [trigger, 'class:command', 'component:plan-status']
expected_outcome: Claude invokes the plan-status command through the Skill tool.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

How far along is the plan suite in .apothem/plans/search-revamp? Which phases are done and what is next?
