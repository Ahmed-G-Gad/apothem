---
description: A near-miss request that freshify must not pick up.
tags: [no-trigger, 'class:command', 'component:freshify', user-invoked-only]
expected_outcome: Claude does not invoke freshify.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

What is a __pycache__ directory for?
