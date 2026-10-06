---
description: A request in plan-execute's domain, phrased as a user would type it.
tags: [trigger, 'class:command', 'component:plan-execute']
expected_outcome: Claude invokes the plan-execute command through the Skill tool.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Carry out phase 02 of the plan suite in .apothem/plans/search-revamp: implement its tasks, run the gates, and write the phase report.
