---
description: A request in plan-audit's domain, phrased as a user would type it.
tags: [trigger, 'class:command', 'component:plan-audit']
expected_outcome: Claude invokes the plan-audit command through the Skill tool.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Audit the plan suite in .apothem/plans/search-revamp end to end and fix whatever findings come up until it is clean.
