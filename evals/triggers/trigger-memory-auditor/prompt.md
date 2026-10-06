---
description: A task memory-auditor exists for, phrased as a user would type it.
tags: [trigger, 'class:agent', 'component:memory-auditor']
expected_outcome: Claude delegates to the memory-auditor subagent through the Agent tool.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Audit MEMORY.md and its topic files against the filesystem: check that the counts, referenced paths and dates still hold.
