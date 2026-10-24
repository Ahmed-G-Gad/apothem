---
description: A near-miss request that threat-model-audit must not pick up.
tags: [no-trigger, 'class:command', 'component:threat-model-audit']
expected_outcome: Claude does not invoke threat-model-audit.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

What do the letters in STRIDE stand for? One line each.
