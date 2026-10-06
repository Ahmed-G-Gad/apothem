---
description: A task codebase-explorer exists for, phrased as a user would type it.
tags: [trigger, 'class:agent', 'component:codebase-explorer']
expected_outcome: Claude delegates to the codebase-explorer subagent through the Agent tool.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Find every place in this repository where load_config is called and map which modules depend on it.
