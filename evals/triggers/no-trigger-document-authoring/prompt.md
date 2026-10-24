---
description: A near-miss request that document-authoring must not pick up.
tags: [no-trigger, 'class:skill', 'component:document-authoring']
expected_outcome: Claude does not invoke document-authoring.
max_turns: 3
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

<!-- SPDX-License-Identifier: MIT -->

What is the difference between a thesis and a dissertation? Two sentences.
