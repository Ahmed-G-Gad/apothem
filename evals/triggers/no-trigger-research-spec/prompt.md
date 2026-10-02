---
description: A near-miss request that research-spec must not pick up.
tags: [no-trigger, 'class:command', 'component:research-spec']
expected_outcome: Claude does not invoke research-spec.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Write an OpenAPI description for a GET /users endpoint that returns a list of users.
