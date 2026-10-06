---
description: A near-miss request that should not be delegated to fact-checker.
tags: [no-trigger, 'class:agent', 'component:fact-checker']
expected_outcome: Claude does not delegate to fact-checker.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Rewrite this sentence to sound friendlier: 'Your request was denied.'
