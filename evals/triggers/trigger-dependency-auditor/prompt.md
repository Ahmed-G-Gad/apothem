---
description: A task dependency-auditor exists for, phrased as a user would type it.
tags: [trigger, 'class:agent', 'component:dependency-auditor']
expected_outcome: Claude delegates to the dependency-auditor subagent through the Agent tool.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Audit our dependencies for supply-chain risk before the release: unpinned, stale, duplicate and known-vulnerable packages.
