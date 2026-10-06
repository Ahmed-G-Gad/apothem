---
description: A request in plan-design's domain, phrased as a user would type it.
tags: [trigger, 'class:command', 'component:plan-design']
expected_outcome: Claude invokes the plan-design command through the Skill tool.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

The search-revamp plan suite is architecture-heavy. Produce its architecture design document: components, interfaces, and the decisions behind them.
