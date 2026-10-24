---
description: A near-miss request that ecosystem-audit must not pick up.
tags: [no-trigger, 'class:skill', 'component:ecosystem-audit']
expected_outcome: Claude does not invoke ecosystem-audit.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

What is configuration drift? Two sentences.
