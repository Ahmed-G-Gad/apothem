---
description: A task mcp-builder exists for, phrased as a user would type it.
tags: [trigger, 'class:agent', 'component:mcp-builder']
expected_outcome: Claude delegates to the mcp-builder subagent through the Agent tool.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Build an MCP server for our weather API with two tools, get_forecast(city) and get_alerts(region), both returning JSON.
