---
description: A near-miss request that should not be delegated to research-scout.
tags: [no-trigger, 'class:agent', 'component:research-scout']
expected_outcome: Claude does not delegate to research-scout.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Spell-check these words: recieve, seperate, occured.
