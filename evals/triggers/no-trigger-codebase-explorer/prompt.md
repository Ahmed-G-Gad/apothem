---
description: A near-miss request that should not be delegated to codebase-explorer.
tags: [no-trigger, 'class:agent', 'component:codebase-explorer']
expected_outcome: Claude does not delegate to codebase-explorer.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Write a Python function load_config(path) that reads a TOML file and returns a dict.
