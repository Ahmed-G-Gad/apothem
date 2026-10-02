---
description: A task research-scout exists for, phrased as a user would type it.
tags: [trigger, 'class:agent', 'component:research-scout']
expected_outcome: Claude delegates to the research-scout subagent through the Agent tool.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Find the authoritative sources on HTTP/3 connection migration (the RFC and the primary implementation docs), ranked by authority.
