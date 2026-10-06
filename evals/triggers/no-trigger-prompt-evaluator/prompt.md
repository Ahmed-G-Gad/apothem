---
description: A near-miss request that should not be delegated to prompt-evaluator.
tags: [no-trigger, 'class:agent', 'component:prompt-evaluator']
expected_outcome: Claude does not delegate to prompt-evaluator.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Write a system prompt for a customer-support assistant for a bike shop.
