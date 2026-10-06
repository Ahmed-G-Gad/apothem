---
description: A task fact-checker exists for, phrased as a user would type it.
tags: [trigger, 'class:agent', 'component:fact-checker']
expected_outcome: Claude delegates to the fact-checker subagent through the Agent tool.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Fact-check this claim before it goes into our docs, with sources: 'SQLite is faster than PostgreSQL for every workload.'
