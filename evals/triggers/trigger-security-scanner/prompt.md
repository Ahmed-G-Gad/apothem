---
description: A task security-scanner exists for, phrased as a user would type it.
tags: [trigger, 'class:agent', 'component:security-scanner']
expected_outcome: Claude delegates to the security-scanner subagent through the Agent tool.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Sweep this repository for committed secrets, shell injection and unsafe deserialization before the release.
