---
description: A near-miss request that architecture-review must not pick up.
tags: [no-trigger, 'class:command', 'component:architecture-review']
expected_outcome: Claude does not invoke architecture-review.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

What is the difference between hexagonal architecture and a layered architecture? Two short paragraphs.
