---
description: A near-miss request that should not be delegated to quality-gate.
tags: [no-trigger, 'class:agent', 'component:quality-gate']
expected_outcome: Claude does not delegate to quality-gate.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

Conceptually, what is a quality gate in a CI pipeline?
