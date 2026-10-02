---
description: A near-miss request that plan-design must not pick up.
tags: [no-trigger, 'class:command', 'component:plan-design']
expected_outcome: Claude does not invoke plan-design.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Draw a quick ASCII diagram of a three-tier web application.
